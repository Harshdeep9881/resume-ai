from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Candidate,
    CandidateEvaluation,
    CandidateResume,
    Job,
    JobEvaluationConfig,
    Resume,
)


def compute_default_recommendation(final_score, shortlist_threshold, review_threshold):
    if final_score >= shortlist_threshold:
        return "yes"
    if final_score >= review_threshold:
        return "hold"
    return "no"


class Command(BaseCommand):
    help = "Backfill Candidate/CandidateResume/CandidateEvaluation records from existing Resume rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            type=int,
            help="Backfill only for a single Job id.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show counts without writing records.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        job_id = options.get("job_id")
        dry_run = options.get("dry_run")

        jobs = Job.objects.all().order_by("id")
        if job_id:
            jobs = jobs.filter(id=job_id)

        if not jobs.exists():
            self.stdout.write(self.style.WARNING("No matching jobs found."))
            return

        created_candidates = 0
        created_resumes = 0
        created_evaluations = 0
        skipped = 0

        missing_file_count = 0

        for job in jobs:
            config, _ = JobEvaluationConfig.objects.get_or_create(job=job)
            legacy_resumes = Resume.objects.filter(job=job).order_by("id")

            for legacy in legacy_resumes:
                filename = Path(legacy.file.name).name if legacy.file else f"resume_{legacy.id}"
                candidate_name = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
                candidate_name = candidate_name or f"Candidate {legacy.id}"
                synthetic_email = f"legacy+job{job.id}-resume{legacy.id}@example.local"

                candidate_defaults = {
                    "full_name": candidate_name[:255],
                    "phone": "",
                    "current_location": "",
                    "consent_given": False,
                }

                if dry_run:
                    created_candidates += 1
                    created_resumes += 1
                    created_evaluations += 1
                    continue

                candidate, candidate_created = Candidate.objects.get_or_create(
                    job=job,
                    email=synthetic_email,
                    defaults=candidate_defaults,
                )
                if candidate_created:
                    created_candidates += 1
                else:
                    skipped += 1
                    continue

                candidate_resume, resume_created = CandidateResume.objects.get_or_create(
                    candidate=candidate,
                    defaults={
                        "extracted_text": legacy.extracted_text,
                    },
                )
                if resume_created:
                    if legacy.file:
                        try:
                            with legacy.file.open("rb") as fp:
                                candidate_resume.file.save(filename, File(fp), save=True)
                        except FileNotFoundError:
                            missing_file_count += 1
                            candidate_resume.file = legacy.file.name
                            candidate_resume.save(update_fields=["file"])
                    created_resumes += 1

                final_score = Decimal(str(round((legacy.similarity_score or 0.0) * 100, 2)))
                recommendation = compute_default_recommendation(
                    final_score,
                    config.shortlist_threshold,
                    config.review_threshold,
                )

                _, eval_created = CandidateEvaluation.objects.get_or_create(
                    candidate=candidate,
                    defaults={
                        "final_score": final_score,
                        "confidence": "low",
                        "recommendation": recommendation,
                        "strengths": [],
                        "gaps": ["Backfilled from legacy resume flow"],
                        "missing_evidence": ["Candidate questionnaire not completed"],
                    },
                )
                if eval_created:
                    created_evaluations += 1

        if dry_run:
            transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("Backfill completed."))
        self.stdout.write(f"Candidates created: {created_candidates}")
        self.stdout.write(f"Candidate resumes created: {created_resumes}")
        self.stdout.write(f"Candidate evaluations created: {created_evaluations}")
        self.stdout.write(f"Skipped existing candidates: {skipped}")
        self.stdout.write(f"Missing legacy files encountered: {missing_file_count}")
