from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("ticketing", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Repeatable jobs (replaces the need for a separate "celery beat" container's schedule file)
celery_app.conf.beat_schedule = {
    "check-sla-and-overdue-tickets": {
        "task": "app.tasks.check_overdue_tickets",
        "schedule": crontab(minute=0, hour="*/6"),  # every 6 hours
    },
}

celery_app.autodiscover_tasks(["app"])
