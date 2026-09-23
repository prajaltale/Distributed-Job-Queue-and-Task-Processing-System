import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # tell Celery which Django settings file to load

app = Celery('config')  # create the Celery application, named after this project

app.config_from_object('django.conf:settings', namespace='CELERY')  # read any CELERY_* variables from settings.py

app.autodiscover_tasks()  # automatically scan every installed app for a tasks.py file