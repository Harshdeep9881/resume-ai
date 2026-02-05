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
    resumes = job.resumes.all().order_by("-similarity_score")

    return render(request, "core/results.html", {
        "job": job,
        "resumes": resumes
    })
