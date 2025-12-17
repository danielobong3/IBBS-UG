from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update as sa_update
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.schemas.booking import (
    LockSeatRequest,
    LockSeatResponse,
    ConfirmBookingRequest,
    BookingResponse,
    ReleaseLockRequest,
)
from app.services.seat_lock import lock_seat, validate_and_consume_lock, release_lock
from app.db.session import get_session
import app.models.models as models

router = APIRouter()


@router.get("/")
async def bookings_root():
    return {"module": "bookings", "status": "ok"}


@router.post("/locks/lock", response_model=LockSeatResponse)
async def create_lock(req: LockSeatRequest):
    """Lock a seat in Redis for a short TTL and return a token."""
    res = await lock_seat(req.trip_id, req.seat_id, ttl=req.ttl)
    if not res:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Seat already locked")
    return LockSeatResponse(token=res["token"], expires_at=res["expires_at"])


@router.post("/locks/confirm", response_model=BookingResponse)
async def confirm_booking(req: ConfirmBookingRequest, db: AsyncSession = Depends(get_session)):
    """Confirm booking by validating lock token and creating booking transactionally."""
    # validate and atomically consume lock
    ok = await validate_and_consume_lock(req.trip_id, req.seat_id, req.token)
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invalid or expired lock token")

    # perform transactional booking; rely on DB unique constraint to avoid double-booking
    booking = models.Booking(
        user_id=req.user_id,
        trip_id=req.trip_id,
        seat_id=req.seat_id,
        status="confirmed",
        total_amount=0,
    )

    try:
        async with db.begin():
            # decrement seats_available atomically if > 0
            upd = (
                sa_update(models.Trip)
                .where(models.Trip.id == req.trip_id)
                .where(models.Trip.seats_available > 0)
                .values(seats_available=(models.Trip.seats_available - 1))
            )
            result = await db.execute(upd)
            if result.rowcount == 0:
                # no seats available, rollback
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No seats available")

            db.add(booking)

        # committed
    except IntegrityError:
        # violation of unique constraint (trip+seat) => already booked
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Seat already booked")

    await db.refresh(booking)

    return BookingResponse(
        booking_id=booking.id,
        trip_id=booking.trip_id,
        seat_id=booking.seat_id,
        status=booking.status,
        booked_at=booking.booked_at,
    )


@router.post("/locks/release")
async def release_lock_endpoint(req: ReleaseLockRequest):
    """Release a lock. If token provided, will only release when token matches. Otherwise unconditional release."""
    ok = await release_lock(req.trip_id, req.seat_id, token=req.token)
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Token mismatch or lock not owned")
    return {"released": True}
