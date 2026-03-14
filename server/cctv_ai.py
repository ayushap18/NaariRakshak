"""
CCTV AI Threat Detection Module for NaariRakshak
=================================================
Uses OpenAI CLIP zero-shot with prompt ensembling + YOLOv8 person gating
for multi-category threat detection.

Accuracy pipeline (cascaded, cheapest-first):
  1. YOLOv8-nano person gate — skip CLIP entirely if 0 people detected
  2. Farneback optical flow motion analysis — chaos scoring
  3. Prompt ensembling — 7 domain-specific templates per category, averaged
  4. Binary violence pre-classifier — 2-class "violent vs peaceful" independent check
  5. Temperature-calibrated softmax — TEMPERATURE=1.5 on top of CLIP logit_scale
  6. Motion modulation — boost/dampen based on optical flow
  7. Temporal analysis buffer — 3/4 frame voting window
  8. Fine-tuned classifier head support — optional learned MLP on CLIP embeddings

Model: openai/clip-vit-base-patch32 (ViT-B/32, stable and fast)
Person gate: YOLOv8n (6MB, ~40ms/frame at 320px)
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import io
import time
import uuid
import base64
import threading
import collections
import itertools
from datetime import datetime, timezone

import torch

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

# ─── YOLO person detection state ───
_yolo_model = None
_yolo_lock = threading.Lock()

MODEL_ID = "openai/clip-vit-base-patch32"
THREAT_THRESHOLD = 0.35  # threat score above this = alert
FRAME_SAMPLE_INTERVAL = 15

# ─── Confidence calibration ───
# CLIP logit_scale = 100.0 internally. TEMPERATURE divides the scaled logits.
# 1.5 balances between sharp (1.0) and too soft (2.0).
TEMPERATURE = 1.5

# ─── Temporal analysis buffer ───
_frame_history = collections.deque(maxlen=4)
_TEMPORAL_WINDOW = 4
_TEMPORAL_MIN_DETECTIONS = 3  # 3 out of 4 frames must agree
_analysis_lock = threading.Lock()

# ─── Motion analysis state (Farneback optical flow) ───
_prev_gray = None

# ─── Fine-tuned classifier head ───
_finetuned_model = None
FINETUNED_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'violence_classifier.pt')

# ─── Safety threat labels — rich, mutually exclusive descriptions ───
THREAT_LABELS = {
    "violence": "two or more people fighting, punching, kicking, slapping each other, a physical brawl between multiple people",
    "harassment": "a man aggressively grabbing or groping a woman in public, unwanted forceful physical contact between people",
    "stalking": "a person secretly following another person on a street at night, creeping behind a walking woman",
    "weapon_threat": "a person pointing a knife or gun at another person, armed robbery at gunpoint",
    "distress": "a woman screaming while being physically attacked or dragged by another person",
    "robbery": "someone violently snatching a purse from another person, two people struggling over a bag",
    "abduction": "a person being forcefully dragged into a vehicle by others, multiple people kidnapping someone",
    "mob_attack": "a group of people surrounding and beating one person, mob violence, gang assault",
}

SAFE_LABELS = {
    "normal_activity": "people walking calmly on a sidewalk at a normal pace, relaxed body language, no physical contact between strangers",
    "empty_scene": "an empty room, empty hallway, empty street with no people visible",
    "indoor_normal": "a normal quiet indoor scene like an office, living room, classroom, or shop",
    "person_at_desk": "a single person sitting at a desk or computer, someone working on a laptop, webcam selfie, video call",
    "single_person": "one person alone standing or sitting peacefully, no other people nearby, calm relaxed posture, looking at phone",
    "outdoor_normal": "a peaceful outdoor scene, park bench, garden, quiet parking lot, playground",
    "sitting_relaxing": "people sitting peacefully, friends having a calm conversation, reading, eating together at a table",
    "group_socializing": "a group of friends talking and laughing together, people socializing at a cafe or party",
    "exercising": "a person exercising, stretching, doing yoga or fitness training, jogging alone",
    "greeting": "two friends hugging or greeting each other warmly, a friendly handshake between people",
}

# ─── Prompt ensembling templates ───
# Each template wraps a core category description for diversity.
# Averaging across templates is proven to boost CLIP zero-shot accuracy.
PROMPT_TEMPLATES = [
    "a photo of {}",
    "a surveillance camera image showing {}",
    "a CCTV footage frame of {}",
    "a security camera photo of {}",
    "a video frame depicting {}",
    "a nighttime security camera recording of {}",
    "a street camera view of {}",
]

# ─── Pre-computed ensembled text embeddings (populated on model load) ───
_ensembled_text_features = None  # shape: (num_categories, embedding_dim)
_all_keys = list(THREAT_LABELS.keys()) + list(SAFE_LABELS.keys())

# ─── Binary violence pre-classifier embeddings ───
_binary_text_features = None  # shape: (2, embedding_dim) — [violent, peaceful]
BINARY_LABELS = [
    "a violent dangerous scene with people fighting, attacking, or struggling",
    "a safe calm peaceful scene with no conflict or danger",
]
BINARY_THREAT_THRESHOLD = 0.55  # binary "violent" probability above this = threat signal


# ═══════════════════════════════════════════════════════
# YOLO PERSON GATE — skip CLIP if <2 people detected
# ═══════════════════════════════════════════════════════

def _load_yolo():
    """Lazy-load YOLOv8-nano for person detection (~6MB, very fast)."""
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    with _yolo_lock:
        if _yolo_model is not None:
            return _yolo_model
        try:
            from ultralytics import YOLO
            print("[CCTV-AI] Loading YOLOv8-nano for person detection...", flush=True)
            _yolo_model = YOLO("yolov8n.pt")
            print("[CCTV-AI] YOLOv8-nano loaded.", flush=True)
            return _yolo_model
        except Exception as e:
            print(f"[CCTV-AI] YOLO load failed (will skip person gate): {e}")
            return None


def detect_persons(frame_bgr, conf_threshold=0.35):
    """
    Detect persons in frame using YOLOv8-nano.
    Returns (person_count, list_of_center_points, list_of_boxes).
    """
    model = _load_yolo()
    if model is None:
        return -1, [], []  # -1 means YOLO unavailable, skip gating

    try:
        results = model.predict(
            frame_bgr,
            classes=[0],      # COCO class 0 = person
            conf=conf_threshold,
            imgsz=320,        # small input = fast (~40ms CPU)
            verbose=False
        )
        boxes = results[0].boxes
        centers = []
        box_list = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            centers.append(((x1 + x2) / 2, (y1 + y2) / 2))
            box_list.append((x1, y1, x2, y2))
        return len(boxes), centers, box_list
    except Exception as e:
        print(f"[CCTV-AI] YOLO inference error: {e}")
        return -1, [], []


def check_proximity(centers, frame_width, proximity_ratio=0.3):
    """Check if any two detected people are close enough for interaction."""
    if len(centers) < 2:
        return False
    threshold = frame_width * proximity_ratio
    for c1, c2 in itertools.combinations(centers, 2):
        dist = ((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2) ** 0.5
        if dist < threshold:
            return True
    return False


def _extract_features(model_output):
    """
    Extract raw feature tensor from CLIP model output.
    Handles both old transformers (returns Tensor) and v5+ (returns BaseModelOutputWithPooling).
    """
    if isinstance(model_output, torch.Tensor):
        return model_output
    if hasattr(model_output, 'pooler_output') and model_output.pooler_output is not None:
        return model_output.pooler_output
    if hasattr(model_output, 'last_hidden_state'):
        return model_output.last_hidden_state[:, 0, :]  # CLS token
    # Fallback: try indexing
    return model_output[0] if hasattr(model_output, '__getitem__') else model_output


def _encode_single_text(text):
    """Encode a single text prompt. Processing one at a time avoids batch segfaults."""
    inputs = _clip_processor(text=[text], return_tensors="pt", padding=True)
    with torch.no_grad():
        raw_output = _clip_model.get_text_features(**inputs)
        embedding = _extract_features(raw_output)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding[0]  # remove batch dim


def _compute_ensembled_text_features():
    """
    Compute ensembled text embeddings for all categories.
    For each category, encode each prompt template individually,
    average the L2-normalized embeddings, then re-normalize.
    """
    global _ensembled_text_features

    all_descriptions = list(THREAT_LABELS.values()) + list(SAFE_LABELS.values())
    category_embeddings = []

    for i, desc in enumerate(all_descriptions):
        template_embeddings = []
        for template in PROMPT_TEMPLATES:
            prompt = template.format(desc)
            emb = _encode_single_text(prompt)
            template_embeddings.append(emb)
        stacked = torch.stack(template_embeddings, dim=0)
        mean_embedding = stacked.mean(dim=0)
        mean_embedding = mean_embedding / mean_embedding.norm()
        category_embeddings.append(mean_embedding)
        print(f"[CCTV-AI]   text embedding {i+1}/{len(all_descriptions)}", flush=True)

    _ensembled_text_features = torch.stack(category_embeddings, dim=0)


def _compute_binary_text_features():
    """
    Compute text embeddings for binary violence classifier.
    Just 2 labels: violent vs peaceful. Uses same prompt ensembling.
    """
    global _binary_text_features

    category_embeddings = []
    for desc in BINARY_LABELS:
        template_embeddings = []
        for template in PROMPT_TEMPLATES:
            prompt = template.format(desc)
            emb = _encode_single_text(prompt)
            template_embeddings.append(emb)
        stacked = torch.stack(template_embeddings, dim=0)
        mean_embedding = stacked.mean(dim=0)
        mean_embedding = mean_embedding / mean_embedding.norm()
        category_embeddings.append(mean_embedding)

    _binary_text_features = torch.stack(category_embeddings, dim=0)


class ViolenceClassifier(torch.nn.Module):
    """Two-layer MLP on top of 512-dim CLIP embeddings. Must match train_violence_classifier.py."""
    def __init__(self, input_dim=512):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_dim, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.3),
            torch.nn.Linear(256, 64),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.2),
            torch.nn.Linear(64, 1),
            torch.nn.Sigmoid(),
        )
    def forward(self, x):
        return self.net(x)


def _load_finetuned():
    """
    Load a fine-tuned classifier head if available.
    The classifier should take CLIP image embeddings as input and output
    a single violence probability (sigmoid output).
    """
    global _finetuned_model
    if os.path.exists(FINETUNED_MODEL_PATH):
        try:
            _finetuned_model = ViolenceClassifier()
            _finetuned_model.load_state_dict(
                torch.load(FINETUNED_MODEL_PATH, map_location='cpu', weights_only=True)
            )
            _finetuned_model.eval()
            print(f"[CCTV-AI] Fine-tuned classifier loaded from {FINETUNED_MODEL_PATH}")
            return True
        except Exception as e:
            print(f"[CCTV-AI] Failed to load fine-tuned model: {e}")
            _finetuned_model = None
            return False
    return False


def _load_model():
    """Lazy-load the CLIP zero-shot model and pre-compute ensembled text embeddings."""
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

            # Pre-compute ensembled text features for all categories
            print("[CCTV-AI] Computing ensembled text embeddings...", flush=True)
            _compute_ensembled_text_features()
            _compute_binary_text_features()
            print("[CCTV-AI] Binary violence pre-classifier ready.", flush=True)

            # Attempt to load fine-tuned classifier head
            _load_finetuned()

            print(
                f"[CCTV-AI] CLIP model loaded. "
                f"{len(THREAT_LABELS)} threat + {len(SAFE_LABELS)} safe categories, "
                f"{len(PROMPT_TEMPLATES)} prompt templates each."
            )
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


def compute_motion_score(frame_gray):
    """
    Compute motion intensity using Farneback dense optical flow.
    Returns (motion_score, chaos_score) — both 0.0 to ~1.0.

    motion_score: overall motion magnitude (high = lots of movement)
    chaos_score: motion variance / mean (high = chaotic/fight-like, low = uniform/walking)

    Thread-safe: protects global _prev_gray with _analysis_lock.
    """
    global _prev_gray
    with _analysis_lock:
        if _prev_gray is None:
            _prev_gray = frame_gray.copy()
            return 0.0, 0.0
        prev = _prev_gray
        _prev_gray = frame_gray.copy()

    try:
        flow = cv2.calcOpticalFlowFarneback(
            prev, frame_gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        mean_mag = float(np.mean(mag))
        std_mag = float(np.std(mag))
        chaos = std_mag / (mean_mag + 1e-6)
        # Normalize motion to 0-1 range (3.0+ px/frame = high motion)
        motion_score = min(mean_mag / 3.0, 1.0)
        # Normalize chaos to 0-1 range (2.0+ = chaotic)
        chaos_score = min(chaos / 2.0, 1.0)
        return float(motion_score), float(chaos_score)
    except Exception:
        # Fallback to simple frame diff if optical flow fails
        diff = cv2.absdiff(prev, frame_gray)
        motion = float(np.mean(diff) / 255.0)
        return motion, 0.0


def _center_crop(image, crop_ratio=0.7):
    """
    Return a center-cropped version of a PIL Image.
    Focuses on the action area (center of frame) which often contains the subject.
    """
    w, h = image.size
    new_w, new_h = int(w * crop_ratio), int(h * crop_ratio)
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    return image.crop((left, top, left + new_w, top + new_h))


def _compute_clip_scores(image):
    """
    Compute category scores for a single PIL Image using ensembled text embeddings.
    Uses temperature-scaled cosine similarity for sharper predictions.
    Returns a dict mapping category key -> probability.
    """
    # Get image embedding
    inputs = _clip_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        raw_output = _clip_model.get_image_features(**inputs)
        image_features = _extract_features(raw_output)
        # L2 normalize
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        # Cosine similarity with ensembled text features, scaled by CLIP's logit_scale
        logit_scale = _clip_model.logit_scale.exp()
        logits = (image_features @ _ensembled_text_features.T) * logit_scale
        logits = logits[0]  # remove batch dim

        # Temperature scaling for confidence calibration
        probs = (logits / TEMPERATURE).softmax(dim=-1)

    scores = {}
    for i, key in enumerate(_all_keys):
        scores[key] = round(probs[i].item(), 4)

    return scores


def _compute_binary_score(image):
    """
    Binary violence pre-classifier: "violent" vs "peaceful".
    With only 2 classes, softmax is much more decisive than with 18 classes.
    Returns the probability of the "violent" class (0.0-1.0).
    """
    if _binary_text_features is None:
        return None

    inputs = _clip_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        raw_output = _clip_model.get_image_features(**inputs)
        image_features = _extract_features(raw_output)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        logit_scale = _clip_model.logit_scale.exp()
        logits = (image_features @ _binary_text_features.T) * logit_scale
        logits = logits[0]
        probs = (logits / TEMPERATURE).softmax(dim=-1)

    return round(probs[0].item(), 4)  # index 0 = violent


def _get_finetuned_score(image):
    """
    Run the fine-tuned classifier on a PIL Image's CLIP embedding.
    Returns a float violence probability, or None if no fine-tuned model is available.
    """
    if _finetuned_model is None:
        return None

    try:
        inputs = _clip_processor(images=image, return_tensors="pt")
        with torch.no_grad():
            raw_output = _clip_model.get_image_features(**inputs)
            image_features = _extract_features(raw_output)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            output = _finetuned_model(image_features)
            # ViolenceClassifier already applies Sigmoid, so read output directly
            if output.dim() > 1:
                score = output[0, 0].item()
            else:
                score = output[0].item()
        return score
    except Exception as e:
        print(f"[CCTV-AI] Fine-tuned model inference error: {e}")
        return None


def analyse_frame(image_bytes: bytes, raw_frame_bgr=None) -> dict:
    """
    Analyse a single frame using cascaded detection pipeline:
    1. YOLOv8 person gate (skip if <2 people)
    2. CLIP zero-shot with prompt ensembling
    3. Farneback optical flow motion analysis
    4. Optional fine-tuned classifier fusion

    Args:
        image_bytes: JPEG/PNG encoded image bytes
        raw_frame_bgr: Optional BGR numpy array for YOLO + motion analysis.
                       If not provided, will be decoded from image_bytes.

    Returns:
        dict with threat_detected, threat_score, safe_score, top_threat, label, etc.
    """
    if not _load_model():
        return {"error": "Model not available", "threat_detected": False, "threat_score": 0,
                "safe_score": 0, "top_threat": "none", "top_threat_score": 0,
                "label": "Model Loading", "threat_scores": {}, "safe_scores": {},
                "violence": False, "confidence": 0, "raw_scores": {},
                "person_count": 0}

    try:
        # ── Decode frame for YOLO + motion if not provided ──
        if raw_frame_bgr is None:
            nparr = np.frombuffer(image_bytes, np.uint8)
            raw_frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        frame_gray = cv2.cvtColor(raw_frame_bgr, cv2.COLOR_BGR2GRAY)
        frame_h, frame_w = raw_frame_bgr.shape[:2]

        # ══════════════════════════════════════════
        # STAGE 1: YOLO person gate (cheapest first)
        # ══════════════════════════════════════════
        person_count, centers, boxes = detect_persons(raw_frame_bgr)
        people_close = check_proximity(centers, frame_w) if person_count >= 2 else False

        # If YOLO is available and NO people at all, skip expensive CLIP
        if person_count == 0:
            motion_score, chaos_score = compute_motion_score(frame_gray)
            return {
                "threat_detected": False,
                "threat_score": 0, "safe_score": 1.0,
                "top_threat": "none", "top_threat_score": 0,
                "label": "Empty Scene",
                "threat_scores": {k: 0.0 for k in THREAT_LABELS},
                "safe_scores": {k: 0.1 for k in SAFE_LABELS},
                "threshold": THREAT_THRESHOLD,
                "violence": False, "confidence": 0,
                "raw_scores": {},
                "person_count": 0,
                "motion_score": round(motion_score, 4),
                "chaos_score": round(chaos_score, 4),
                "yolo_gated": True,
            }

        # ══════════════════════════════════════════
        # STAGE 2: Motion analysis (Farneback optical flow)
        # ══════════════════════════════════════════
        motion_score, chaos_score = compute_motion_score(frame_gray)

        # ══════════════════════════════════════════
        # STAGE 3: CLIP zero-shot classification
        # ══════════════════════════════════════════
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        scores = _compute_clip_scores(image)

        # ── Binary violence pre-classifier (independent 2-class check) ──
        binary_violence_score = _compute_binary_score(image)

        # Separate threat and safe scores
        threat_scores = {k: scores[k] for k in THREAT_LABELS}
        safe_scores = {k: scores[k] for k in SAFE_LABELS}
        max_threat_key = max(threat_scores, key=threat_scores.get)
        max_threat_score = threat_scores[max_threat_key]
        total_threat = sum(threat_scores.values())
        total_safe = sum(safe_scores.values())
        avg_threat = total_threat / len(THREAT_LABELS)
        avg_safe = total_safe / len(SAFE_LABELS)

        # ── Fine-tuned classifier fusion ──
        ft_score = _get_finetuned_score(image)
        if ft_score is not None:
            fused_threat_score = ft_score * 0.6 + max_threat_score * 0.4
            max_threat_score = round(fused_threat_score, 4)
            threat_scores[max_threat_key] = max_threat_score
            total_threat = sum(threat_scores.values())
            avg_threat = total_threat / len(THREAT_LABELS)

        # ══════════════════════════════════════════
        # STAGE 4: Motion modulation
        # ══════════════════════════════════════════
        if motion_score > 0.3 and chaos_score > 0.5:
            # High chaotic motion — boost threat
            max_threat_score = min(1.0, max_threat_score * 1.25)
        elif motion_score > 0.15 and chaos_score > 0.3:
            # Moderate chaotic motion — slight boost
            max_threat_score = min(1.0, max_threat_score * 1.1)
        # Only dampen when truly zero motion (empty scene, statue)
        elif motion_score < 0.02 and max_threat_score > 0:
            max_threat_score = max_threat_score * 0.7
        threat_scores[max_threat_key] = round(max_threat_score, 4)

        # ══════════════════════════════════════════
        # STAGE 5: Threat decision — binary + multi-class fusion
        # ══════════════════════════════════════════
        # Either the binary classifier says "violent" OR the multi-class
        # max threat exceeds threshold. Both are valid signals.
        binary_positive = (binary_violence_score is not None
                           and binary_violence_score >= BINARY_THREAT_THRESHOLD)
        multiclass_positive = max_threat_score >= THREAT_THRESHOLD

        threat_detected = binary_positive or multiclass_positive

        # If binary says violent, boost the max threat score for UI display
        if binary_positive and not multiclass_positive:
            max_threat_score = max(max_threat_score, binary_violence_score * 0.8)
            threat_scores[max_threat_key] = round(max_threat_score, 4)

        # Build readable label
        if threat_detected:
            label = max_threat_key.replace("_", " ").title()
        else:
            max_safe_key = max(safe_scores, key=safe_scores.get)
            label = max_safe_key.replace("_", " ").title()

        result = {
            "threat_detected": threat_detected,
            "threat_score": round(total_threat, 4),
            "safe_score": round(total_safe, 4),
            "top_threat": max_threat_key,
            "top_threat_score": round(max_threat_score, 4),
            "label": label,
            "threat_scores": threat_scores,
            "safe_scores": safe_scores,
            "threshold": THREAT_THRESHOLD,
            "violence": threat_detected,
            "confidence": round(max_threat_score, 4),
            "raw_scores": scores,
            "person_count": person_count,
            "motion_score": round(motion_score, 4),
            "chaos_score": round(chaos_score, 4),
            "people_close": people_close,
            "binary_violence_score": binary_violence_score,
        }
        return result

    except Exception as e:
        print(f"[CCTV-AI] Frame analysis error: {e}")
        return {"error": str(e), "threat_detected": False, "threat_score": 0,
                "safe_score": 0, "top_threat": "none", "top_threat_score": 0,
                "label": "Error", "threat_scores": {}, "safe_scores": {},
                "violence": False, "confidence": 0, "raw_scores": {},
                "person_count": -1}


def analyse_frame_temporal(image_bytes: bytes, raw_frame_bgr=None) -> dict:
    """
    Analyse a frame with temporal smoothing to reduce single-frame false positives.

    Wraps analyse_frame and maintains a sliding window of recent results.
    Only reports a threat if at least _TEMPORAL_MIN_DETECTIONS out of the
    last _TEMPORAL_WINDOW frames detected a threat.

    Args:
        image_bytes: JPEG/PNG encoded image bytes
        raw_frame_bgr: Optional BGR numpy array for YOLO + motion analysis

    Returns:
        Same dict format as analyse_frame, with temporal smoothing applied.
    """
    result = analyse_frame(image_bytes, raw_frame_bgr=raw_frame_bgr)

    if "error" in result:
        return result

    raw_detection = result["threat_detected"]

    # Update sliding window (thread-safe: deque.append is atomic, lock for iteration)
    _frame_history.append(raw_detection)

    with _analysis_lock:
        # Count positives in the window
        positives = sum(1 for d in _frame_history if d)
    temporally_confirmed = positives >= _TEMPORAL_MIN_DETECTIONS

    # Override threat_detected with temporal result
    result["temporal_raw_detection"] = raw_detection
    result["threat_detected"] = temporally_confirmed
    result["violence"] = temporally_confirmed  # backward compat

    # If temporally suppressed, update label to safe
    if not temporally_confirmed and raw_detection:
        safe_scores = result.get("safe_scores", {})
        if safe_scores:
            max_safe_key = max(safe_scores, key=safe_scores.get)
            result["label"] = max_safe_key.replace("_", " ").title()

    return result


def analyse_video(video_path: str, progress_callback=None) -> dict:
    """
    Analyse a video file frame-by-frame for threats.

    Uses multi-crop analysis (full frame + center crop) for each sampled frame,
    averaging scores for better accuracy. Also incorporates motion analysis
    via frame differencing between sampled frames.
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
    record_frames = []
    prev_gray_video = None  # local motion state for video (not global)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_num % FRAME_SAMPLE_INTERVAL == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                pil_img = Image.fromarray(rgb)

                # ── YOLO person gate for video ──
                person_count, centers, boxes = detect_persons(frame)
                frame_h, frame_w = frame.shape[:2]
                people_close = check_proximity(centers, frame_w) if person_count >= 2 else False

                if person_count == 0:
                    # Skip this frame — no people visible
                    prev_gray_video = gray.copy()
                    frame_num += 1
                    analysed += 1
                    continue

                # ── Full-frame scores ──
                full_scores = _compute_clip_scores(pil_img)

                # ── Center-crop scores ──
                cropped_img = _center_crop(pil_img, crop_ratio=0.7)
                crop_scores = _compute_clip_scores(cropped_img)

                # ── Average full + crop scores ──
                scores = {}
                for key in _all_keys:
                    scores[key] = round((full_scores[key] + crop_scores[key]) / 2.0, 4)

                # ── Motion analysis (Farneback optical flow, local to video) ──
                motion = 0.0
                chaos = 0.0
                if prev_gray_video is not None:
                    try:
                        flow = cv2.calcOpticalFlowFarneback(
                            prev_gray_video, gray, None,
                            pyr_scale=0.5, levels=3, winsize=15,
                            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                        )
                        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                        mean_mag = float(np.mean(mag))
                        std_mag = float(np.std(mag))
                        motion = min(mean_mag / 3.0, 1.0)
                        chaos = min(std_mag / (mean_mag + 1e-6) / 2.0, 1.0)
                    except Exception:
                        diff = cv2.absdiff(prev_gray_video, gray)
                        motion = float(np.mean(diff) / 255.0)
                prev_gray_video = gray.copy()

                # ── Threat detection logic ──
                threat_scores = {k: scores[k] for k in THREAT_LABELS}
                safe_scores = {k: scores[k] for k in SAFE_LABELS}
                max_threat_key = max(threat_scores, key=threat_scores.get)
                max_threat_score = threat_scores[max_threat_key]
                total_threat = sum(threat_scores.values())
                total_safe = sum(safe_scores.values())
                avg_threat = total_threat / len(THREAT_LABELS)
                avg_safe = total_safe / len(SAFE_LABELS)

                # Fine-tuned classifier fusion (if available)
                ft_score = _get_finetuned_score(pil_img)
                if ft_score is not None:
                    max_threat_score = ft_score * 0.6 + max_threat_score * 0.4
                    threat_scores[max_threat_key] = round(max_threat_score, 4)
                    total_threat = sum(threat_scores.values())
                    avg_threat = total_threat / len(THREAT_LABELS)

                # Motion modulation
                if motion > 0.3 and chaos > 0.5:
                    max_threat_score = min(1.0, max_threat_score * 1.25)
                elif motion > 0.15 and chaos > 0.3:
                    max_threat_score = min(1.0, max_threat_score * 1.1)
                elif motion < 0.02 and max_threat_score > 0:
                    max_threat_score = max_threat_score * 0.7

                # Binary violence pre-classifier for video
                binary_violence_score = _compute_binary_score(pil_img)
                binary_positive = (binary_violence_score is not None
                                   and binary_violence_score >= BINARY_THREAT_THRESHOLD)
                multiclass_positive = max_threat_score >= THREAT_THRESHOLD
                threat_detected = binary_positive or multiclass_positive

                if binary_positive and not multiclass_positive:
                    max_threat_score = max(max_threat_score, binary_violence_score * 0.8)

                analysed += 1

                if threat_detected:
                    timestamp_sec = round(frame_num / fps, 2)
                    # Preserve aspect ratio for thumbnail (max width 320)
                    h_orig, w_orig = frame.shape[:2]
                    thumb_w = 320
                    thumb_h = int(h_orig * thumb_w / max(w_orig, 1))
                    thumb = cv2.resize(frame, (thumb_w, thumb_h))
                    _, thumb_enc = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    snapshot_b64 = base64.b64encode(thumb_enc).decode('utf-8')

                    label = max_threat_key.replace("_", " ").title()

                    detection = {
                        "frame_num": frame_num,
                        "timestamp_sec": timestamp_sec,
                        "confidence": round(max_threat_score, 4),
                        "threat_type": max_threat_key,
                        "label": label,
                        "threat_scores": dict(threat_scores),
                        "snapshot_b64": snapshot_b64,
                        "motion_score": round(motion, 4),
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
                # Cap at 10 seconds of frames to limit memory usage
                max_record_frames = int(fps * 10)
                if len(record_frames) > max_record_frames:
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
    """Build a human-readable summary of video analysis results."""
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
