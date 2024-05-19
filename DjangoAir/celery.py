import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoAir.settings')

app = Celery('DjangoAir')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
