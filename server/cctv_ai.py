"""
CCTV AI Violence Detection Module for NaariRakshak
Uses ViT (Vision Transformer) model for frame-level violence classification.
Model: jaranohaal/vit-base-violence-detection (98.8% accuracy)
"""
import os
# macOS: prevent duplicate libomp crash
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
# Prevent tqdm progress bars from crashing background threads under nohup
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import io
import time
import json
import uuid
import base64
import threading
from datetime import datetime, timezone

# Pre-import torch before cv2 to avoid segfault from OpenMP library conflicts on macOS
import torch
torch.set_num_threads(1)  # Avoid OpenMP segfault when model is created in a worker thread

import cv2
import numpy as np
from PIL import Image

# Lazy-loaded model components
_model = None
_feature_extractor = None
_model_lock = threading.Lock()
_model_loading = False
_model_load_failed = False
_model_fail_time = 0
_MODEL_RETRY_COOLDOWN = 30  # seconds before retrying after failure

MODEL_ID = "jaranohaal/vit-base-violence-detection"
CONFIDENCE_THRESHOLD = 0.85
FRAME_SAMPLE_INTERVAL = 15  # analyse every Nth frame


def _convert_timm_to_hf(timm_state):
    """Convert timm ViT state dict keys to HuggingFace ViT format."""
    hf = {}
    hf['vit.embeddings.cls_token'] = timm_state['cls_token']
    hf['vit.embeddings.position_embeddings'] = timm_state['pos_embed']
    hf['vit.embeddings.patch_embeddings.projection.weight'] = timm_state['patch_embed.proj.weight']
    hf['vit.embeddings.patch_embeddings.projection.bias'] = timm_state['patch_embed.proj.bias']
    hf['vit.layernorm.weight'] = timm_state['norm.weight']
    hf['vit.layernorm.bias'] = timm_state['norm.bias']
    hf['classifier.weight'] = timm_state['head.weight']
    hf['classifier.bias'] = timm_state['head.bias']
    for i in range(12):
        t = f'blocks.{i}'
        h = f'vit.encoder.layer.{i}'
        hf[f'{h}.layernorm_before.weight'] = timm_state[f'{t}.norm1.weight']
        hf[f'{h}.layernorm_before.bias'] = timm_state[f'{t}.norm1.bias']
        hf[f'{h}.layernorm_after.weight'] = timm_state[f'{t}.norm2.weight']
        hf[f'{h}.layernorm_after.bias'] = timm_state[f'{t}.norm2.bias']
        hf[f'{h}.attention.output.dense.weight'] = timm_state[f'{t}.attn.proj.weight']
        hf[f'{h}.attention.output.dense.bias'] = timm_state[f'{t}.attn.proj.bias']
        # Split combined QKV into separate Q, K, V
        q_w, k_w, v_w = timm_state[f'{t}.attn.qkv.weight'].chunk(3, dim=0)
        q_b, k_b, v_b = timm_state[f'{t}.attn.qkv.bias'].chunk(3, dim=0)
        hf[f'{h}.attention.attention.query.weight'] = q_w
        hf[f'{h}.attention.attention.query.bias'] = q_b
        hf[f'{h}.attention.attention.key.weight'] = k_w
        hf[f'{h}.attention.attention.key.bias'] = k_b
        hf[f'{h}.attention.attention.value.weight'] = v_w
        hf[f'{h}.attention.attention.value.bias'] = v_b
        hf[f'{h}.intermediate.dense.weight'] = timm_state[f'{t}.mlp.fc1.weight']
        hf[f'{h}.intermediate.dense.bias'] = timm_state[f'{t}.mlp.fc1.bias']
        hf[f'{h}.output.dense.weight'] = timm_state[f'{t}.mlp.fc2.weight']
        hf[f'{h}.output.dense.bias'] = timm_state[f'{t}.mlp.fc2.bias']
    return hf


def _load_model():
    """Lazy-load the ViT violence detection model."""
    global _model, _feature_extractor, _model_loading, _model_load_failed, _model_fail_time
    if _model is not None:
        return True
    # Cooldown after a recent failure to avoid spamming
    if _model_load_failed and (time.time() - _model_fail_time) < _MODEL_RETRY_COOLDOWN:
        return False
    with _model_lock:
        if _model is not None:
            return True
        _model_loading = True
        try:
            import torch
            from transformers import ViTForImageClassification, ViTConfig
            try:
                from transformers import ViTImageProcessor as _ViTProcessor
            except ImportError:
                from transformers import ViTFeatureExtractor as _ViTProcessor
            print(f"[CCTV-AI] Loading model {MODEL_ID}...")
            _feature_extractor = _ViTProcessor.from_pretrained(MODEL_ID)

            # The checkpoint uses timm weight format; convert to HF format
            config = ViTConfig.from_pretrained(MODEL_ID)
            config.id2label = {0: "non-violence", 1: "violence"}
            config.label2id = {"non-violence": 0, "violence": 1}
            _model = ViTForImageClassification(config)

            from huggingface_hub import hf_hub_download
            weights_path = hf_hub_download(MODEL_ID, filename="model.safetensors")
            from safetensors.torch import load_file
            timm_state = load_file(weights_path)

            # Detect if weights are in timm format and convert
            if any(k.startswith('blocks.') for k in timm_state):
                timm_state = _convert_timm_to_hf(timm_state)

            _model.load_state_dict(timm_state, strict=True)
            _model.eval()
            _model_load_failed = False
            print(f"[CCTV-AI] Model loaded. Labels: {_model.config.id2label}")
            return True
        except Exception as e:
            _model = None
            print(f"[CCTV-AI] Failed to load model: {e}")
            _model_load_failed = True
            _model_fail_time = time.time()
            return False
        finally:
            _model_loading = False


