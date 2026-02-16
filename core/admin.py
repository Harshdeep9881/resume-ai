from django.contrib import admin
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

admin.site.register(Job)
admin.site.register(Resume)
admin.site.register(JobEvaluationConfig)
admin.site.register(JobRequirement)
admin.site.register(ScreeningQuestion)
admin.site.register(Candidate)
admin.site.register(CandidateResume)
admin.site.register(CandidateArtifact)
admin.site.register(CandidateAnswer)
admin.site.register(KnockoutResult)
admin.site.register(CandidateEvaluation)
admin.site.register(BucketScore)
