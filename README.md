# Resume AI

A Django-based resume screening platform with two workflows:

- Legacy flow: upload a job description + bulk resumes, then rank candidates.
- V2 hiring flow: create a structured job, collect candidate applications, score using weighted buckets, and manage a hiring pipeline.

## Features

- Resume text extraction from PDF files.
- Optional OCR support for image resumes (`png`, `jpg`, `jpeg`, `tiff`, `bmp`, `webp`) via Tesseract.
- Skill extraction using keyword matching with embedding fallback.
- Resume scoring with:
  - Must-have vs nice-to-have requirement separation
  - Section-aware scoring (`experience`, `projects`, `education`)
  - Fit summary and gap analysis
- V2 multi-signal evaluation:
  - Custom screening questions
  - Knockout rules
  - Weighted bucket scoring (`skills_evidence`, `problem_solving`, `role_fit`, `work_style`)
  - Final recommendation (`yes`, `hold`, `no`) with confidence level
- HR pipeline views:
  - Candidate list with filters
  - Candidate detail page with bucket breakdown
  - Recommendation override
- Excel export for shortlisted legacy candidates.

## Tech Stack

- Python 3.12+
- Django 6.x
- SQLite (default)
- sentence-transformers (`all-MiniLM-L6-v2`) for embedding similarity
- PyPDF2 + Pillow + pytesseract for document parsing
- Bootstrap 5 + Django templates

## Project Structure

- `resume_ai/` - Django project settings and URL config
- `core/` - Main app (models, scoring logic, views, templates)
- `media/` - Uploaded resumes/artifacts
- `db.sqlite3` - Local development database

## Data Model (High-level)

- `Job`, `Resume` for legacy flow
- `JobEvaluationConfig`, `JobRequirement`, `ScreeningQuestion` for V2 setup
- `Candidate`, `CandidateResume`, `CandidateAnswer`, `CandidateArtifact` for applications
- `KnockoutResult`, `CandidateEvaluation`, `BucketScore` for scoring and decisioning

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run migrations.
4. Create a superuser (optional, for admin access).
5. Start the server.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open: `http://127.0.0.1:8000/`

## OCR Prerequisite (for image resumes)

`pytesseract` is a Python wrapper; it also needs the system `tesseract` binary installed.

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

If Tesseract is missing, image extraction paths will raise an OCR warning and continue.

## First-run Model Download

On first similarity/skill extraction, `sentence-transformers/all-MiniLM-L6-v2` is downloaded. Ensure internet access during first run.

## App Routes

### Auth

- `/login/`
- `/logout/`
- `/signup/`

### Legacy Resume Ranking Flow

- `/upload-job/`
- `/upload-resumes/<job_id>/`
- `/results/<job_id>/`
- `/dashboard/<job_id>/`
- `/compare/<job_id>/`
- `/download-excel/<job_id>/`

### V2 Hiring Flow

- `/setup-job-v2/`
- `/apply/<job_id>/`
- `/apply/<job_id>/success/`
- `/pipeline/<job_id>/`
- `/pipeline/<job_id>/candidate/<candidate_id>/`

## Management Command

Backfill V2 candidate entities from legacy `Resume` rows:

```bash
python manage.py backfill_candidates_from_resumes
```

Useful options:

```bash
python manage.py backfill_candidates_from_resumes --job-id 1
python manage.py backfill_candidates_from_resumes --dry-run
```

## Fine-tuning Pipeline

A complete fine-tuning/evaluation workflow is available under `training/`.

- Guide: `training/README.md`
- Labeled data template: `training/data/labels_template.csv`
- Scripts:
  - `training/prepare_training_data.py`
  - `training/train_embeddings.py`
  - `training/evaluate_ranker.py`
  - `training/smoke_inference.py`

To use a fine-tuned model in the app:

```bash
export RESUME_AI_EMBEDDING_MODEL=/absolute/path/to/your/model
python manage.py runserver
```

## Notes

- Current settings are development-friendly (`DEBUG=True`, SQLite).
- `SECRET_KEY` is currently hardcoded in settings and should be moved to environment variables before production deployment.
- `ALLOWED_HOSTS` is empty by default and must be configured for deployment.

## License

Add your preferred license here (MIT/Apache-2.0/etc.).