def is_model_loaded():
    return _model is not None


def is_model_loading():
    return _model_loading


def get_model_status():
    return {
        "loaded": is_model_loaded(),
        "loading": is_model_loading(),
        "model_id": MODEL_ID,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "frame_interval": FRAME_SAMPLE_INTERVAL
    }


def analyse_frame(image_bytes: bytes) -> dict:
    """
    Analyse a single image frame for violence.
    Returns: {violence: bool, confidence: float, label: str, raw_scores: {}}
    """
    if not _load_model():
        return {"error": "Model not available", "violence": False, "confidence": 0}

    import torch
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = _feature_extractor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = _model(**inputs)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)[0]

        scores = {}
        for idx, prob in enumerate(probs):
            label = _model.config.id2label[idx]
            scores[label] = round(prob.item(), 4)

        # Get the violence class score (exact match, not substring)
        violence_score = scores.get('violence', 0.0)

        is_violent = violence_score >= CONFIDENCE_THRESHOLD
        predicted_idx = logits.argmax(-1).item()
        predicted_label = _model.config.id2label[predicted_idx]

        return {
            "violence": is_violent,
            "confidence": round(violence_score, 4),
            "label": predicted_label,
            "raw_scores": scores,
            "threshold": CONFIDENCE_THRESHOLD
        }
    except Exception as e:
        print(f"[CCTV-AI] Frame analysis error: {e}")
        return {"error": str(e), "violence": False, "confidence": 0}


def analyse_video(video_path: str, progress_callback=None) -> dict:
    """
    Analyse a video file frame-by-frame.
    Returns: {total_frames, analysed_frames, detections: [{frame_num, timestamp_sec, confidence, snapshot_b64}], summary}
    """
    if not _load_model():
        return {"error": "Model not available"}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open video: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    detections = []
    analysed = 0
    frame_num = 0
    recording = False
    record_start = None
    record_frames = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_num % FRAME_SAMPLE_INTERVAL == 0:
                # Convert BGR to RGB and encode to bytes
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                buf = io.BytesIO()
                pil_img.save(buf, format='JPEG', quality=70)
                img_bytes = buf.getvalue()

                result = analyse_frame(img_bytes)
                analysed += 1

                if result.get('violence'):
                    timestamp_sec = round(frame_num / fps, 2)
                    # Create thumbnail
                    thumb = cv2.resize(frame, (320, 180))
                    _, thumb_enc = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    snapshot_b64 = base64.b64encode(thumb_enc).decode('utf-8')

                    detection = {
                        "frame_num": frame_num,
                        "timestamp_sec": timestamp_sec,
                        "confidence": result['confidence'],
                        "label": result['label'],
                        "snapshot_b64": snapshot_b64,
                        "detected_at": datetime.now(timezone.utc).isoformat()
                    }
                    detections.append(detection)

                    # Start recording violent segment
                    if not recording:
                        recording = True
                        record_start = max(0, frame_num - int(fps * 2))
                        record_frames = []

                if progress_callback and analysed % 5 == 0:
                    progress_callback({
                        "progress": round(frame_num / max(total_frames, 1) * 100, 1),
                        "analysed": analysed,
                        "detections_so_far": len(detections)
                    })

            # Collect frames if recording violence segment
            if recording:
                record_frames.append(frame)
                if len(record_frames) > int(fps * 10):
                    recording = False

            frame_num += 1
    finally:
        cap.release()

    # Save recorded violent clip if any
    clip_path = None
    if record_frames and len(record_frames) > 10:
        clip_path = os.path.join('evidence', f'violence_{uuid.uuid4().hex[:8]}.mp4')
        os.makedirs('evidence', exist_ok=True)
        h, w = record_frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(clip_path, fourcc, fps, (w, h))
        for f in record_frames:
            writer.write(f)
        writer.release()
        print(f"[CCTV-AI] Saved violence clip: {clip_path}")

    return {
        "total_frames": frame_num,
        "analysed_frames": analysed,
        "fps": fps,
        "duration_sec": round(frame_num / fps, 2),
        "detections": detections,
        "violence_detected": len(detections) > 0,
        "violence_frame_ratio": round(len(detections) / max(analysed, 1), 4),
        "clip_path": clip_path,
        "summary": _build_summary(detections, frame_num, fps)
    }


def _build_summary(detections, total_frames, fps):
    if not detections:
        return "No violence detected in the video feed."
    duration = round(total_frames / fps, 1)
    first = detections[0]
    avg_conf = round(sum(d['confidence'] for d in detections) / len(detections), 2)
    return (
        f"⚠️ Violence detected: {len(detections)} incident(s) over {duration}s video. "
        f"First detection at {first['timestamp_sec']}s with {first['confidence']*100:.0f}% confidence. "
        f"Average confidence: {avg_conf*100:.0f}%. Clip recorded for evidence."
    )
