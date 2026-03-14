#!/usr/bin/env python3
"""
NaariRakshak — Violence Classifier Training Pipeline
=====================================================

Fine-tunes a lightweight MLP classifier head on top of frozen CLIP embeddings
(openai/clip-vit-base-patch32) for binary violence detection.

Datasets
--------
This script is designed for two popular Kaggle datasets:

1. Real Life Violence Situations Dataset (RLVS)
   https://www.kaggle.com/datasets/mohamedmustafa/real-life-violence-situations-dataset
   Structure after download & extraction:
       data/
         Violence/        ← video files (.avi/.mp4) showing violent scenes
         NonViolence/     ← video files showing non-violent scenes

2. UCF Crime Dataset (optional, supplementary)
   https://www.kaggle.com/datasets/odins0n/ucf-crime-dataset
   Place "Fighting" / "Assault" clips in Violence/, other clips in NonViolence/.

You can also point the script at pre-extracted frame images:
       data/
         Violence/        ← .jpg/.png frame images
         NonViolence/     ← .jpg/.png frame images

How to run
----------
    # Basic usage — videos in RLVS format
    python train_violence_classifier.py --data_dir ./data

    # Full options
    python train_violence_classifier.py \\
        --data_dir ./data \\
        --epochs 30 \\
        --batch_size 64 \\
        --frames_per_video 10 \\
        --lr 1e-3 \\
        --patience 5 \\
        --cache_dir ./embedding_cache \\
        --output_dir ./models

Output
------
- Best model weights:   server/models/violence_classifier.pt
- Training history plot: server/models/training_history.png

The saved model is loaded in cctv_ai.py like:
    model = ViolenceClassifier()
    model.load_state_dict(torch.load("server/models/violence_classifier.pt"))
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
from PIL import Image

# ---------------------------------------------------------------------------
# Classifier architecture — must match what cctv_ai.py expects
# ---------------------------------------------------------------------------

class ViolenceClassifier(nn.Module):
    """Two-layer MLP on top of 512-dim CLIP embeddings."""

    def __init__(self, input_dim=512):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------------------
# CLIP embedding extraction
# ---------------------------------------------------------------------------

def load_clip(device: str):
    """Load the CLIP model and processor (frozen, eval-only)."""
    from transformers import CLIPModel, CLIPProcessor

    model_id = "openai/clip-vit-base-patch32"
    print(f"[train] Loading CLIP model: {model_id} ...")
    processor = CLIPProcessor.from_pretrained(model_id, use_fast=False)
    model = CLIPModel.from_pretrained(model_id).to(device)
    model.eval()
    print("[train] CLIP model loaded.")
    return model, processor


def extract_frames_from_video(video_path: str, frames_per_video: int) -> list:
    """
    Extract ``frames_per_video`` evenly-spaced frames from a video file.
    Returns a list of PIL Images.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[train] WARNING: cannot open video {video_path}")
        return []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []

    indices = np.linspace(0, total - 1, frames_per_video, dtype=int)
    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(rgb))
    cap.release()
    return frames


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".mp4", ".mkv", ".mov", ".wmv", ".mpg", ".mpeg"}


