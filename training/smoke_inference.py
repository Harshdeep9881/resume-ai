#!/usr/bin/env python3
"""Quick inference smoke test for a trained embedding model."""

from __future__ import annotations

import argparse

from sentence_transformers import SentenceTransformer, util


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Model name or local model directory")
    parser.add_argument("--job-text", required=True)
    parser.add_argument("--resume-text", required=True)
    args = parser.parse_args()

    model = SentenceTransformer(args.model)
    emb = model.encode([args.job_text, args.resume_text], normalize_embeddings=True)
    score = float(util.cos_sim(emb[0], emb[1]).item())
    print(f"cosine_similarity={score:.4f}")


if __name__ == "__main__":
    main()
