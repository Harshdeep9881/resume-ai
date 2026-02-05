from django.shortcuts import render, redirect
from .models import Job, Resume
from .utils import extract_text_from_pdf
from .embeddings import compute_similarity

def home(request):
    return render(request, "core/home.html")


def upload_job(request):
    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")

        job = Job.objects.create(title=title, description=description)

        return redirect("upload_resumes", job_id=job.id)

    return render(request, "core/upload_job.html")


def upload_resumes(request, job_id):
    job = Job.objects.get(id=job_id)

    if request.method == "POST":
        files = request.FILES.getlist("resumes")

        for file in files:
            text = extract_text_from_pdf(file)

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

    resumes = Resume.objects.filter(job=job).order_by("-similarity_score")

    for r in resumes:
        if r.similarity_score >= 0.75:
            r.status = "Shortlisted ✅"
        elif r.similarity_score >= 0.50:
            r.status = "Review ⚠️"
        else:
            r.status = "Rejected ❌"

    return render(request, "core/results.html", {
        "resumes": resumes,
        "job": job
    })

from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font

def download_excel(request, job_id):
    job = Job.objects.get(id=job_id)

    shortlisted = Resume.objects.filter(
        job=job,
        similarity_score__gte=0.75
    ).order_by("-similarity_score")

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