def discover_samples(data_dir: str, frames_per_video: int):
    """
    Walk the data directory and return (images_or_paths, labels).

    Supports two layouts:
      - Video files in Violence/ and NonViolence/ subdirectories.
      - Pre-extracted frame images in the same directory structure.

    Returns:
        samples: list of (PIL.Image or image_path_str, label_int)
    """
    data_path = Path(data_dir)

    violence_dir = None
    nonviolence_dir = None

    # Try case-insensitive matching for directory names
    for d in data_path.iterdir():
        if not d.is_dir():
            continue
        name_lower = d.name.lower()
        if name_lower in ("violence", "violent", "fight", "fighting"):
            violence_dir = d
        elif name_lower in ("nonviolence", "non-violence", "nonviolent", "non_violence", "normal"):
            nonviolence_dir = d

    if violence_dir is None or nonviolence_dir is None:
        print(f"[train] ERROR: Expected subdirectories 'Violence/' and 'NonViolence/' inside {data_dir}")
        print(f"[train] Found directories: {[d.name for d in data_path.iterdir() if d.is_dir()]}")
        sys.exit(1)

    print(f"[train] Violence dir : {violence_dir}")
    print(f"[train] NonViolence dir: {nonviolence_dir}")

    samples = []  # list of (path_or_pil, label)

    for label, folder in [(1, violence_dir), (0, nonviolence_dir)]:
        files = sorted(folder.iterdir())
        videos = [f for f in files if f.suffix.lower() in VIDEO_EXTENSIONS]
        images = [f for f in files if f.suffix.lower() in IMAGE_EXTENSIONS]

        if videos:
            print(f"[train]   {folder.name}: {len(videos)} videos (extracting {frames_per_video} frames each)")
            for v in videos:
                pil_frames = extract_frames_from_video(str(v), frames_per_video)
                for img in pil_frames:
                    samples.append((img, label))
        elif images:
            print(f"[train]   {folder.name}: {len(images)} images")
            for img_path in images:
                samples.append((str(img_path), label))
        else:
            # Check subdirectories (e.g., Violence/V_1/, Violence/V_2/, ...)
            sub_videos = []
            sub_images = []
            for sub in sorted(folder.rglob("*")):
                if sub.is_file():
                    if sub.suffix.lower() in VIDEO_EXTENSIONS:
                        sub_videos.append(sub)
                    elif sub.suffix.lower() in IMAGE_EXTENSIONS:
                        sub_images.append(sub)

            if sub_videos:
                print(f"[train]   {folder.name}: {len(sub_videos)} videos in subdirs")
                for v in sub_videos:
                    pil_frames = extract_frames_from_video(str(v), frames_per_video)
                    for img in pil_frames:
                        samples.append((img, label))
            elif sub_images:
                print(f"[train]   {folder.name}: {len(sub_images)} images in subdirs")
                for img_path in sub_images:
                    samples.append((str(img_path), label))
            else:
                print(f"[train] WARNING: no videos or images found in {folder}")

    print(f"[train] Total samples discovered: {len(samples)}")
    label_counts = defaultdict(int)
    for _, lbl in samples:
        label_counts[lbl] += 1
    print(f"[train]   Violence (1): {label_counts[1]}  |  NonViolence (0): {label_counts[0]}")
    return samples


def compute_cache_key(data_dir: str, frames_per_video: int) -> str:
    """Deterministic hash so we can cache embeddings for a given dataset config."""
    key_str = f"{os.path.abspath(data_dir)}|fpv={frames_per_video}"
    return hashlib.md5(key_str.encode()).hexdigest()[:12]


