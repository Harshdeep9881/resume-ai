#!/usr/bin/env python3
"""Fine-tune a SentenceTransformer model using triplet data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from sentence_transformers import InputExample, SentenceTransformer, losses
from sentence_transformers.evaluation import TripletEvaluator
from torch.utils.data import DataLoader


def _load_triplets(path: Path) -> List[dict]:
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if not all(k in item for k in ("anchor", "positive", "negative")):
                continue
            records.append(item)
    if not records:
        raise ValueError(f"No valid triplets found in {path}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune embeddings for resume ranking.")
    parser.add_argument("--train-triplets", required=True, help="Path to train_triplets.jsonl")
    parser.add_argument("--val-triplets", default="", help="Path to val_triplets.jsonl")
    parser.add_argument("--base-model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--output-dir", required=True, help="Directory for trained model")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    args = parser.parse_args()

    train_path = Path(args.train_triplets)
    val_path = Path(args.val_triplets) if args.val_triplets else None
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_records = _load_triplets(train_path)

    train_samples = [
        InputExample(texts=[x["anchor"], x["positive"], x["negative"]]) for x in train_records
    ]
    train_loader = DataLoader(train_samples, shuffle=True, batch_size=args.batch_size)

    model = SentenceTransformer(args.base_model)
    train_loss = losses.TripletLoss(model=model)

    evaluator = None
    eval_steps = 0
    if val_path and val_path.exists() and val_path.stat().st_size > 0:
        val_records = _load_triplets(val_path)
        evaluator = TripletEvaluator(
            anchors=[x["anchor"] for x in val_records],
            positives=[x["positive"] for x in val_records],
            negatives=[x["negative"] for x in val_records],
            name="val-triplets",
        )
        eval_steps = max(100, len(train_loader) // 2)

    warmup_steps = int(len(train_loader) * args.epochs * args.warmup_ratio)

    model.fit(
        train_objectives=[(train_loader, train_loss)],
        epochs=args.epochs,
        warmup_steps=warmup_steps,
        optimizer_params={"lr": args.learning_rate},
        evaluator=evaluator,
        evaluation_steps=eval_steps,
        output_path=str(output_dir),
        show_progress_bar=True,
    )

    print(f"Training complete. Model saved to: {output_dir}")


if __name__ == "__main__":
    main()
