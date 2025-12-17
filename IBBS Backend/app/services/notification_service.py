from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import Dict, Optional
from app.services.notification_providers import LogProvider, NotificationProvider
from app.redis_client import redis_client
from datetime import datetime
from prometheus_client import Counter
import logging

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "notifications" / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml", "txt"]),
)

# metrics
NOTIF_COUNTER_SENT = Counter("ibbs_notifications_sent_total", "Total notifications sent", ["channel", "provider"])
NOTIF_COUNTER_FAILED = Counter("ibbs_notifications_failed_total", "Total notification failures", ["channel", "provider"])
NOTIF_COUNTER_RETRIED = Counter("ibbs_notifications_retried_total", "Total notification retries", ["channel", "provider"])


class NotificationService:
    def __init__(self, provider: Optional[NotificationProvider] = None):
        self.provider = provider or LogProvider()

    def render(self, template_name: str, locale: str = "en", context: Dict = None) -> str:
        ctx = context or {}
        # try locale-specific template, fallback to en
        tpl_candidates = [f"{locale}/{template_name}", f"en/{template_name}"]
        for tpl in tpl_candidates:
            try:
                template = _env.get_template(tpl)
                return template.render(**ctx)
            except Exception:
                continue
        raise RuntimeError("Template not found: %s" % template_name)

    async def send_email(self, to: str, subject: str, template_name: str, context: Dict = None, locale: str = "en", meta: Dict = None):
        body = self.render(template_name, locale=locale, context=context)
        try:
            res = await self.provider.send_email(to=to, subject=subject, body=body, meta=meta)
            NOTIF_COUNTER_SENT.labels(channel="email", provider=getattr(self.provider, '__class__').__name__).inc()
            return res
        except Exception as exc:
            NOTIF_COUNTER_FAILED.labels(channel="email", provider=getattr(self.provider, '__class__').__name__).inc()
            logger.exception("Email send failed")
            raise

    async def send_sms(self, to: str, template_name: str, context: Dict = None, locale: str = "en", meta: Dict = None):
        body = self.render(template_name, locale=locale, context=context)
        try:
            res = await self.provider.send_sms(to=to, body=body, meta=meta)
            NOTIF_COUNTER_SENT.labels(channel="sms", provider=getattr(self.provider, '__class__').__name__).inc()
            return res
        except Exception as exc:
            NOTIF_COUNTER_FAILED.labels(channel="sms", provider=getattr(self.provider, '__class__').__name__).inc()
            logger.exception("SMS send failed")
            raise


notification_service = NotificationService()