@torch.no_grad()
def extract_embeddings(samples, clip_model, clip_processor, device, batch_size, cache_dir):
    """
    Extract CLIP image embeddings for all samples.
    Caches to disk as .npz so subsequent runs skip extraction.

    Returns:
        embeddings: np.ndarray of shape (N, 512)
        labels: np.ndarray of shape (N,)
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    # Check cache
    cache_file = cache_path / "embeddings.npz"
    meta_file = cache_path / "meta.json"
    if cache_file.exists() and meta_file.exists():
        meta = json.loads(meta_file.read_text())
        if meta.get("num_samples") == len(samples):
            print(f"[train] Loading cached embeddings from {cache_file} ({meta['num_samples']} samples)")
            data = np.load(cache_file)
            return data["embeddings"], data["labels"]

    print(f"[train] Extracting CLIP embeddings for {len(samples)} samples (batch_size={batch_size}) ...")

    all_embeddings = []
    all_labels = []

    # Process in batches
    for start in range(0, len(samples), batch_size):
        end = min(start + batch_size, len(samples))
        batch = samples[start:end]

        pil_images = []
        labels = []
        for item, label in batch:
            if isinstance(item, str):
                try:
                    img = Image.open(item).convert("RGB")
                except Exception as e:
                    print(f"[train] WARNING: cannot open {item}: {e}")
                    continue
            else:
                img = item.convert("RGB") if item.mode != "RGB" else item
            pil_images.append(img)
            labels.append(label)

        if not pil_images:
            continue

        inputs = clip_processor(images=pil_images, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        raw_output = clip_model.get_image_features(**inputs)  # (B, 512)
        # Handle transformers v5+ returning BaseModelOutputWithPooling
        if isinstance(raw_output, torch.Tensor):
            outputs = raw_output
        elif hasattr(raw_output, 'pooler_output') and raw_output.pooler_output is not None:
            outputs = raw_output.pooler_output
        else:
            outputs = raw_output[0]
        # L2 normalize (same as CLIP default)
        outputs = outputs / outputs.norm(dim=-1, keepdim=True)

        all_embeddings.append(outputs.cpu().numpy())
        all_labels.extend(labels)

        done = min(end, len(samples))
        if done % (batch_size * 10) == 0 or done == len(samples):
            print(f"[train]   {done}/{len(samples)} samples embedded")

    embeddings = np.concatenate(all_embeddings, axis=0)
    labels = np.array(all_labels, dtype=np.float32)

    # Save cache
    np.savez(cache_file, embeddings=embeddings, labels=labels)
    meta_file.write_text(json.dumps({"num_samples": len(labels)}))
    print(f"[train] Cached embeddings to {cache_file}")

    return embeddings, labels


# ---------------------------------------------------------------------------
# Dataset for the MLP
# ---------------------------------------------------------------------------

class EmbeddingDataset(Dataset):
    def __init__(self, embeddings: np.ndarray, labels: np.ndarray):
        self.embeddings = torch.tensor(embeddings, dtype=torch.float32)
        self.labels = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.embeddings[idx], self.labels[idx]


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def compute_metrics(preds: np.ndarray, targets: np.ndarray, threshold=0.5):
    """Compute accuracy, precision, recall, F1 from raw probabilities."""
    binary = (preds >= threshold).astype(np.float32)
    tp = ((binary == 1) & (targets == 1)).sum()
    fp = ((binary == 1) & (targets == 0)).sum()
    fn = ((binary == 0) & (targets == 1)).sum()
    tn = ((binary == 0) & (targets == 0)).sum()

    accuracy = (tp + tn) / (tp + tn + fp + fn + 1e-8)
    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    f1 = 2 * precision * recall / (precision + recall + 1e-8)

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


def print_confusion_matrix(metrics: dict):
    tp, fp, fn, tn = metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]
    print("\n  Confusion Matrix")
    print("  " + "-" * 35)
    print(f"  {'':15s} {'Pred Violence':>14s} {'Pred Safe':>10s}")
    print(f"  {'True Violence':15s} {tp:>14d} {fn:>10d}")
    print(f"  {'True Safe':15s} {fp:>14d} {tn:>10d}")
    print("  " + "-" * 35)


def print_class_report(metrics: dict):
    print("\n  Per-Class Metrics")
    print("  " + "-" * 50)
    print(f"  {'Class':15s} {'Precision':>10s} {'Recall':>10s} {'F1':>10s}")
    print(f"  {'Violence':15s} {metrics['precision']:>10.4f} {metrics['recall']:>10.4f} {metrics['f1']:>10.4f}")
    # Compute safe-class metrics
    tp, fp, fn, tn = metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]
    safe_prec = tn / (tn + fn + 1e-8)
    safe_rec = tn / (tn + fp + 1e-8)
    safe_f1 = 2 * safe_prec * safe_rec / (safe_prec + safe_rec + 1e-8)
    print(f"  {'NonViolence':15s} {safe_prec:>10.4f} {safe_rec:>10.4f} {safe_f1:>10.4f}")
    print("  " + "-" * 50)
    print(f"  {'Overall Acc':15s} {metrics['accuracy']:>10.4f}")


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[train] Device: {device}")

    # 1. Discover samples
    samples = discover_samples(args.data_dir, args.frames_per_video)
    if len(samples) == 0:
        print("[train] No samples found. Exiting.")
        sys.exit(1)

    # 2. Extract CLIP embeddings
    cache_key = compute_cache_key(args.data_dir, args.frames_per_video)
    cache_dir = os.path.join(args.cache_dir, cache_key)
    clip_model, clip_processor = load_clip(device)
    embeddings, labels = extract_embeddings(
        samples, clip_model, clip_processor, device, args.batch_size, cache_dir
    )
    # Free CLIP from memory
    del clip_model, clip_processor
    if device == "cuda":
        torch.cuda.empty_cache()

    # 3. Build dataset & split
    dataset = EmbeddingDataset(embeddings, labels)
    val_size = int(0.2 * len(dataset))
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(
        dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )
    print(f"[train] Train: {train_size}  |  Val: {val_size}")

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    # 4. Model, loss, optimizer
    model = ViolenceClassifier(input_dim=embeddings.shape[1]).to(device)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    # 5. Training loop with early stopping
    best_val_f1 = 0.0
    best_epoch = 0
    patience_counter = 0
    history = {"train_loss": [], "val_loss": [], "val_acc": [], "val_f1": []}

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    best_model_path = output_dir / "violence_classifier.pt"

    print(f"\n[train] Starting training for {args.epochs} epochs (patience={args.patience})")
    print("=" * 80)

    for epoch in range(1, args.epochs + 1):
        # --- Train ---
        model.train()
        train_losses = []
        for emb_batch, lbl_batch in train_loader:
            emb_batch, lbl_batch = emb_batch.to(device), lbl_batch.to(device)
            optimizer.zero_grad()
            preds = model(emb_batch)
            loss = criterion(preds, lbl_batch)
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())
        avg_train_loss = np.mean(train_losses)

        # --- Validate ---
        model.eval()
        val_losses = []
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for emb_batch, lbl_batch in val_loader:
                emb_batch, lbl_batch = emb_batch.to(device), lbl_batch.to(device)
                preds = model(emb_batch)
                loss = criterion(preds, lbl_batch)
                val_losses.append(loss.item())
                all_preds.append(preds.cpu().numpy())
                all_targets.append(lbl_batch.cpu().numpy())

        avg_val_loss = np.mean(val_losses)
        all_preds = np.concatenate(all_preds)
        all_targets = np.concatenate(all_targets)
        metrics = compute_metrics(all_preds, all_targets)

        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)
        history["val_acc"].append(metrics["accuracy"])
        history["val_f1"].append(metrics["f1"])

        print(
            f"  Epoch {epoch:3d}/{args.epochs}  |  "
            f"train_loss={avg_train_loss:.4f}  val_loss={avg_val_loss:.4f}  |  "
            f"acc={metrics['accuracy']:.4f}  prec={metrics['precision']:.4f}  "
            f"rec={metrics['recall']:.4f}  F1={metrics['f1']:.4f}"
        )

        # Early stopping check
        if metrics["f1"] > best_val_f1:
            best_val_f1 = metrics["f1"]
            best_epoch = epoch
            patience_counter = 0
            torch.save(model.state_dict(), best_model_path)
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"\n[train] Early stopping at epoch {epoch} (no improvement for {args.patience} epochs)")
                break

    print("=" * 80)
    print(f"[train] Best model at epoch {best_epoch} with val F1={best_val_f1:.4f}")
    print(f"[train] Saved to: {best_model_path}")

    # 6. Final evaluation with best model
    model.load_state_dict(torch.load(best_model_path, weights_only=True))
    model.eval()
    all_preds = []
    all_targets = []
    with torch.no_grad():
        for emb_batch, lbl_batch in val_loader:
            emb_batch = emb_batch.to(device)
            preds = model(emb_batch)
            all_preds.append(preds.cpu().numpy())
            all_targets.append(lbl_batch.numpy())

    all_preds = np.concatenate(all_preds)
    all_targets = np.concatenate(all_targets)
    final_metrics = compute_metrics(all_preds, all_targets)

    print("\n" + "=" * 80)
    print("  FINAL EVALUATION (best checkpoint on validation set)")
    print("=" * 80)
    print_confusion_matrix(final_metrics)
    print_class_report(final_metrics)

    # 7. Save training history plot
    try:
        save_training_plot(history, output_dir / "training_history.png")
    except Exception as e:
        print(f"[train] Could not save plot (matplotlib may not be installed): {e}")

    # Save history as JSON for reference
    history_path = output_dir / "training_history.json"
    history_path.write_text(json.dumps(history, indent=2))
    print(f"\n[train] Training history saved to {history_path}")

    return best_model_path


def save_training_plot(history: dict, path):
    """Save a 2-panel training history plot."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs = range(1, len(history["train_loss"]) + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.plot(epochs, history["train_loss"], label="Train Loss")
    ax1.plot(epochs, history["val_loss"], label="Val Loss")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("BCE Loss")
    ax1.set_title("Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(epochs, history["val_acc"], label="Accuracy")
    ax2.plot(epochs, history["val_f1"], label="F1 Score")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score")
    ax2.set_title("Validation Metrics")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.suptitle("NaariRakshak Violence Classifier — Training History", fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[train] Training plot saved to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Train a violence classifier (MLP) on top of CLIP embeddings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_violence_classifier.py --data_dir ./data
  python train_violence_classifier.py --data_dir ./data --epochs 30 --batch_size 64 --frames_per_video 10
  python train_violence_classifier.py --data_dir ./data --cache_dir ./emb_cache --output_dir ./models
        """,
    )
    parser.add_argument(
        "--data_dir", type=str, required=True,
        help="Root directory containing Violence/ and NonViolence/ subdirectories.",
    )
    parser.add_argument("--epochs", type=int, default=30, help="Max training epochs (default: 30).")
    parser.add_argument("--batch_size", type=int, default=64, help="Batch size for both embedding extraction and training (default: 64).")
    parser.add_argument("--frames_per_video", type=int, default=10, help="Number of frames to sample per video (default: 10).")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate for Adam optimizer (default: 1e-3).")
    parser.add_argument("--patience", type=int, default=5, help="Early stopping patience in epochs (default: 5).")
    parser.add_argument(
        "--cache_dir", type=str, default="./embedding_cache",
        help="Directory to cache extracted CLIP embeddings (default: ./embedding_cache).",
    )
    parser.add_argument(
        "--output_dir", type=str, default="./models",
        help="Directory to save the trained model and plots (default: ./models).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
