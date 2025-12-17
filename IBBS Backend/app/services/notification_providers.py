from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    """Abstract provider for notifications (email/sms)."""

    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str, meta: Optional[Dict] = None) -> Dict:
        raise NotImplementedError()

    @abstractmethod
    async def send_sms(self, to: str, body: str, meta: Optional[Dict] = None) -> Dict:
        raise NotImplementedError()


class LogProvider(NotificationProvider):
    """Simple provider that logs messages (useful for dev/testing)."""

    async def send_email(self, to: str, subject: str, body: str, meta: Optional[Dict] = None) -> Dict:
        logger.info("[LogProvider] Sending email to %s subject=%s", to, subject)
        logger.debug("Email body: %s", body)
        return {"status": "sent", "provider": "log"}

    async def send_sms(self, to: str, body: str, meta: Optional[Dict] = None) -> Dict:
        logger.info("[LogProvider] Sending SMS to %s", to)
        logger.debug("SMS body: %s", body)
        return {"status": "sent", "provider": "log"}


# TODO: Add real providers (Twilio, SMTP, MSG91, AfricasTalking, etc.)
