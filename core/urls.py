from django.urls import path
from core import views

urlpatterns = [
    path('', views.home, name="home"),
    path('upload-job/', views.upload_job, name="upload_job"),
    path('upload-resumes/<int:job_id>/', views.upload_resumes, name="upload_resumes"),
    path('setup-job-v2/', views.setup_job_v2, name="setup_job_v2"),
    path('apply/<int:job_id>/', views.candidate_apply, name="candidate_apply"),
    path('apply/<int:job_id>/success/', views.candidate_apply_success, name="candidate_apply_success"),
    path('pipeline/<int:job_id>/', views.job_pipeline, name="job_pipeline"),
    path('pipeline/<int:job_id>/candidate/<int:candidate_id>/', views.candidate_detail, name="candidate_detail"),
    path(
        'pipeline/<int:job_id>/candidate/<int:candidate_id>/recommendation/',
        views.update_candidate_recommendation,
        name="update_candidate_recommendation",
    ),
    path('dashboard/<int:job_id>/', views.dashboard, name="dashboard"),
    path('results/<int:job_id>/', views.results, name="results"),
    path('compare/<int:job_id>/', views.compare_candidates, name="compare_candidates"),
    path('download-excel/<int:job_id>/', views.download_excel, name="download_excel"),
]
