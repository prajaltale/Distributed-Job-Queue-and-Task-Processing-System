from rest_framework import generics
from .models import Job
from .serializers import JobSerializer
from .tasks import process_job

class JobCreateView(generics.CreateAPIView):
    queryset = Job.objects.all() # the table this view works with
    serializer_class = JobSerializer # how incoming/Outgoing data is converted

    def perform_create(self, serializer):
        job = serializer.save()     # save the job first - status defaults to 'pending'
        process_job.delay(job.id)   # hand off to Celery, runs later in the background  


class JobStatusView(generics.RetrieveAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer