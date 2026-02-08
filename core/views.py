import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from .models import Job, Resume
from django.contrib import messages
from .utils import extract_text_from_file
from .embeddings import compute_similarity
from .scoring import classify_job_requirements, score_resume
from .skills import SKILL_LIST


def home(request):
    return render(request, "core/home.html")


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "registration/signup.html", {"form": form})


@login_required
def upload_job(request):
    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        skills_json = request.POST.get("skills_json", "[]")

        try:
            selected_skills = json.loads(skills_json)
        except Exception:
            selected_skills = []

        job = Job.objects.create(
            title=title,
            description=description,
            skills=selected_skills
        )

        return redirect("upload_resumes", job_id=job.id)

    return render(request, "core/upload_job.html", {
        "skill_list": SKILL_LIST
    })


@login_required
def upload_resumes(request, job_id):
    job = Job.objects.get(id=job_id)

    if request.method == "POST":
        files = request.FILES.getlist("resumes")

        precomputed = classify_job_requirements(job.description, job.skills)

        for file in files:
            try:
                text = extract_text_from_file(file)
            except RuntimeError as exc:
                messages.error(
                    request,
                    f"{file.name}: OCR unavailable. Install tesseract-ocr and pytesseract to read images.",
                )
                continue

            if job.skills or job.description:
                analysis = score_resume(
                    job.description,
                    text,
                    selected_skills=job.skills,
                    precomputed=precomputed,
                )
                score = analysis["overall_score"]
            else:
                score = compute_similarity(job.description, text)

            Resume.objects.create(
                job=job,
                file=file,
                extracted_text=text,
                similarity_score=score
            )

        return redirect("results", job_id=job.id)

    return render(request, "core/upload_resumes.html", {"job": job})


def results(request, job_id):
    job = Job.objects.get(id=job_id)

    precomputed = classify_job_requirements(job.description, job.skills)

    resumes = list(Resume.objects.filter(job=job))

    for r in resumes:
        analysis = score_resume(
            job.description,
            r.extracted_text or "",
            selected_skills=job.skills,
            precomputed=precomputed,
        )

        r.similarity_score = analysis["overall_score"]
        r.section_scores = analysis["section_scores"]
        r.matched_skills = ", ".join(analysis["matched_skills"]) if analysis["matched_skills"] else "None"
        r.missing_skills = ", ".join(analysis["missing_skills"]) if analysis["missing_skills"] else "None"
        r.must_skills = analysis["must_skills"]
        r.nice_skills = analysis["nice_skills"]
        r.matched_must_count = max(len(analysis["must_skills"]) - len(analysis["missing_skills"]), 0)
        r.matched_nice_count = max(len(analysis["matched_skills"]) - r.matched_must_count, 0)
        r.fit_summary = analysis["fit_summary"]
        r.gap_analysis = analysis["gap_analysis"]

        # Status logic
        if r.similarity_score >= 0.75:
            r.status = "Shortlisted"
        elif r.similarity_score >= 0.50:
            r.status = "Review"
        else:
            r.status = "Rejected"

    resumes.sort(key=lambda resume: resume.similarity_score, reverse=True)

    return render(request, "core/results.html", {
        "resumes": resumes,
        "job": job,
    })


def dashboard(request, job_id):
    job = Job.objects.get(id=job_id)
    precomputed = classify_job_requirements(job.description, job.skills)
    resumes = list(Resume.objects.filter(job=job))
    total_resumes = len(resumes)
    shortlisted_count = 0
    rejected_count = 0
    score_sum = 0.0

    for r in resumes:
        analysis = score_resume(
            job.description,
            r.extracted_text or "",
            selected_skills=job.skills,
            precomputed=precomputed,
        )
        r.similarity_score = analysis["overall_score"]
        if r.similarity_score >= 0.75:
            shortlisted_count += 1
        elif r.similarity_score < 0.50:
            rejected_count += 1

        score_sum += r.similarity_score

    avg_score = round(score_sum / total_resumes, 4) if total_resumes else 0.0

    return render(request, "core/dashboard.html", {
        "job": job,
        "total_resumes": total_resumes,
        "shortlisted_count": shortlisted_count,
        "rejected_count": rejected_count,
        "avg_score": avg_score
    })


from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font

def download_excel(request, job_id):
    job = Job.objects.get(id=job_id)

    precomputed = classify_job_requirements(job.description, job.skills)
    resumes = list(Resume.objects.filter(job=job))
    shortlisted = []

    for r in resumes:
        analysis = score_resume(
            job.description,
            r.extracted_text or "",
            selected_skills=job.skills,
            precomputed=precomputed,
        )
        r.similarity_score = analysis["overall_score"]
        if r.similarity_score >= 0.75:
            shortlisted.append(r)

    shortlisted.sort(key=lambda resume: resume.similarity_score, reverse=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Shortlisted Candidates"

    # Header row
    headers = ["File Name", "Similarity Score", "Status"]
    ws.append(headers)

    for col in range(1, 4):
        ws.cell(row=1, column=col).font = Font(bold=True)

    for r in shortlisted:
        filename = r.file.name.split("/")[-1]   # <-- IMPORTANT FIX

        ws.append([
            filename,
            round(r.similarity_score, 3),
            "Shortlisted"
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="shortlisted_candidates.xlsx"'

    wb.save(response)
    return response
