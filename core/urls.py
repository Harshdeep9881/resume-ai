from django.urls import path
from core import views

urlpatterns = [
    path('', views.home, name="home"),
    path('upload-job/', views.upload_job, name="upload_job"),
    path('upload-resumes/<int:job_id>/', views.upload_resumes, name="upload_resumes"),
    path('dashboard/<int:job_id>/', views.dashboard, name="dashboard"),
    path('results/<int:job_id>/', views.results, name="results"),
    path('download-excel/<int:job_id>/', views.download_excel, name="download_excel"),
]
