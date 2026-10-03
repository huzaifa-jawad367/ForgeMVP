"""EfficientAD-Medium Inference on VisA Dataset.

Model: thangkt/visionqc-efficientad-medium-pcb1 (Hugging Face)
Architecture: EfficientAD-medium (Student-Teacher + Autoencoder anomaly detector)
Trained on: VisA pcb1 category using Anomalib 2.6.0

Features:
1. Evaluates on the official VisA 1-class test set (Normal vs Anomaly)
2. Computes image-level metrics: Accuracy, Precision, Recall, F1-Score, AUROC
3. Generates and saves visual defect heatmaps with jet colormaps overlaid on original images
4. Exports detailed per-image prediction CSVs to `outputs/efficientad_predictions/`
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from PIL import Image
import torch
from torchvision.transforms import functional as TF
from huggingface_hub import hf_hub_download
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

import warnings
warnings.filterwarnings("ignore")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("efficientad_visa")

HF_REPO_ID = "thangkt/visionqc-efficientad-medium-pcb1"
CKPT_FILENAME = "model-best.ckpt"
DEFAULT_VISA_ROOT = Path("../data/VisA_20220922").resolve()
OUTPUT_DIR = Path("./outputs/efficientad_predictions").resolve()


def get_model(ckpt_path: Optional[str] = None, device: str = "cpu"):
    """Load the EfficientAD-medium model from checkpoint with Anomalib architecture."""
    from anomalib.models import EfficientAd

    if ckpt_path is None or not Path(ckpt_path).exists():
        logger.info("Fetching model checkpoint from Hugging Face: %s ...", HF_REPO_ID)
        ckpt_path = hf_hub_download(repo_id=HF_REPO_ID, filename=CKPT_FILENAME)
        logger.info("Checkpoint ready at: %s", ckpt_path)

    logger.info("Loading checkpoint weights: %s", ckpt_path)
    data = torch.load(ckpt_path, map_location=device, weights_only=False)
    hparams = data.get("hyper_parameters", {})

    model = EfficientAd(
        model_size=hparams.get("model_size", "medium"),
        teacher_out_channels=hparams.get("teacher_out_channels", 384),
        padding=hparams.get("padding", False),
        pad_maps=hparams.get("pad_maps", True),
    )
    # strict=False avoids PL evaluator metric buffers mismatch
    model.load_state_dict(data["state_dict"], strict=False)
    model.to(device)
    model.eval()

    # When normalization is enabled in Anomalib, normalized_image_threshold is 0.5
    norm_thresh = float(model.post_processor.normalized_image_threshold.item()) if hasattr(model.post_processor, "normalized_image_threshold") else 0.5
    raw_thresh = float(model.post_processor.image_threshold.item()) if hasattr(model.post_processor, "image_threshold") else 0.1376
    logger.info(
        "EfficientAD loaded successfully! (Normalized Threshold: %.4f, Raw Threshold: %.4f)",
        norm_thresh,
        raw_thresh,
    )
    return model, norm_thresh, raw_thresh


def predict_single_image(
    model,
    image_path: Path,
    threshold: float = 0.5,
    device: str = "cpu",
    target_size: Tuple[int, int] = (256, 256),
) -> Dict:
    """Run inference on a single image and return anomaly score, prediction, and anomaly map."""
    pil_img = Image.open(image_path).convert("RGB")
    orig_w, orig_h = pil_img.size

    # Resize to 256x256 as required by EfficientAD
    resized_pil = pil_img.resize(target_size, Image.BILINEAR)
    tensor = TF.to_tensor(resized_pil).unsqueeze(0).to(device)

    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(tensor)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    score = float(out.pred_score.item())
    if hasattr(out, "pred_label") and out.pred_label is not None:
        is_anomaly = bool(out.pred_label.item()) if threshold == 0.5 else bool(score >= threshold)
    else:
        is_anomaly = bool(score >= threshold)

    anomaly_map = out.anomaly_map.squeeze().cpu().numpy()

    return {
        "score": score,
        "is_anomaly": is_anomaly,
        "latency_ms": latency_ms,
        "anomaly_map": anomaly_map,
        "orig_size": (orig_w, orig_h),
    }


def save_heatmap_visualization(
    image_path: Path,
    anomaly_map: np.ndarray,
    output_path: Path,
    score: float,
    is_anomaly: bool,
    true_label: Optional[str] = None,
    mask_path: Optional[Path] = None,
):
    """Save side-by-side or overlaid anomaly heatmap visualization."""
    orig_bgr = cv2.imread(str(image_path))
    if orig_bgr is None:
        return
    h, w = orig_bgr.shape[:2]

    # Resize anomaly map to original dimensions
    amap_resized = cv2.resize(anomaly_map, (w, h))
    amap_norm = np.clip(amap_resized, 0, 1)
    heatmap = cv2.applyColorMap(np.uint8(255 * amap_norm), cv2.COLORMAP_JET)

    # Blended overlay
    overlay = cv2.addWeighted(orig_bgr, 0.65, heatmap, 0.35, 0)

    # Annotate on overlay
    status_text = f"PRED: {'ANOMALY' if is_anomaly else 'NORMAL'} (Score: {score:.3f})"
    if true_label:
        status_text += f" | TRUE: {true_label.upper()}"
    color = (0, 0, 255) if is_anomaly else (0, 255, 0)

    cv2.rectangle(overlay, (10, 10), (w - 10, 60), (0, 0, 0), -1)
    cv2.putText(
        overlay,
        status_text,
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        2,
        cv2.LINE_AA,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), overlay)


def evaluate_visa_split(
    model,
    image_threshold: float,
    pixel_threshold: float,
    visa_root: Path,
    category: str = "pcb1",
    split: str = "test",
    limit: Optional[int] = None,
    save_heatmaps_count: int = 10,
    device: str = "cpu",
):
    """Evaluate on VisA split CSV and compute anomaly detection metrics."""
    split_csv_path = visa_root / "split_csv" / "1cls.csv"
    if not split_csv_path.exists():
        raise FileNotFoundError(f"1cls.csv not found at {split_csv_path}")

    df = pd.read_csv(split_csv_path)
    subset = df[(df["object"] == category) & (df["split"] == split)].copy()

    if subset.empty:
        logger.warning("No records found for category=%s, split=%s in 1cls.csv", category, split)
        return None

    if limit is not None and limit > 0:
        # Sample proportionally from normal and anomaly
        normals = subset[subset["label"] == "normal"].head(limit // 2)
        anomalies = subset[subset["label"] == "anomaly"].head(limit // 2)
        subset = pd.concat([normals, anomalies]).reset_index(drop=True)

    logger.info(
        "Evaluating %d images for category '%s' (Normal: %d, Anomaly: %d)...",
        len(subset),
        category,
        int((subset["label"] == "normal").sum()),
        int((subset["label"] == "anomaly").sum()),
    )

    results = []
    saved_heatmaps = 0

    for idx, row in subset.iterrows():
        img_rel_path = row["image"]
        img_full_path = visa_root / img_rel_path
        true_label = row["label"]
        true_binary = 1 if true_label == "anomaly" else 0

        if not img_full_path.exists():
            logger.warning("Image missing: %s", img_full_path)
            continue

        res = predict_single_image(
            model=model,
            image_path=img_full_path,
            threshold=image_threshold,
            device=device,
        )

        pred_binary = 1 if res["is_anomaly"] else 0
        correct = (pred_binary == true_binary)

        # Save sample visual heatmaps
        heatmap_file = None
        if saved_heatmaps < save_heatmaps_count:
            # Prioritize saving anomalies and some normals
            should_save = (true_binary == 1) or (saved_heatmaps < save_heatmaps_count // 2)
            if should_save:
                out_name = f"{category}_{split}_{idx:04d}_{true_label}_{'pred_anom' if res['is_anomaly'] else 'pred_norm'}.jpg"
                out_path = OUTPUT_DIR / "heatmaps" / out_name
                save_heatmap_visualization(
                    image_path=img_full_path,
                    anomaly_map=res["anomaly_map"],
                    output_path=out_path,
                    score=res["score"],
                    is_anomaly=res["is_anomaly"],
                    true_label=true_label,
                )
                heatmap_file = out_path.name
                saved_heatmaps += 1

        results.append({
            "object": category,
            "split": split,
            "image": img_rel_path,
            "true_label": true_label,
            "true_binary": true_binary,
            "pred_score": round(res["score"], 4),
            "pred_binary": pred_binary,
            "pred_label": "anomaly" if res["is_anomaly"] else "normal",
            "correct": correct,
            "latency_ms": round(res["latency_ms"], 2),
            "heatmap_path": heatmap_file or "",
        })

        if (idx + 1) % 25 == 0 or (idx + 1) == len(subset):
            logger.info("Processed [%d/%d] images...", idx + 1, len(subset))

    res_df = pd.DataFrame(results)

    # Compute metrics
    y_true = res_df["true_binary"].values
    y_pred = res_df["pred_binary"].values
    y_scores = res_df["pred_score"].values

    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    try:
        auroc = roc_auc_score(y_true, y_scores)
    except Exception:
        auroc = float("nan")

    cm = confusion_matrix(y_true, y_pred)
    # tn, fp, fn, tp
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)

    avg_latency = res_df["latency_ms"].mean()

    # Save prediction table CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_out = OUTPUT_DIR / f"predictions_{category}_{split}.csv"
    res_df.to_csv(csv_out, index=False)

    print("\n" + "=" * 80)
    print(f"EFFICIENTAD EVALUATION RESULTS: {category.upper()} ({split.upper()} SET)")
    print("=" * 80)
    print(f"Total Evaluated Images : {len(res_df)}")
    print(f"Image-level AUROC      : {auroc:.4f}")
    print(f"Accuracy               : {acc * 100:.2f}%")
    print(f"F1-Score               : {f1:.4f}")
    print(f"Precision              : {prec * 100:.2f}%")
    print(f"Recall (Sensitivity)   : {rec * 100:.2f}%")
    print(f"True Positives (Anom)  : {tp} / {tp + fn}")
    print(f"True Negatives (Norm)  : {tn} / {tn + fp}")
    print(f"False Positives        : {fp}")
    print(f"False Negatives        : {fn}")
    print(f"Avg Inference Latency  : {avg_latency:.2f} ms")
    print(f"Predictions saved to   : {csv_out}")
    print(f"Heatmap overlays saved : {OUTPUT_DIR / 'heatmaps'}")
    print("=" * 80)

    return {
        "category": category,
        "split": split,
        "total": len(res_df),
        "auroc": round(auroc, 4),
        "accuracy": round(acc, 4),
        "f1_score": round(f1, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "avg_latency_ms": round(avg_latency, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Run EfficientAD-Medium inference on VisA dataset")
    parser.add_argument("--category", type=str, default="pcb1", help="VisA category (default: pcb1)")
    parser.add_argument("--split", type=str, default="test", help="VisA split to evaluate (default: test)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of images for quick testing (e.g. 20)")
    parser.add_argument("--save-heatmaps", type=int, default=10, help="Number of heatmap overlay images to save")
    parser.add_argument("--image", type=str, default=None, help="Path to single image for ad-hoc inference")
    parser.add_argument("--visa-root", type=str, default=str(DEFAULT_VISA_ROOT), help="Path to VisA dataset root")
    parser.add_argument("--ckpt", type=str, default=None, help="Path to local checkpoint if already downloaded")
    args = parser.parse_args()

    visa_root = Path(args.visa_root).resolve()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Using device: %s", device)

    # Load model
    model, img_thresh, pix_thresh = get_model(ckpt_path=args.ckpt, device=device)

    if args.image:
        img_p = Path(args.image).resolve()
        logger.info("Running single image inference: %s", img_p)
        res = predict_single_image(model, img_p, threshold=img_thresh, device=device)
        out_heatmap = OUTPUT_DIR / f"single_{img_p.stem}_heatmap.jpg"
        save_heatmap_visualization(
            image_path=img_p,
            anomaly_map=res["anomaly_map"],
            output_path=out_heatmap,
            score=res["score"],
            is_anomaly=res["is_anomaly"],
        )
        print("\nSingle Image Prediction:")
        print(f" Image       : {img_p.name}")
        print(f" Score       : {res['score']:.4f} (Threshold: {img_thresh:.4f})")
        print(f" Verdict     : {'ANOMALY DETECTED' if res['is_anomaly'] else 'NORMAL'}")
        print(f" Latency     : {res['latency_ms']:.2f} ms")
        print(f" Overlay Map : {out_heatmap}")
    else:
        evaluate_visa_split(
            model=model,
            image_threshold=img_thresh,
            pixel_threshold=pix_thresh,
            visa_root=visa_root,
            category=args.category,
            split=args.split,
            limit=args.limit,
            save_heatmaps_count=args.save_heatmaps,
            device=device,
        )


if __name__ == "__main__":
    main()
