#!/usr/bin/env python3
"""Prepare triplet datasets for SentenceTransformer fine-tuning.

Input CSV columns:
- job_id
- job_text
- resume_text
- outcome

The script performs a job-level train/validation split to avoid leakage.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

POSITIVE_DEFAULT = {"shortlist", "interview", "hire", "yes", "pass"}


@dataclass
class Row:
    job_id: str
    job_text: str
    resume_text: str
    outcome: str


def _read_rows(path: Path) -> List[Row]:
    rows: List[Row] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        expected = {"job_id", "job_text", "resume_text", "outcome"}
        missing = expected - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        for line in reader:
            job_id = (line.get("job_id") or "").strip()
            job_text = (line.get("job_text") or "").strip()
            resume_text = (line.get("resume_text") or "").strip()
            outcome = (line.get("outcome") or "").strip().lower()
            if not (job_id and job_text and resume_text and outcome):
                continue
            rows.append(Row(job_id=job_id, job_text=job_text, resume_text=resume_text, outcome=outcome))
    if not rows:
        raise ValueError("No valid rows found in input CSV.")
    return rows


def _split_jobs(job_ids: List[str], val_ratio: float, seed: int) -> Dict[str, str]:
    if not 0.0 <= val_ratio < 1.0:
        raise ValueError("val_ratio must be in [0.0, 1.0).")

    rng = random.Random(seed)
    shuffled = list(job_ids)
    rng.shuffle(shuffled)

    val_count = int(round(len(shuffled) * val_ratio))
    val_jobs = set(shuffled[:val_count])

    result: Dict[str, str] = {}
    for jid in shuffled:
        result[jid] = "val" if jid in val_jobs else "train"
    return result


def _write_jsonl(path: Path, payloads: List[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for item in payloads:
            f.write(json.dumps(item, ensure_ascii=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare train/val triplets from labeled resume data.")
    parser.add_argument("--input-csv", required=True, help="Path to labeled CSV")
    parser.add_argument("--output-dir", default="training/outputs", help="Directory for prepared files")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation ratio split by job_id")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--positive-outcomes",
        default=",".join(sorted(POSITIVE_DEFAULT)),
        help="Comma-separated outcomes treated as positive",
    )
    parser.add_argument(
        "--max-negatives-per-positive",
        type=int,
        default=4,
        help="Triplets created per positive resume (sampled from same job negatives)",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    positives = {x.strip().lower() for x in args.positive_outcomes.split(",") if x.strip()}
    if not positives:
        raise ValueError("positive outcomes set cannot be empty")

    rows = _read_rows(input_csv)
    by_job: Dict[str, List[Row]] = defaultdict(list)
    for row in rows:
        by_job[row.job_id].append(row)

    split_map = _split_jobs(sorted(by_job.keys()), args.val_ratio, args.seed)
    rng = random.Random(args.seed)

    train_triplets: List[dict] = []
    val_triplets: List[dict] = []

    skipped_jobs = 0
    for job_id, group in by_job.items():
        pos = [r for r in group if r.outcome in positives]
        neg = [r for r in group if r.outcome not in positives]

        # Need both classes per job for useful triplets.
        if not pos or not neg:
            skipped_jobs += 1
            continue

        split = split_map[job_id]
        target = train_triplets if split == "train" else val_triplets

        for p in pos:
            sample_size = min(len(neg), max(1, args.max_negatives_per_positive))
            sampled_negatives = rng.sample(neg, sample_size)
            for n in sampled_negatives:
                target.append(
                    {
                        "job_id": p.job_id,
                        "anchor": p.job_text,
                        "positive": p.resume_text,
                        "negative": n.resume_text,
                    }
                )

    if not train_triplets:
        raise ValueError("No train triplets created. Check labels and class balance per job.")

    _write_jsonl(output_dir / "train_triplets.jsonl", train_triplets)
    _write_jsonl(output_dir / "val_triplets.jsonl", val_triplets)

    metadata = {
        "input_csv": str(input_csv),
        "total_rows": len(rows),
        "jobs_total": len(by_job),
        "jobs_skipped_no_pos_or_neg": skipped_jobs,
        "train_triplets": len(train_triplets),
        "val_triplets": len(val_triplets),
        "positive_outcomes": sorted(positives),
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "max_negatives_per_positive": args.max_negatives_per_positive,
    }

    with (output_dir / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("Prepared data successfully")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
