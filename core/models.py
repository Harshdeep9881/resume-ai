from django.contrib.auth.models import User
from django.db import models

class Job(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    skills = models.JSONField(blank=True, null=True)
    location = models.CharField(max_length=120, blank=True)
    employment_type = models.CharField(max_length=40, blank=True)
    min_experience_years = models.PositiveSmallIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Resume(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="resumes")
    file = models.FileField(upload_to="resumes/")
    extracted_text = models.TextField(blank=True, null=True)
    similarity_score = models.FloatField(default=0.0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


class JobEvaluationConfig(models.Model):
    job = models.OneToOneField(
        Job, on_delete=models.CASCADE, related_name="evaluation_config"
    )
    weight_skills_evidence = models.PositiveSmallIntegerField(default=25)
    weight_problem_solving = models.PositiveSmallIntegerField(default=30)
    weight_role_fit = models.PositiveSmallIntegerField(default=30)
    weight_work_style = models.PositiveSmallIntegerField(default=15)
    shortlist_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=70.00)
    review_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)

    def __str__(self):
        return f"Evaluation Config: {self.job.title}"


class JobRequirement(models.Model):
    REQUIREMENT_TYPE_CHOICES = [("must", "Must"), ("nice", "Nice")]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="requirements")
    text = models.CharField(max_length=255)
    requirement_type = models.CharField(
        max_length=10, choices=REQUIREMENT_TYPE_CHOICES, default="must"
    )

    def __str__(self):
        return f"{self.job.title} - {self.requirement_type}: {self.text}"


class ScreeningQuestion(models.Model):
    QUESTION_TYPE_CHOICES = [
        ("knockout_bool", "Knockout Bool"),
        ("single_choice", "Single Choice"),
        ("multi_choice", "Multi Choice"),
        ("short_text", "Short Text"),
        ("long_text", "Long Text"),
        ("number", "Number"),
        ("file", "File Upload"),
        ("url", "URL"),
    ]
    BUCKET_CHOICES = [
        ("skills_evidence", "Skills Evidence"),
        ("problem_solving", "Problem Solving"),
        ("role_fit", "Role Fit"),
        ("work_style", "Work Style"),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="questions")
    prompt = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    is_required = models.BooleanField(default=True)
    is_knockout = models.BooleanField(default=False)
    knockout_rule = models.JSONField(null=True, blank=True)
    bucket = models.CharField(max_length=25, choices=BUCKET_CHOICES, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.job.title}: {self.prompt[:50]}"


class Candidate(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="candidates")
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    current_location = models.CharField(max_length=120, blank=True)
    years_experience = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    notice_period_days = models.PositiveSmallIntegerField(null=True, blank=True)
    expected_salary = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    consent_given = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["job", "email"])]

    def __str__(self):
        return f"{self.full_name} ({self.job.title})"


class CandidateResume(models.Model):
    candidate = models.OneToOneField(
        Candidate, on_delete=models.CASCADE, related_name="resume"
    )
    file = models.FileField(upload_to="resumes/")
    extracted_text = models.TextField(blank=True, null=True)
    parsed_json = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.file.name


class CandidateArtifact(models.Model):
    ARTIFACT_TYPE_CHOICES = [
        ("portfolio", "Portfolio"),
        ("github", "GitHub"),
        ("case_study", "Case Study"),
        ("loom", "Loom"),
        ("other", "Other"),
    ]

    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="artifacts"
    )
    artifact_type = models.CharField(max_length=20, choices=ARTIFACT_TYPE_CHOICES)
    url = models.URLField(blank=True)
    file = models.FileField(upload_to="artifacts/", blank=True, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.candidate.full_name} - {self.artifact_type}"


class CandidateAnswer(models.Model):
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        ScreeningQuestion, on_delete=models.CASCADE, related_name="answers"
    )
    answer_text = models.TextField(blank=True)
    answer_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("candidate", "question")

    def __str__(self):
        return f"{self.candidate.full_name} - Q{self.question.id}"


class KnockoutResult(models.Model):
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="knockout_results"
    )
    question = models.ForeignKey(ScreeningQuestion, on_delete=models.CASCADE)
    passed = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.candidate.full_name} - {'Pass' if self.passed else 'Fail'}"


class CandidateEvaluation(models.Model):
    RECOMMENDATION_CHOICES = [("yes", "Yes"), ("hold", "Hold"), ("no", "No")]
    CONFIDENCE_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]

    candidate = models.OneToOneField(
        Candidate, on_delete=models.CASCADE, related_name="evaluation"
    )
    final_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    confidence = models.CharField(
        max_length=10, choices=CONFIDENCE_CHOICES, default="medium"
    )
    recommendation = models.CharField(
        max_length=10, choices=RECOMMENDATION_CHOICES, default="hold"
    )
    strengths = models.JSONField(default=list, blank=True)
    gaps = models.JSONField(default=list, blank=True)
    missing_evidence = models.JSONField(default=list, blank=True)
    evaluated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.candidate.full_name} - {self.final_score}"


class BucketScore(models.Model):
    BUCKET_CHOICES = [
        ("skills_evidence", "Skills Evidence"),
        ("problem_solving", "Problem Solving"),
        ("role_fit", "Role Fit"),
        ("work_style", "Work Style"),
    ]

    candidate_evaluation = models.ForeignKey(
        CandidateEvaluation,
        on_delete=models.CASCADE,
        related_name="bucket_scores",
    )
    bucket = models.CharField(max_length=25, choices=BUCKET_CHOICES)
    raw_score = models.DecimalField(max_digits=3, decimal_places=1)
    weighted_score = models.DecimalField(max_digits=5, decimal_places=2)
    rationale = models.TextField(blank=True)

    class Meta:
        unique_together = ("candidate_evaluation", "bucket")

    def __str__(self):
        return f"{self.candidate_evaluation.candidate.full_name} - {self.bucket}"
