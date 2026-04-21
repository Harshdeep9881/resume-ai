# Resume AI

A Django-based resume screening platform with two workflows: legacy similarity scoring and a V2 multi-signal evaluation pipeline. Supports local AI assistance using Ollama and Google Gemini.

## System Architecture & Workflows

The platform operates as a modular Django application with an SQLite database (adaptable to PostgreSQL/MySQL). It provides two distinct operational flows:

1. **Legacy Flow:** Centered around bulk uploading applicant resumes against a job description. Uses `sentence-transformers` for embeddings to compute a direct similarity score.
2. **V2 Hiring Flow:** A comprehensive applicant tracking system. Users create structured job postings (with Must-Have/Nice-to-Have criteria, weighted buckets). Candidates apply through an integrated portal with custom screening questions and artifacts. The system then evaluates candidates based on skills, problem-solving, role fit, and work style, culminating in a `yes`, `hold`, or `no` recommendation.

### AI Recruiting Assistant & RAG Workflow

The platform features an intelligent AI Assistant designed to aid recruiters.
- **RAG-Powered Context:** The assistant utilizes a Retrieval-Augmented Generation (RAG) approach. As users interact with the chatbot, it dynamically injects the current job context (Job Title, Description, Selected Skills, and configured Screening Questions) into the prompt. This grounds the AI's generation, ensuring highly relevant and tailored advice.
- **Features:** Generates structured job descriptions, recommends top skills, creates varied screening questions with knockout conditions, and answers HR queries.
- **Ollama Primary Backend:** Configured to run locally and privately using [Ollama](https://ollama.com/) (defaults to `llama3.2`), avoiding API costs and ensuring data privacy.
- **Gemini Fallback:** Seamlessly falls back to Google's Gemini API (`gemini-2.0-flash`, etc.) if the local Ollama instance is unavailable and a `GEMINI_API_KEY` is provided.

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
- **Ollama** (Local AI processing) / **Google Gemini** (Fallback API)
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

### 1. Ollama Setup (Optional but recommended for Local AI)
To use the AI Assistant locally without using Gemini API credits:
1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh` (or visit [ollama.com](https://ollama.com/download))
2. Pull the default model: `ollama pull llama3.2`
3. Serve the model: `ollama serve`

### 2. Django Setup
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

## Multilingual Support

For language detection, translation flow, German/Russian notes, and OCR caveats, see:

- `MULTILINGUAL_README.md`

## Notes

- Current settings are development-friendly (`DEBUG=True`, SQLite).
- `SECRET_KEY` is currently hardcoded in settings and should be moved to environment variables before production deployment.
- `ALLOWED_HOSTS` is empty by default and must be configured for deployment.
- For Gemini API fallback, set `GEMINI_API_KEY=your_api_key_here` in a `.env` file or your environment variable settings.

## License

Add your preferred license here (MIT/Apache-2.0/etc.).
