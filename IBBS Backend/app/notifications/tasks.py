from app.celery_app import celery_app
from celery.utils.log import get_task_logger
from app.services.notification_service import notification_service, NOTIF_COUNTER_RETRIED
from app.services.notification_providers import LogProvider
from app.redis_client import redis_client
import asyncio

logger = get_task_logger(__name__)

DLQ_KEY = "notification_dlq"


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600, retry_jitter=True, max_retries=3)
def send_notification_task(self, channel: str, to: str, template_name: str, context: dict = None, locale: str = "en", provider_name: str = "log"):
    """Channel: 'email' or 'sms'. This task retries on failure; when retries exhausted it writes to DLQ in Redis."""
    # NOTE: Celery tasks are synchronous by default here; run async calls via asyncio
    async def _do():
        # provider selection (we only have LogProvider in this scaffold)
        provider = LogProvider()
        # temporary: create a NotificationService that uses provider instance
        svc = notification_service
        svc.provider = provider

        if channel == "email":
            await svc.send_email(to=to, subject=context.get('subject',''), template_name=template_name, context=context, locale=locale)
        else:
            await svc.send_sms(to=to, template_name=template_name, context=context, locale=locale)

    try:
        asyncio.get_event_loop().run_until_complete(_do())
    except self.MaxRetriesExceededError:
        # move to DLQ
        logger.error("Max retries exceeded for notification to %s; sending to DLQ", to)
        redis_client.rpush(DLQ_KEY, str({"channel": channel, "to": to, "template": template_name, "context": context, "locale": locale}))
        raise
    except Exception as exc:
        # increment retry metric
        NOTIF_COUNTER_RETRIED.labels(channel=channel, provider=provider_name).inc()
        logger.exception("Error sending notification: %s", exc)
        raise self.retry(exc=exc)
