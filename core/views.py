import json
from decimal import Decimal

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import (
    BucketScore,
    Candidate,
    CandidateAnswer,
    CandidateArtifact,
    CandidateEvaluation,
    CandidateResume,
    Job,
    JobEvaluationConfig,
    JobRequirement,
    KnockoutResult,
    Resume,
    ScreeningQuestion,
)
from .utils import extract_text_from_file
from .embeddings import compute_similarity
from .scoring import classify_job_requirements, score_resume
from .skills import SKILL_LIST
from .multilingual import prepare_text_for_analysis


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

            prepared_resume = prepare_text_for_analysis(text)
            analyzed_text = prepared_resume["translated_text"]

            if job.skills or job.description:
                analysis = score_resume(
                    job.description,
                    analyzed_text,
                    selected_skills=job.skills,
                    precomputed=precomputed,
                )
                score = analysis["overall_score"]
            else:
                score = compute_similarity(job.description, analyzed_text)

            Resume.objects.create(
                job=job,
                file=file,
                extracted_text=analyzed_text,
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

        # Status logic: prioritize must-have coverage over score
        if r.must_skills and not analysis["missing_skills"]:
            r.status = "Shortlisted"
        elif r.similarity_score >= 0.75:
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


def compare_candidates(request, job_id):
    job = Job.objects.get(id=job_id)
    precomputed = classify_job_requirements(job.description, job.skills)
    resumes = list(Resume.objects.filter(job=job))

    compared = []
    for r in resumes:
        analysis = score_resume(
            job.description,
            r.extracted_text or "",
            selected_skills=job.skills,
            precomputed=precomputed,
        )

        score = analysis["overall_score"]
        missing = analysis["missing_skills"]
        must_skills = analysis["must_skills"]

        if must_skills and not missing:
            status = "Shortlisted"
        elif score >= 0.75:
            status = "Shortlisted"
        elif score >= 0.50:
            status = "Review"
        else:
            status = "Rejected"

        matched_skills = analysis["matched_skills"]
        compared.append({
            "name": r.file.name.split("/")[-1],
            "score": score,
            "status": status,
            "section_scores": analysis["section_scores"],
            "matched_skills": matched_skills,
            "missing_skills": missing,
            "must_skills": must_skills,
            "nice_skills": analysis["nice_skills"],
            "fit_summary": analysis["fit_summary"],
            "gap_analysis": analysis["gap_analysis"],
            "matched_must_count": max(len(must_skills) - len(missing), 0),
            "matched_nice_count": max(
                len(matched_skills) - max(len(must_skills) - len(missing), 0), 0
            ),
        })

    compared.sort(key=lambda candidate: candidate["score"], reverse=True)
    top_candidates = compared[:4]

    return render(request, "core/compare.html", {
        "job": job,
        "candidates": top_candidates,
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
        if analysis["must_skills"] and not analysis["missing_skills"]:
            shortlisted_count += 1
        elif r.similarity_score >= 0.75:
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


import openpyxl
from openpyxl.styles import Font


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_lines(raw_text):
    if not raw_text:
        return []
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _evaluate_knockout(question, answer):
    rule = question.knockout_rule or {}
    operator = str(rule.get("operator", "equals")).lower()
    expected = str(rule.get("value", "")).strip().lower()
    actual = (answer or "").strip().lower()

    if not expected:
        return bool(actual)
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        return expected in actual
    if operator == "min_value":
        try:
            return float(actual) >= float(expected)
        except ValueError:
            return False
    if operator == "max_value":
        try:
            return float(actual) <= float(expected)
        except ValueError:
            return False
    return actual == expected


def _bucket_weighted_score(raw_score, weight):
    bounded_raw = max(Decimal("0.0"), min(Decimal("5.0"), Decimal(str(raw_score))))
    return (bounded_raw / Decimal("5.0")) * Decimal("100.0") * (Decimal(weight) / Decimal("100.0"))


@login_required
def setup_job_v2(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        location = (request.POST.get("location") or "").strip()
        employment_type = (request.POST.get("employment_type") or "").strip()
        min_exp = request.POST.get("min_experience_years")
        skills_json = request.POST.get("skills_json", "[]")
        must_requirements = _parse_lines(request.POST.get("must_requirements"))
        nice_requirements = _parse_lines(request.POST.get("nice_requirements"))

        weights = {
            "skills": _to_int(request.POST.get("weight_skills_evidence"), 25),
            "problem": _to_int(request.POST.get("weight_problem_solving"), 30),
            "role": _to_int(request.POST.get("weight_role_fit"), 30),
            "style": _to_int(request.POST.get("weight_work_style"), 15),
        }
        if sum(weights.values()) != 100:
            messages.error(request, "Bucket weights must total exactly 100.")
            return redirect("setup_job_v2")

        try:
            selected_skills = json.loads(skills_json)
            if not isinstance(selected_skills, list):
                selected_skills = []
        except Exception:
            selected_skills = []

        questions_payload = request.POST.get("questions_json", "[]")
        try:
            questions = json.loads(questions_payload)
            if not isinstance(questions, list):
                questions = []
        except Exception:
            questions = []

        job = Job.objects.create(
            title=title,
            description=description,
            skills=selected_skills,
            location=location,
            employment_type=employment_type,
            min_experience_years=_to_int(min_exp, None) if min_exp else None,
            created_by=request.user,
        )

        JobEvaluationConfig.objects.create(
            job=job,
            weight_skills_evidence=weights["skills"],
            weight_problem_solving=weights["problem"],
            weight_role_fit=weights["role"],
            weight_work_style=weights["style"],
            shortlist_threshold=Decimal(str(request.POST.get("shortlist_threshold") or "70")),
            review_threshold=Decimal(str(request.POST.get("review_threshold") or "50")),
        )

        for requirement in must_requirements:
            JobRequirement.objects.create(job=job, text=requirement, requirement_type="must")
        for requirement in nice_requirements:
            JobRequirement.objects.create(job=job, text=requirement, requirement_type="nice")

        for order, item in enumerate(questions, start=1):
            prompt = (item.get("prompt") or "").strip()
            question_type = (item.get("question_type") or "").strip()
            if not prompt or not question_type:
                continue

            is_knockout = bool(item.get("is_knockout"))
            knockout_value = (item.get("knockout_value") or "").strip()
            ScreeningQuestion.objects.create(
                job=job,
                prompt=prompt,
                question_type=question_type,
                is_required=bool(item.get("is_required", True)),
                is_knockout=is_knockout,
                knockout_rule=(
                    {"operator": "equals", "value": knockout_value}
                    if is_knockout and knockout_value
                    else None
                ),
                bucket=(item.get("bucket") or "").strip(),
                order=order,
            )

        return redirect("job_pipeline", job_id=job.id)

    return render(
        request,
        "core/setup_job_v2.html",
        {
            "skill_list": SKILL_LIST,
            "active_nav": "setup",
        },
    )


def candidate_apply(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    questions = list(job.questions.all())

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        current_location = (request.POST.get("current_location") or "").strip()
        years_experience = request.POST.get("years_experience")
        notice_period_days = request.POST.get("notice_period_days")
        expected_salary = request.POST.get("expected_salary")

        candidate = Candidate.objects.create(
            job=job,
            full_name=full_name,
            email=email,
            phone=phone,
            current_location=current_location,
            years_experience=Decimal(str(years_experience)) if years_experience else None,
            notice_period_days=_to_int(notice_period_days, None) if notice_period_days else None,
            expected_salary=Decimal(str(expected_salary)) if expected_salary else None,
            consent_given=bool(request.POST.get("consent_given")),
        )

        resume_file = request.FILES.get("resume_file")
        resume_text = ""
        if resume_file:
            try:
                resume_text = extract_text_from_file(resume_file)
            except RuntimeError:
                messages.warning(
                    request,
                    "We saved your profile, but OCR is unavailable for this file type on the server.",
                )
            prepared_resume = prepare_text_for_analysis(resume_text)
            analyzed_resume_text = prepared_resume["translated_text"]
            CandidateResume.objects.create(
                candidate=candidate,
                file=resume_file,
                extracted_text=analyzed_resume_text,
            )
            resume_text = analyzed_resume_text

        precomputed = classify_job_requirements(job.description, job.skills)
        analysis = score_resume(
            job.description,
            resume_text,
            selected_skills=job.skills,
            precomputed=precomputed,
        )

        knockout_failed = False
        answered_by_bucket = {
            "problem_solving": [],
            "work_style": [],
            "skills_evidence": [],
            "role_fit": [],
        }

        for question in questions:
            answer_text = (request.POST.get(f"question_{question.id}") or "").strip()
            CandidateAnswer.objects.create(
                candidate=candidate,
                question=question,
                answer_text=answer_text,
            )
            if question.bucket in answered_by_bucket:
                answered_by_bucket[question.bucket].append(bool(answer_text))

            if question.is_knockout:
                passed = _evaluate_knockout(question, answer_text)
                KnockoutResult.objects.create(
                    candidate=candidate,
                    question=question,
                    passed=passed,
                    reason="" if passed else "Knockout rule not satisfied",
                )
                if not passed:
                    knockout_failed = True

        artifact_types = request.POST.getlist("artifact_type")
        artifact_urls = request.POST.getlist("artifact_url")
        artifact_notes = request.POST.getlist("artifact_notes")
        artifact_files = request.FILES.getlist("artifact_file")
        artifact_file_index = 0

        for idx, artifact_type in enumerate(artifact_types):
            artifact_type = (artifact_type or "").strip() or "other"
            artifact_url = (artifact_urls[idx] if idx < len(artifact_urls) else "").strip()
            artifact_note = (artifact_notes[idx] if idx < len(artifact_notes) else "").strip()
            artifact_file = artifact_files[artifact_file_index] if artifact_file_index < len(artifact_files) else None
            if artifact_file:
                artifact_file_index += 1

            if not artifact_url and not artifact_note and not artifact_file:
                continue
            CandidateArtifact.objects.create(
                candidate=candidate,
                artifact_type=artifact_type,
                url=artifact_url,
                notes=artifact_note,
                file=artifact_file,
            )

        config, _ = JobEvaluationConfig.objects.get_or_create(job=job)

        def _ratio_raw(bucket_key):
            answers = answered_by_bucket.get(bucket_key, [])
            if not answers:
                return Decimal("2.5")
            return Decimal("5.0") * Decimal(sum(1 for a in answers if a)) / Decimal(len(answers))

        raw_scores = {
            "skills_evidence": Decimal(str(round((analysis.get("overall_score", 0.0) * 5), 2))),
            "problem_solving": _ratio_raw("problem_solving"),
            "role_fit": Decimal(str(round((analysis.get("overall_score", 0.0) * 5), 2))),
            "work_style": _ratio_raw("work_style"),
        }

        weighted_scores = {
            "skills_evidence": _bucket_weighted_score(
                raw_scores["skills_evidence"], config.weight_skills_evidence
            ),
            "problem_solving": _bucket_weighted_score(
                raw_scores["problem_solving"], config.weight_problem_solving
            ),
            "role_fit": _bucket_weighted_score(raw_scores["role_fit"], config.weight_role_fit),
            "work_style": _bucket_weighted_score(raw_scores["work_style"], config.weight_work_style),
        }
        final_score = sum(weighted_scores.values())

        answered_required = 0
        total_required = 0
        missing_required_questions = []
        for q in questions:
            if q.is_required:
                total_required += 1
                if request.POST.get(f"question_{q.id}", "").strip():
                    answered_required += 1
                else:
                    missing_required_questions.append(q.prompt)
        answer_ratio = (answered_required / total_required) if total_required else 1.0

        knockout_results = list(candidate.knockout_results.select_related("question"))
        failed_knockouts = [result.question.prompt for result in knockout_results if not result.passed]

        if knockout_failed:
            recommendation = "no"
            final_score = Decimal("0.00")
            confidence = "medium"
        elif final_score >= config.shortlist_threshold:
            recommendation = "yes"
            confidence = "high" if answer_ratio >= 0.8 else "medium"
        elif final_score >= config.review_threshold:
            recommendation = "hold"
            confidence = "medium"
        else:
            recommendation = "no"
            confidence = "low"

        matched_skills = analysis.get("matched_skills", [])
        missing_skills = analysis.get("missing_skills", [])
        fit_summary = analysis.get("fit_summary", [])
        gap_analysis = analysis.get("gap_analysis", [])

        strengths = []
        if matched_skills:
            strengths.append(f"Matched skills: {', '.join(matched_skills[:8])}")
        if fit_summary:
            strengths.extend(fit_summary[:2])
        if answer_ratio >= 0.8:
            strengths.append("Most required screening questions were answered.")

        gaps = []
        if missing_skills:
            gaps.append(f"Missing skills: {', '.join(missing_skills[:8])}")
        if gap_analysis:
            gaps.extend(gap_analysis[:2])
        if failed_knockouts:
            gaps.append(f"Knockout failed: {failed_knockouts[0]}")

        missing_evidence = []
        if missing_required_questions:
            missing_evidence.append(
                f"Required answers missing: {min(len(missing_required_questions), 5)} question(s)."
            )
        if not candidate.artifacts.exists():
            missing_evidence.append("No portfolio/artifact evidence submitted.")
        if not strengths:
            strengths = ["Insufficient high-confidence evidence yet."]
        if not gaps:
            gaps = ["No major role-fit gaps identified from current signals."]
        if not missing_evidence:
            missing_evidence = ["No major missing evidence identified."]

        evaluation = CandidateEvaluation.objects.create(
            candidate=candidate,
            final_score=round(final_score, 2),
            confidence=confidence,
            recommendation=recommendation,
            strengths=strengths,
            gaps=gaps,
            missing_evidence=missing_evidence,
        )

        bucket_rationales = {
            "skills_evidence": (
                f"Resume skill alignment score derived from matched skills count ({len(matched_skills)} matched)."
            ),
            "problem_solving": (
                "Based on completion of problem-solving tagged screening answers."
            ),
            "role_fit": (
                "Blends role description similarity with requirement coverage and knockout outcomes."
            ),
            "work_style": (
                "Based on work-style question completion and response coverage quality."
            ),
        }
        for bucket, raw_score in raw_scores.items():
            BucketScore.objects.create(
                candidate_evaluation=evaluation,
                bucket=bucket,
                raw_score=round(raw_score, 1),
                weighted_score=round(weighted_scores[bucket], 2),
                rationale=bucket_rationales.get(
                    bucket,
                    "Auto-scored from resume signal and screening completion.",
                ),
            )

        return redirect("candidate_apply_success", job_id=job.id)

    return render(
        request,
        "core/candidate_apply.html",
        {
            "job": job,
            "questions": questions,
        },
    )


def candidate_apply_success(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    return render(request, "core/candidate_apply_success.html", {"job": job})


@login_required
def job_pipeline(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    search = (request.GET.get("search") or "").strip()
    recommendation_filter = (request.GET.get("recommendation") or "").strip()
    confidence_filter = (request.GET.get("confidence") or "").strip()

    candidates = (
        Candidate.objects.filter(job=job)
        .select_related("evaluation")
        .prefetch_related("knockout_results")
        .order_by("-evaluation__final_score", "-created_at")
    )
    if search:
        candidates = candidates.filter(
            Q(full_name__icontains=search) | Q(email__icontains=search)
        )
    if recommendation_filter in {"yes", "hold", "no"}:
        candidates = candidates.filter(evaluation__recommendation=recommendation_filter)
    if confidence_filter in {"low", "medium", "high"}:
        candidates = candidates.filter(evaluation__confidence=confidence_filter)

    metrics_qs = CandidateEvaluation.objects.filter(candidate__job=job)
    shortlist_count = metrics_qs.filter(recommendation="yes").count()
    hold_count = metrics_qs.filter(recommendation="hold").count()
    reject_count = metrics_qs.filter(recommendation="no").count()
    avg_score = round(
        sum(float(item.final_score) for item in metrics_qs) / metrics_qs.count(), 2
    ) if metrics_qs.exists() else 0

    cards = []
    for candidate in candidates:
        evaluation = getattr(candidate, "evaluation", None)
        knockout_results = list(candidate.knockout_results.all())
        knockout_failed = any(not item.passed for item in knockout_results)
        if knockout_failed:
            knockout_state = "Failed"
        elif knockout_results:
            knockout_state = "Passed"
        else:
            knockout_state = "Not set"

        strengths = evaluation.strengths if evaluation else []
        gaps = evaluation.gaps if evaluation else []
        cards.append(
            {
                "candidate": candidate,
                "evaluation": evaluation,
                "recommendation_key": evaluation.recommendation if evaluation else "",
                "primary_strength": strengths[0] if strengths else "No strength summary yet.",
                "primary_gap": gaps[0] if gaps else "No gap summary yet.",
                "knockout_state": knockout_state,
                "can_move": bool(evaluation),
            }
        )

    kanban = {
        "yes": [c for c in cards if c["recommendation_key"] == "yes"],
        "hold": [c for c in cards if c["recommendation_key"] == "hold"],
        "no": [c for c in cards if c["recommendation_key"] == "no"],
    }
    unscored_cards = [c for c in cards if c["recommendation_key"] not in {"yes", "hold", "no"}]

    return render(
        request,
        "core/job_pipeline.html",
        {
            "job": job,
            "candidates": candidates,
            "search": search,
            "recommendation_filter": recommendation_filter,
            "confidence_filter": confidence_filter,
            "shortlist_count": shortlist_count,
            "hold_count": hold_count,
            "reject_count": reject_count,
            "avg_score": avg_score,
            "cards": cards,
            "kanban": kanban,
            "unscored_cards": unscored_cards,
            "active_nav": "pipeline",
            "apply_url": request.build_absolute_uri(
                reverse("candidate_apply", kwargs={"job_id": job.id})
            ),
        },
    )


@login_required
def candidate_detail(request, job_id, candidate_id):
    job = get_object_or_404(Job, id=job_id)
    candidate = get_object_or_404(
        Candidate.objects.select_related("evaluation").prefetch_related(
            "answers__question",
            "artifacts",
            "knockout_results__question",
            "evaluation__bucket_scores",
        ),
        id=candidate_id,
        job=job,
    )
    evaluation = getattr(candidate, "evaluation", None)
    bucket_scores = evaluation.bucket_scores.all().order_by("-weighted_score") if evaluation else []
    candidate_resume = CandidateResume.objects.filter(candidate=candidate).first()

    if request.method == "POST" and evaluation:
        new_recommendation = (request.POST.get("recommendation") or "").strip()
        if new_recommendation in {"yes", "hold", "no"}:
            evaluation.recommendation = new_recommendation
            evaluation.save(update_fields=["recommendation"])
            messages.success(request, "Recommendation updated successfully.")
            return redirect("candidate_detail", job_id=job.id, candidate_id=candidate.id)

    return render(
        request,
        "core/candidate_detail.html",
        {
            "job": job,
            "candidate": candidate,
            "candidate_resume": candidate_resume,
            "evaluation": evaluation,
            "bucket_scores": bucket_scores,
            "answers": candidate.answers.all().order_by("question__order", "question__id"),
            "artifacts": candidate.artifacts.all(),
            "knockout_results": candidate.knockout_results.all().order_by("id"),
            "active_nav": "pipeline",
        },
    )


@login_required
@require_POST
def update_candidate_recommendation(request, job_id, candidate_id):
    job = get_object_or_404(Job, id=job_id)
    candidate = get_object_or_404(Candidate.objects.select_related("evaluation"), id=candidate_id, job=job)
    evaluation = getattr(candidate, "evaluation", None)
    if not evaluation:
        return JsonResponse({"ok": False, "error": "Candidate has no evaluation yet."}, status=400)

    payload = request.POST
    content_type = request.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON payload."}, status=400)

    recommendation = str(payload.get("recommendation", "")).strip()
    if recommendation not in {"yes", "hold", "no"}:
        return JsonResponse({"ok": False, "error": "Invalid recommendation value."}, status=400)

    evaluation.recommendation = recommendation
    evaluation.save(update_fields=["recommendation"])
    return JsonResponse(
        {
            "ok": True,
            "recommendation": recommendation,
            "recommendation_display": evaluation.get_recommendation_display(),
        }
    )

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
        if analysis["must_skills"] and not analysis["missing_skills"]:
            shortlisted.append(r)
        elif r.similarity_score >= 0.75:
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
