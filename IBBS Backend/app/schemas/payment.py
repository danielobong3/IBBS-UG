from pydantic import BaseModel, Field
from typing import Optional


class PaymentInitiateRequest(BaseModel):
    booking_id: int
    provider: str = Field(..., description="one of: flutterwave, mtn, airtel")
    amount: float
    currency: Optional[str] = "UGX"


class PaymentInitiateResponse(BaseModel):
    provider: str
    provider_ref: str
    checkout_url: Optional[str] = None


class WebhookAck(BaseModel):
    received: bool
