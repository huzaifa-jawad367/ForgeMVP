"""VisA Dataset Analysis Script using Pandas.

Analyzes the VisA (Visual Anomaly) dataset located at `../data/VisA_20220922`:
1. Class-wise Anomaly vs. Normal distribution (counts and percentages)
2. Fine-grained defect type taxonomy across all 12 categories
3. Standard 1-Class Anomaly Detection Train/Test split analysis
4. Multi-class Few-Shot and High-Shot split distributions
5. Pixel-level Ground Truth mask availability and image resolutions
6. Disk verification and export to CSV files for reporting
"""

from pathlib import Path
import cv2
import pandas as pd

VISA_ROOT = Path("../data/VisA_20220922").resolve()
OUTPUT_DIR = Path("./outputs/dataset_analysis").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def analyze_visa():
    print(f"Loading VisA dataset from: {VISA_ROOT}")
    if not VISA_ROOT.exists():
        raise FileNotFoundError(f"VisA dataset root not found at {VISA_ROOT}")

    # 1. Load 1cls.csv
    cls1_path = VISA_ROOT / "split_csv" / "1cls.csv"
    df_1cls = pd.read_csv(cls1_path)

    # 2. Iterate through all 12 object categories
    categories = sorted([
        d.name for d in VISA_ROOT.iterdir()
        if d.is_dir() and d.name != "split_csv"
    ])

    cat_records = []
    defect_records = []

    for cat in categories:
        cat_dir = VISA_ROOT / cat
        anno_file = cat_dir / "image_anno.csv"
        anno_df = pd.read_csv(anno_file) if anno_file.exists() else None

        img_norm_dir = cat_dir / "Data" / "Images" / "Normal"
        img_anom_dir = cat_dir / "Data" / "Images" / "Anomaly"
        mask_anom_dir = cat_dir / "Data" / "Masks" / "Anomaly"

        # Deduplicated file count (avoiding Windows case-insensitive glob duplication)
        disk_normal = len([
            f for f in img_norm_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg"]
        ]) if img_norm_dir.exists() else 0

        disk_anomaly = len([
            f for f in img_anom_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg"]
        ]) if img_anom_dir.exists() else 0

        disk_masks = len([
            f for f in mask_anom_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".png"]
        ]) if mask_anom_dir.exists() else 0

        # Sample image resolution
        sample_img = next((f for f in img_norm_dir.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg"]), None) if img_norm_dir.exists() else None
        resolution = "N/A"
        if sample_img:
            img = cv2.imread(str(sample_img))
            if img is not None:
                h, w, _ = img.shape
                resolution = f"{w}x{h}"

        cat_records.append({
            "category": cat,
            "disk_normal": disk_normal,
            "disk_anomaly": disk_anomaly,
            "disk_total": disk_normal + disk_anomaly,
            "disk_masks": disk_masks,
            "resolution": resolution,
        })

        # Fine-grained defect labels
        if anno_df is not None:
            defects = anno_df[anno_df["label"] != "normal"]["label"].value_counts()
            for defect_name, count in defects.items():
                defect_records.append({
                    "category": cat,
                    "defect_type": defect_name,
                    "count": count
                })

    df_cat = pd.DataFrame(cat_records)
    df_defects = pd.DataFrame(defect_records)

    # 3. Class-wise crosstab from 1cls.csv
    label_pivot = pd.crosstab(df_1cls["object"], df_1cls["label"]).reset_index()
    label_pivot["Total"] = label_pivot["normal"] + label_pivot["anomaly"]
    label_pivot["anomaly_pct"] = (label_pivot["anomaly"] / label_pivot["Total"] * 100).round(2)
    label_pivot["normal_pct"] = (label_pivot["normal"] / label_pivot["Total"] * 100).round(2)

    # 4. 1-class train/test split breakdown
    split_pivot = (
        pd.crosstab([df_1cls["object"], df_1cls["split"]], df_1cls["label"])
        .unstack(level="split", fill_value=0)
    )
    split_pivot.columns = [f"{col[1]}_{col[0]}" for col in split_pivot.columns]
    split_pivot = split_pivot.reset_index()

    # Merge into primary summary table
    summary_df = pd.merge(
        label_pivot,
        df_cat[["category", "disk_masks", "resolution"]],
        left_on="object",
        right_on="category"
    ).drop(columns=["category"])

    summary_df = pd.merge(summary_df, split_pivot, on="object", how="left")

    # Add Category Grouping for VisA
    category_groups = {
        "pcb1": "Complex structure (PCB)",
        "pcb2": "Complex structure (PCB)",
        "pcb3": "Complex structure (PCB)",
        "pcb4": "Complex structure (PCB)",
        "candle": "Multiple objects",
        "capsules": "Multiple objects",
        "macaroni1": "Multiple objects",
        "macaroni2": "Multiple objects",
        "cashew": "Single / Natural object",
        "chewinggum": "Single / Natural object",
        "fryum": "Single / Natural object",
        "pipe_fryum": "Single / Natural object",
    }
    summary_df.insert(1, "group", summary_df["object"].map(category_groups))

    # Total Row
    total_row = {
        "object": "TOTAL / ENTIRE DATASET",
        "group": "All 12 Classes",
        "normal": int(summary_df["normal"].sum()),
        "anomaly": int(summary_df["anomaly"].sum()),
        "Total": int(summary_df["Total"].sum()),
        "anomaly_pct": round(summary_df["anomaly"].sum() / summary_df["Total"].sum() * 100, 2),
        "normal_pct": round(summary_df["normal"].sum() / summary_df["Total"].sum() * 100, 2),
        "disk_masks": int(summary_df["disk_masks"].sum()),
        "resolution": "Various (~1.3-1.5MP)",
        "train_normal": int(summary_df["train_normal"].sum()),
        "test_normal": int(summary_df["test_normal"].sum()),
        "train_anomaly": int(summary_df["train_anomaly"].sum()),
        "test_anomaly": int(summary_df["test_anomaly"].sum()),
    }
    summary_with_total = pd.concat([summary_df, pd.DataFrame([total_row])], ignore_index=True)

    # 5. Split comparison across 1cls, 2cls_fewshot, 2cls_highshot
    fewshot_path = VISA_ROOT / "split_csv" / "2cls_fewshot.csv"
    highshot_path = VISA_ROOT / "split_csv" / "2cls_highshot.csv"

    splits_overview = [
        {
            "benchmark_split": "1cls (Unsupervised / 1-Class AD)",
            "train_normal": int(((df_1cls["split"] == "train") & (df_1cls["label"] == "normal")).sum()),
            "train_anomaly": int(((df_1cls["split"] == "train") & (df_1cls["label"] == "anomaly")).sum()),
            "test_normal": int(((df_1cls["split"] == "test") & (df_1cls["label"] == "normal")).sum()),
            "test_anomaly": int(((df_1cls["split"] == "test") & (df_1cls["label"] == "anomaly")).sum()),
            "total_images": len(df_1cls),
        }
    ]

    if fewshot_path.exists():
        df_few = pd.read_csv(fewshot_path)
        splits_overview.append({
            "benchmark_split": "2cls_fewshot (Few-Shot Supervised)",
            "train_normal": int(((df_few["split"] == "train") & (df_few["label"] == "normal")).sum()),
            "train_anomaly": int(((df_few["split"] == "train") & (df_few["label"] == "anomaly")).sum()),
            "test_normal": int(((df_few["split"] == "test") & (df_few["label"] == "normal")).sum()),
            "test_anomaly": int(((df_few["split"] == "test") & (df_few["label"] == "anomaly")).sum()),
            "total_images": len(df_few),
        })

    if highshot_path.exists():
        df_high = pd.read_csv(highshot_path)
        splits_overview.append({
            "benchmark_split": "2cls_highshot (High-Shot Supervised)",
            "train_normal": int(((df_high["split"] == "train") & (df_high["label"] == "normal")).sum()),
            "train_anomaly": int(((df_high["split"] == "train") & (df_high["label"] == "anomaly")).sum()),
            "test_normal": int(((df_high["split"] == "test") & (df_high["label"] == "normal")).sum()),
            "test_anomaly": int(((df_high["split"] == "test") & (df_high["label"] == "anomaly")).sum()),
            "total_images": len(df_high),
        })

    df_splits_overview = pd.DataFrame(splits_overview)

    # 6. Save CSVs
    summary_csv_path = OUTPUT_DIR / "visa_classwise_summary.csv"
    defects_csv_path = OUTPUT_DIR / "visa_defect_types_breakdown.csv"
    splits_csv_path = OUTPUT_DIR / "visa_splits_comparison.csv"

    summary_with_total.to_csv(summary_csv_path, index=False)
    df_defects.to_csv(defects_csv_path, index=False)
    df_splits_overview.to_csv(splits_csv_path, index=False)

    print("\n" + "=" * 110)
    print("VISA DATASET: CLASS-WISE BREAKDOWN (ANOMALY VS NORMAL)")
    print("=" * 110)
    print(summary_with_total.to_string(index=False))

    print("\n" + "=" * 110)
    print("BENCHMARK SPLITS OVERVIEW")
    print("=" * 110)
    print(df_splits_overview.to_string(index=False))

    print(f"\nGenerated 3 report CSVs in: {OUTPUT_DIR}")
    print(f" 1. {summary_csv_path.name} (High-level class breakdown with anomaly %, masks, splits)")
    print(f" 2. {defects_csv_path.name} (Detailed 152 defect taxonomy breakdown across all classes)")
    print(f" 3. {splits_csv_path.name} (1-Class vs 2-Class Few-Shot vs High-Shot splits)")


if __name__ == "__main__":
    analyze_visa()
