from .celery import app as celery_app  # this import runs celery.py the moment Django starts

__all__ = ('celery_app',) # explicitly marks celery_app as available for import elsewhere