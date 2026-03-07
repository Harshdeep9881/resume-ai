# Training Pipeline

This folder provides an end-to-end embedding fine-tuning workflow for resume shortlisting.

## 1) Prepare labeled data

Create a CSV with columns:

- `job_id`
- `job_text`
- `resume_text`
- `outcome`

Use `training/data/labels_template.csv` as a reference.

## 2) Build train/validation triplets

```bash
python training/prepare_training_data.py \
  --input-csv training/data/labels.csv \
  --output-dir training/outputs \
  --val-ratio 0.2 \
  --max-negatives-per-positive 4
```

Output files:

- `training/outputs/train_triplets.jsonl`
- `training/outputs/val_triplets.jsonl`
- `training/outputs/metadata.json`

## 3) Fine-tune model

```bash
python training/train_embeddings.py \
  --train-triplets training/outputs/train_triplets.jsonl \
  --val-triplets training/outputs/val_triplets.jsonl \
  --base-model sentence-transformers/all-MiniLM-L6-v2 \
  --output-dir training/outputs/model_v1 \
  --epochs 2 \
  --batch-size 32
```

## 4) Evaluate ranking quality

```bash
python training/evaluate_ranker.py \
  --input-csv training/data/labels.csv \
  --model training/outputs/model_v1 \
  --k 5 \
  --output-json training/outputs/eval_model_v1.json
```

Metrics reported:

- Mean `Recall@k`
- Mean `MRR`
- Mean `nDCG@k`

## 5) Smoke test scoring

```bash
python training/smoke_inference.py \
  --model training/outputs/model_v1 \
  --job-text "Senior backend engineer with Python, Django, AWS" \
  --resume-text "Built Django APIs, deployed on AWS, improved latency"
```

## 6) Use fine-tuned model in app

Set environment variable before running Django:

```bash
export RESUME_AI_EMBEDDING_MODEL=/home/harsh/resume_ai/training/outputs/model_v1
python manage.py runserver
```

If unset, app defaults to `sentence-transformers/all-MiniLM-L6-v2`.

## Data quality notes

- Split by `job_id` (already done) to avoid leakage.
- Keep at least one positive and one negative per job.
- Start with `shortlist/interview/hire` as positive labels.
- Re-train periodically as hiring preferences drift.
