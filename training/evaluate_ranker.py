#!/usr/bin/env python3
"""Evaluate a resume ranking model on labeled CSV data."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from sentence_transformers import SentenceTransformer, util

POSITIVE_DEFAULT = {"shortlist", "interview", "hire", "yes", "pass"}


@dataclass
class Row:
    job_id: str
    job_text: str
    resume_text: str
    outcome: str


@dataclass
class Scored:
    label: int
    score: float


def _read_rows(path: Path) -> List[Row]:
    rows: List[Row] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for line in reader:
            job_id = (line.get("job_id") or "").strip()
            job_text = (line.get("job_text") or "").strip()
            resume_text = (line.get("resume_text") or "").strip()
            outcome = (line.get("outcome") or "").strip().lower()
            if job_id and job_text and resume_text and outcome:
                rows.append(Row(job_id, job_text, resume_text, outcome))
    if not rows:
        raise ValueError("No valid rows found for evaluation")
    return rows


def _recall_at_k(items: List[Scored], k: int) -> float:
    positives = sum(x.label for x in items)
    if positives == 0:
        return 0.0
    found = sum(x.label for x in items[:k])
    return found / positives


def _mrr(items: List[Scored]) -> float:
    for idx, item in enumerate(items, start=1):
        if item.label == 1:
            return 1.0 / idx
    return 0.0


def _dcg(items: List[Scored], k: int) -> float:
    score = 0.0
    for i, item in enumerate(items[:k], start=1):
        gain = float(item.label)
        score += gain / math.log2(i + 1)
    return score


def _ndcg_at_k(items: List[Scored], k: int) -> float:
    actual = _dcg(items, k)
    ideal = _dcg(sorted(items, key=lambda x: x.label, reverse=True), k)
    if ideal == 0.0:
        return 0.0
    return actual / ideal


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ranking quality for a fine-tuned embedding model")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--model", required=True, help="Model name or local path")
    parser.add_argument(
        "--positive-outcomes",
        default=",".join(sorted(POSITIVE_DEFAULT)),
        help="Comma-separated outcomes treated as positive",
    )
    parser.add_argument("--k", type=int, default=5, help="Top-k for Recall@k / nDCG@k")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    positive = {x.strip().lower() for x in args.positive_outcomes.split(",") if x.strip()}
    if not positive:
        raise ValueError("positive outcomes set cannot be empty")

    rows = _read_rows(Path(args.input_csv))

    grouped: Dict[str, List[Row]] = defaultdict(list)
    for row in rows:
        grouped[row.job_id].append(row)

    model = SentenceTransformer(args.model)

    per_job_metrics = []

    for job_id, job_rows in grouped.items():
        if len(job_rows) < 2:
            continue

        anchor_text = job_rows[0].job_text
        resume_texts = [x.resume_text for x in job_rows]

        anchor_emb = model.encode([anchor_text], normalize_embeddings=True)
        resume_embs = model.encode(resume_texts, normalize_embeddings=True)
        sims = util.cos_sim(anchor_emb, resume_embs).tolist()[0]

        ranked = [
            Scored(label=1 if row.outcome in positive else 0, score=float(score))
            for row, score in zip(job_rows, sims)
        ]
        ranked.sort(key=lambda x: x.score, reverse=True)

        if sum(item.label for item in ranked) == 0:
            continue

        per_job_metrics.append(
            {
                "job_id": job_id,
                "recall_at_k": _recall_at_k(ranked, args.k),
                "mrr": _mrr(ranked),
                "ndcg_at_k": _ndcg_at_k(ranked, args.k),
                "num_candidates": len(ranked),
                "num_positive": sum(item.label for item in ranked),
            }
        )

    if not per_job_metrics:
        raise ValueError("No evaluable jobs found (check labels and rows per job).")

    summary = {
        "jobs_evaluated": len(per_job_metrics),
        "k": args.k,
        "mean_recall_at_k": sum(x["recall_at_k"] for x in per_job_metrics) / len(per_job_metrics),
        "mean_mrr": sum(x["mrr"] for x in per_job_metrics) / len(per_job_metrics),
        "mean_ndcg_at_k": sum(x["ndcg_at_k"] for x in per_job_metrics) / len(per_job_metrics),
    }

    print(json.dumps(summary, indent=2))

    if args.output_json:
        payload = {"summary": summary, "per_job": per_job_metrics}
        Path(args.output_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote metrics to {args.output_json}")


if __name__ == "__main__":
    main()
