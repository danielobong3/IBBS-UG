import hmac
import hashlib
import json
from typing import Dict, Optional
from uuid import uuid4
from urllib.parse import urlencode

from app.config import settings
from app.redis_client import redis_client
from app.metrics import PAYMENT_SUCCESS, PAYMENT_FAILURE


class PaymentError(Exception):
    pass


class BaseAdapter:
    provider_name: str = "base"

    async def initiate(self, booking_id: int, amount: float, currency: str) -> Dict:
        raise NotImplementedError()

    async def verify_signature(self, headers: Dict[str, str], body: bytes) -> bool:
        # default: HMAC-SHA256 using provider secret configured in settings
        secret = self.get_secret()
        if not secret:
            return False
        sig_header = headers.get("x-signature") or headers.get("x-flutterwave-signature") or ""
        computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, sig_header)

    def get_secret(self) -> Optional[str]:
        return ""


class FlutterwaveAdapter(BaseAdapter):
    provider_name = "flutterwave"

    def get_secret(self) -> Optional[str]:
        return settings.FLUTTERWAVE_SECRET

    async def initiate(self, booking_id: int, amount: float, currency: str) -> Dict:
        # In production you'd call Flutterwave API. Here we simulate a checkout URL and provider_ref
        provider_ref = f"flw_{uuid4().hex}"
        checkout_url = f"https://flutterwave.com/pay/{provider_ref}?{urlencode({'amount': amount, 'currency': currency})}"
        return {"provider": self.provider_name, "provider_ref": provider_ref, "checkout_url": checkout_url}


class MTNAdapter(BaseAdapter):
    provider_name = "mtn"

    def get_secret(self) -> Optional[str]:
        return settings.MTN_SECRET

    async def initiate(self, booking_id: int, amount: float, currency: str) -> Dict:
        provider_ref = f"mtn_{uuid4().hex}"
        # MTN typically does a push to customer's wallet; return simulated ref
        return {"provider": self.provider_name, "provider_ref": provider_ref, "checkout_url": None}


class AirtelAdapter(BaseAdapter):
    provider_name = "airtel"

    def get_secret(self) -> Optional[str]:
        return settings.AIRTEL_SECRET

    async def initiate(self, booking_id: int, amount: float, currency: str) -> Dict:
        provider_ref = f"airtel_{uuid4().hex}"
        return {"provider": self.provider_name, "provider_ref": provider_ref, "checkout_url": None}


ADAPTERS = {
    "flutterwave": FlutterwaveAdapter(),
    "mtn": MTNAdapter(),
    "airtel": AirtelAdapter(),
}


async def get_adapter(name: str) -> BaseAdapter:
    ad = ADAPTERS.get(name.lower())
    if not ad:
        raise PaymentError(f"Unknown provider: {name}")
    return ad


IDEMPOTENCY_KEY_TPL = "payment_webhook:{provider}:{event_id}"


async def mark_event_processed(provider: str, event_id: str, ttl: int = 60 * 60 * 24) -> bool:
    key = IDEMPOTENCY_KEY_TPL.format(provider=provider, event_id=event_id)
    # set NX to ensure we only process once
    added = await redis_client.set(key, "1", ex=ttl, nx=True)
    return bool(added)


async def is_event_processed(provider: str, event_id: str) -> bool:
    key = IDEMPOTENCY_KEY_TPL.format(provider=provider, event_id=event_id)
    return await redis_client.exists(key)
