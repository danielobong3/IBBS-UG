from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.schemas.payment import PaymentInitiateRequest, PaymentInitiateResponse, WebhookAck
from app.services.payment_gateway import get_adapter, mark_event_processed, is_event_processed
from app.metrics import PAYMENT_SUCCESS, PAYMENT_FAILURE
from app.models.models import Payment, Booking
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select as sa_select
from datetime import datetime

router = APIRouter()


@router.get("/")
async def payments_root():
    return {"module": "payments", "status": "ok"}


@router.post("/initiate", response_model=PaymentInitiateResponse)
async def initiate_payment(req: PaymentInitiateRequest, db: AsyncSession = Depends(get_session)):
    adapter = await get_adapter(req.provider)
    # create a Payment record with status initiated
    provider_resp = await adapter.initiate(req.booking_id, req.amount, req.currency)
    provider_ref = provider_resp.get("provider_ref")

    payment = Payment(
        booking_id=req.booking_id if hasattr(Payment, 'booking_id') else None,
        amount=req.amount,
        currency=req.currency,
        provider=req.provider,
        provider_ref=provider_ref,
        status="initiated",
    )
    try:
        async with db.begin():
            db.add(payment)
    except IntegrityError:
        raise HTTPException(status_code=500, detail="Unable to create payment record")

    return PaymentInitiateResponse(provider=req.provider, provider_ref=provider_ref, checkout_url=provider_resp.get("checkout_url"))


@router.post("/webhook/{provider}", response_model=WebhookAck)
async def payment_webhook(provider: str, request: Request, db: AsyncSession = Depends(get_session)):
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    adapter = await get_adapter(provider)

    # verify signature
    valid = await adapter.verify_signature(headers, body)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # parse event
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # extract an event id unique to provider; try common fields
    event_id = payload.get("id") or payload.get("event_id") or payload.get("tx_id") or payload.get("transaction_id")
    if not event_id:
        # fallback to provider_ref if present
        event_id = payload.get("data", {}).get("id") or payload.get("data", {}).get("tx_ref")
    if not event_id:
        # cannot deduplicate without id
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing event id for idempotency")

    # check idempotency/replay
    processed = await is_event_processed(provider, str(event_id))
    if processed:
        return WebhookAck(received=True)

    # basic normalization for common providers
    status_str = None
    provider_ref = None
    amount = None
    if provider.lower() == "flutterwave":
        data = payload.get("data", {})
        status_str = data.get("status")
        provider_ref = data.get("tx_ref") or data.get("flw_ref")
        amount = data.get("amount")
    else:
        # MTN/Airtel simulation: expect a top-level object
        data = payload.get("data") or payload
        status_str = data.get("status") or data.get("transaction_status")
        provider_ref = data.get("transaction_id") or data.get("tx_ref")
        amount = data.get("amount")

    # mark event as being processed (idempotency store)
    added = await mark_event_processed(provider, str(event_id))
    if not added:
        # race: someone else processed
        return WebhookAck(received=True)

    # transactional update: create/update Payment and update Booking state
    try:
        async with db.begin():
            # try to locate payment by provider_ref
            stmt = sa_select(Payment).where(Payment.provider_ref == provider_ref)
            res = await db.execute(stmt)
            pay = res.scalars().first()
            if not pay:
                pay = Payment(
                    booking_id=None,
                    amount=amount or 0,
                    currency=getattr(Payment, 'currency', 'UGX'),
                    provider=provider,
                    provider_ref=provider_ref,
                    status=status_str or 'unknown',
                )
                db.add(pay)
            else:
                pay.status = status_str or pay.status

            # normalize status checks
            lcstatus = (status_str or '').lower()

            # if payment succeeded, mark booking as paid
            if lcstatus in ("successful", "success", "paid", "completed"):
                # find booking via payment.booking_id
                booking = None
                if pay.booking_id:
                    stmt_b = sa_select(Booking).where(Booking.id == pay.booking_id)
                    resb = await db.execute(stmt_b)
                    booking = resb.scalars().first()

                if booking:
                    booking.status = "paid"
                PAYMENT_SUCCESS.labels(provider=provider).inc()

            # if payment failed, cancel booking and release seat
            elif lcstatus in ("failed", "failed_attempt", "error", "declined", "cancelled"):
                booking = None
                if pay.booking_id:
                    stmt_b = sa_select(Booking).where(Booking.id == pay.booking_id)
                    resb = await db.execute(stmt_b)
                    booking = resb.scalars().first()

                if booking:
                    # mark booking cancelled
                    booking.status = "cancelled"
                    # increment seats_available on trip
                    if booking.trip_id:
                        upd = sa_update(Booking.__table__.metadata.tables['trips']).where(Booking.__table__.metadata.tables['trips'].c.id == booking.trip_id).values(seats_available=(Booking.__table__.metadata.tables['trips'].c.seats_available + 1))
                        # execute raw update
                        await db.execute(upd)
                    # attempt to release any lock (best-effort)
                    try:
                        from app.services.seat_lock import release_lock

                        await release_lock(booking.trip_id, booking.seat_id, token=None)
                    except Exception:
                        pass
                PAYMENT_FAILURE.labels(provider=provider).inc()
            else:
                # unknown/transient statuses: increment failure metric for observability
                PAYMENT_FAILURE.labels(provider=provider).inc()
                # Optionally: create ticket here

    except Exception as exc:
        # Rollback handled by context manager; ensure event key is cleared? Keep it to avoid replayers causing repeated DB errors.
        raise HTTPException(status_code=500, detail=str(exc))

    return WebhookAck(received=True)
