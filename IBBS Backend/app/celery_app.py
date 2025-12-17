from celery import Celery
from app.config import settings


celery_app = Celery(
    "ibbs_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(task_track_started=True)
