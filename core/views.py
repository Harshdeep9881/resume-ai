import json
from django.shortcuts import render, redirect
from .models import Job, Resume
from .utils import extract_text_from_pdf
from .embeddings import compute_similarity, extract_skills
from .skills import SKILL_LIST


def home(request):
    return render(request, "core/home.html")


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


def upload_resumes(request, job_id):
    job = Job.objects.get(id=job_id)

    if request.method == "POST":
        files = request.FILES.getlist("resumes")

        for file in files:
            text = extract_text_from_pdf(file)

            if job.skills:
                resume_skills = extract_skills(text)
                matched = list(set(job.skills) & set(resume_skills))
                score = round(len(matched) / len(job.skills), 4) if job.skills else 0.0
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

    # Extract skills from job description once
    try:
        if job.skills:
            job_skills = job.skills
        else:
            job_skills = extract_skills(job.description)
    except:
        job_skills = []


    resumes = Resume.objects.filter(job=job).order_by("-similarity_score")

    for r in resumes:
        # Extract skills from each resume
        try:
            resume_skills = extract_skills(r.extracted_text)
        except:
            resume_skills = []


        # Compute matched & missing skills
        matched = list(set(job_skills) & set(resume_skills))
        missing = list(set(job_skills) - set(resume_skills))

        # Attach to object for template
        r.matched_skills = ", ".join(matched) if matched else "None"
        r.missing_skills = ", ".join(missing) if missing else "None"

        # Status logic
        if r.similarity_score >= 0.75:
            r.status = "Shortlisted"
        elif r.similarity_score >= 0.50:
            r.status = "Review"
        else:
            r.status = "Rejected"

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
