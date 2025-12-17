from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LockSeatRequest(BaseModel):
    trip_id: int
    seat_id: int
    user_id: Optional[int] = None
    ttl: Optional[int] = Field(300, description="Lock TTL in seconds")


class LockSeatResponse(BaseModel):
    token: str
    expires_at: datetime


class ConfirmBookingRequest(BaseModel):
    trip_id: int
    seat_id: int
    token: str
    user_id: Optional[int] = None


class ReleaseLockRequest(BaseModel):
    trip_id: int
    seat_id: int
    token: Optional[str] = None


class BookingResponse(BaseModel):
    booking_id: int
    trip_id: int
    seat_id: int
    status: str
    booked_at: datetime
