"""
train.py - Train the BioOps Guardian ML classifier.

Usage:
    python src/train.py                         # defaults: 200 per category
    python src/train.py --n_per_category 500    # more data
    python src/train.py --real_data data/real_logs/labels.csv  # mix in real data

The trained model is saved to models/guardian_v1.pkl
"""

import sys
import pathlib
import argparse
import csv
import os

# Make src importable
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.synthetic_data import generate_dataset, save_dataset
from src.ml_classifier import MLClassifier


def load_real_data(labels_csv):
    """Load real labeled logs from a labels.csv file."""
    base_dir = os.path.dirname(labels_csv)
    dataset = []

    with open(labels_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            log_path = os.path.join(base_dir, row["filename"])
            if os.path.exists(log_path):
                with open(log_path) as lf:
                    text = lf.read()
                dataset.append({
                    "text": text,
                    "label": row["label"],
                    "meta": {"pipeline": row.get("pipeline", ""), "source": "real"},
                })

    return dataset


def main():
    parser = argparse.ArgumentParser(description="Train BioOps Guardian ML classifier")
    parser.add_argument("--n_per_category", type=int, default=200,
                        help="Number of synthetic logs per category (default: 200)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--real_data", type=str, default=None,
                        help="Path to labels.csv with real training logs")
    parser.add_argument("--model_output", type=str, default="models/guardian_v1.pkl",
                        help="Where to save the trained model")
    parser.add_argument("--save_synthetic", action="store_true",
                        help="Save generated synthetic logs to data/training/")
    parser.add_argument("--n_estimators", type=int, default=200)
    parser.add_argument("--max_depth", type=int, default=5)
    args = parser.parse_args()

    # ── Generate synthetic data ──────────────────────────────────
    print(f"Generating {args.n_per_category} synthetic logs per category...")
    dataset = generate_dataset(
        n_per_category=args.n_per_category,
        include_clean=True,
        seed=args.seed,
    )
    print(f"  Synthetic: {len(dataset)} logs")

    if args.save_synthetic:
        save_dir = str(PROJECT_ROOT / "data" / "training")
        idx = save_dataset(dataset, save_dir)
        print(f"  Saved to {idx}")

    # ── Mix in real data if provided ─────────────────────────────
    if args.real_data:
        real = load_real_data(args.real_data)
        print(f"  Real data: {len(real)} logs from {args.real_data}")
        dataset.extend(real)
        # Oversample real data (it's more valuable)
        dataset.extend(real * 3)
        print(f"  Total after oversampling real: {len(dataset)}")

    # ── Label distribution ───────────────────────────────────────
    label_counts = {}
    for item in dataset:
        label_counts[item["label"]] = label_counts.get(item["label"], 0) + 1
    print("\nLabel distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")

    # ── Train ────────────────────────────────────────────────────
    print("\nTraining classifier...")
    clf = MLClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
    )
    clf.train(dataset, verbose=True)

    # ── Save model ───────────────────────────────────────────────
    model_path = PROJECT_ROOT / args.model_output
    model_path.parent.mkdir(parents=True, exist_ok=True)
    clf.save(str(model_path))
    print(f"\nModel saved to {model_path}")
    print(f"Model size: {model_path.stat().st_size / 1024 / 1024:.1f} MB")

    # ── Quick smoke test ─────────────────────────────────────────
    print("\n── Smoke test ─────────────────────────────────")
    test_logs = [
        ("Process requirement exceeds available memory -- req: 64 GB; avail: 15 GB", "memory_exceeded"),
        ("No such file or directory: /data/genome.fa", "missing_file"),
        ("FATAL: container creation failed", "container_issue"),
        ("Pipeline completed successfully!", "clean"),
    ]
    for text, expected in test_logs:
        result = clf.predict(text)
        match = "✅" if result["label"] == expected else "❌"
        print(f"  {match} Expected: {expected:<20} Got: {result['label']:<20} Conf: {result['confidence']:.0%}")

    print("\nDone! Run the Streamlit app to use the model interactively.")


if __name__ == "__main__":
    main()
