"""
CCTV AI Threat Detection Module for NaariRakshak
Uses OpenAI CLIP zero-shot for multi-category threat detection.
Detects: violence, harassment, eve teasing, stalking, weapons, distress.
Model: openai/clip-vit-base-patch32 (zero-shot, no specific training needed)
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import io
import time
import uuid
import base64
import threading
from datetime import datetime, timezone

import torch
torch.set_num_threads(1)

import cv2
import numpy as np
from PIL import Image

# ─── Model state ───
_clip_model = None
_clip_processor = None
_model_lock = threading.Lock()
_model_loading = False
_model_load_failed = False
_model_fail_time = 0
_MODEL_RETRY_COOLDOWN = 30

MODEL_ID = "openai/clip-vit-base-patch32"
THREAT_THRESHOLD = 0.30  # threat score above this = alert
FRAME_SAMPLE_INTERVAL = 15

# ─── Safety threat labels for zero-shot classification ───
THREAT_LABELS = {
    "violence": "a photo of people fighting, punching, kicking, physical assault, beating someone",
    "harassment": "a photo of a man aggressively grabbing a woman, eve teasing, unwanted physical contact",
    "stalking": "a photo of a person secretly following another person on the street, trailing someone closely",
    "weapon_threat": "a photo of a person holding a knife or gun and threatening another person",
    "distress": "a photo of a woman screaming for help while being attacked or grabbed by someone",
    "robbery": "a photo of someone violently snatching a bag or purse from a person on the street",
}

SAFE_LABELS = {
    "normal_activity": "a photo of people walking normally on a street, everyday peaceful activity",
    "empty_scene": "a photo of an empty room, empty street, or empty area with no people",
    "indoor_normal": "a photo of a normal indoor scene, office, home, classroom",
    "dark_scene": "a photo of a dark empty room or dark empty street at night with no people visible",
    "outdoor_normal": "a photo of a normal outdoor scene, park, parking lot, garden, building exterior",
    "sitting_relaxing": "a photo of people sitting, relaxing, having a conversation peacefully",
}

# All labels combined for CLIP inference
_all_labels = list(THREAT_LABELS.values()) + list(SAFE_LABELS.values())
_all_keys = list(THREAT_LABELS.keys()) + list(SAFE_LABELS.keys())


def _load_model():
    """Lazy-load the CLIP zero-shot model."""
    global _clip_model, _clip_processor, _model_loading, _model_load_failed, _model_fail_time
    if _clip_model is not None:
        return True
    if _model_load_failed and (time.time() - _model_fail_time) < _MODEL_RETRY_COOLDOWN:
        return False
    with _model_lock:
        if _clip_model is not None:
            return True
        _model_loading = True
        try:
            from transformers import CLIPModel, CLIPProcessor
            print(f"[CCTV-AI] Loading CLIP model {MODEL_ID}...", flush=True)
            _clip_processor = CLIPProcessor.from_pretrained(MODEL_ID, use_fast=False)
            _clip_model = CLIPModel.from_pretrained(MODEL_ID)
            _clip_model.eval()
            _model_load_failed = False
            print(f"[CCTV-AI] CLIP model loaded. {len(THREAT_LABELS)} threat + {len(SAFE_LABELS)} safe categories.")
            return True
        except Exception as e:
            _clip_model = None
            print(f"[CCTV-AI] Failed to load CLIP: {e}")
            _model_load_failed = True
            _model_fail_time = time.time()
            return False
        finally:
            _model_loading = False


def is_model_loaded():
    return _clip_model is not None


def is_model_loading():
    return _model_loading


def get_model_status():
    return {
        "loaded": is_model_loaded(),
        "loading": is_model_loading(),
        "model_id": MODEL_ID,
        "threat_threshold": THREAT_THRESHOLD,
        "frame_interval": FRAME_SAMPLE_INTERVAL,
        "threat_categories": list(THREAT_LABELS.keys()),
        "safe_categories": list(SAFE_LABELS.keys()),
    }


def analyse_frame(image_bytes: bytes) -> dict:
    """
    Analyse a single frame using CLIP zero-shot against safety threat labels.
    Returns scores for each threat category + overall threat assessment.
    """
    if not _load_model():
        return {"error": "Model not available", "threat_detected": False, "threat_score": 0}

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = _clip_processor(
            text=_all_labels, images=image, return_tensors="pt", padding=True
        )
        with torch.no_grad():
            outputs = _clip_model(**inputs)
            logits = outputs.logits_per_image[0]
            probs = logits.softmax(dim=-1)

        # Map probabilities to category names
        scores = {}
        for i, key in enumerate(_all_keys):
            scores[key] = round(probs[i].item(), 4)

        # Compute threat vs safe scores (use averages to normalize for label count)
        threat_scores = {k: scores[k] for k in THREAT_LABELS}
        safe_scores = {k: scores[k] for k in SAFE_LABELS}
        max_threat_key = max(threat_scores, key=threat_scores.get)
        max_threat_score = threat_scores[max_threat_key]
        total_threat = sum(threat_scores.values())
        total_safe = sum(safe_scores.values())
        avg_threat = total_threat / len(THREAT_LABELS)
        avg_safe = total_safe / len(SAFE_LABELS)

        # Require: top single threat > 15% AND average threat > average safe
        threat_detected = max_threat_score >= 0.15 and avg_threat > avg_safe

        # Build readable label
        if threat_detected:
            label = max_threat_key.replace("_", " ").title()
        else:
            max_safe_key = max(safe_scores, key=safe_scores.get)
            label = max_safe_key.replace("_", " ").title()

        return {
            "threat_detected": threat_detected,
            "threat_score": round(total_threat, 4),
            "safe_score": round(total_safe, 4),
            "top_threat": max_threat_key,
            "top_threat_score": round(max_threat_score, 4),
            "label": label,
            "threat_scores": threat_scores,
            "safe_scores": safe_scores,
            "threshold": THREAT_THRESHOLD,
            # Backward compat
            "violence": threat_detected,
            "confidence": round(max_threat_score, 4),
            "raw_scores": scores,
        }
    except Exception as e:
        print(f"[CCTV-AI] Frame analysis error: {e}")
        return {"error": str(e), "threat_detected": False, "threat_score": 0, "violence": False, "confidence": 0}


def analyse_video(video_path: str, progress_callback=None) -> dict:
    """Analyse a video file frame-by-frame for threats."""
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
    record_frames = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_num % FRAME_SAMPLE_INTERVAL == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                buf = io.BytesIO()
                pil_img.save(buf, format='JPEG', quality=70)
                img_bytes = buf.getvalue()

                result = analyse_frame(img_bytes)
                analysed += 1

                if result.get('threat_detected'):
                    timestamp_sec = round(frame_num / fps, 2)
                    thumb = cv2.resize(frame, (320, 180))
                    _, thumb_enc = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    snapshot_b64 = base64.b64encode(thumb_enc).decode('utf-8')

                    detection = {
                        "frame_num": frame_num,
                        "timestamp_sec": timestamp_sec,
                        "confidence": result['top_threat_score'],
                        "threat_type": result['top_threat'],
                        "label": result['label'],
                        "threat_scores": result['threat_scores'],
                        "snapshot_b64": snapshot_b64,
                        "detected_at": datetime.now(timezone.utc).isoformat()
                    }
                    detections.append(detection)

                    if not recording:
                        recording = True
                        record_frames = []

                if progress_callback and analysed % 5 == 0:
                    progress_callback({
                        "progress": round(frame_num / max(total_frames, 1) * 100, 1),
                        "analysed": analysed,
                        "detections_so_far": len(detections)
                    })

            if recording:
                record_frames.append(frame)
                if len(record_frames) > int(fps * 10):
                    recording = False

            frame_num += 1
    finally:
        cap.release()

    clip_path = None
    if record_frames and len(record_frames) > 10:
        clip_path = os.path.join('evidence', f'threat_{uuid.uuid4().hex[:8]}.mp4')
        os.makedirs('evidence', exist_ok=True)
        h, w = record_frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(clip_path, fourcc, fps, (w, h))
        for f in record_frames:
            writer.write(f)
        writer.release()
        print(f"[CCTV-AI] Saved threat clip: {clip_path}")

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
        return "No threats detected in the video feed. Scene appears safe."
    duration = round(total_frames / fps, 1)
    # Group by threat type
    types = {}
    for d in detections:
        t = d.get('threat_type', 'unknown')
        types[t] = types.get(t, 0) + 1
    type_str = ", ".join(f"{k.replace('_',' ')}: {v}" for k, v in types.items())
    first = detections[0]
    avg_conf = round(sum(d['confidence'] for d in detections) / len(detections), 2)
    return (
        f"⚠️ {len(detections)} threat(s) detected over {duration}s video. "
        f"Types: {type_str}. "
        f"First at {first['timestamp_sec']}s ({first['label']}, {first['confidence']*100:.0f}%). "
        f"Avg confidence: {avg_conf*100:.0f}%."
    )
