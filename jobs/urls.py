from django.urls import path
from .views import JobCreateView, JobStatusView

urlpatterns = [
    path('jobs/', JobCreateView.as_view(), name='job-create'),           # POST to create a job
    path('jobs/<uuid:pk>/', JobStatusView.as_view(), name='job-status'), # GET to check status
]