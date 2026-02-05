from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("upload-job/", views.upload_job, name="upload_job"),
    path("upload-resumes/<int:job_id>/", views.upload_resumes, name="upload_resumes"),
    path("results/<int:job_id>/", views.results, name="results"),
]
