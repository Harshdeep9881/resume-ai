from django.db import models

class Job(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    skills = models.JSONField(blank=True, null=True)
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
