from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select, update as sa_update
from app.db.session import get_session
from app.auth.deps import role_required, get_current_user
from app.models.models import Operator, Bus, Trip, Booking, Payment
from app.services.audit import log_audit
from datetime import datetime

router = APIRouter()


@router.get("/")
async def admin_root():
    return {"module": "admin", "status": "ok"}


# Fleet management: operators
@router.post("/operators", dependencies=[Depends(role_required(["Admin", "OperatorManager"]))])
async def create_operator(name: str, contact_email: Optional[str] = None, contact_phone: Optional[str] = None, db: AsyncSession = Depends(get_session), current_user=Depends(get_current_user)):
    op = Operator(name=name, contact_email=contact_email, contact_phone=contact_phone)
    async with db.begin():
        db.add(op)
        await log_audit(db, actor_id=current_user.id, action="create_operator", object_type="operator", object_id=str(name), detail={"email": contact_email, "phone": contact_phone})
    return {"operator_id": op.id, "name": op.name}


@router.get("/operators", dependencies=[Depends(role_required(["Admin", "OperatorManager"]))])
async def list_operators(db: AsyncSession = Depends(get_session)):
    stmt = sa_select(Operator)
    res = await db.execute(stmt)
    ops = [dict(id=o.id, name=o.name, contact_email=o.contact_email) for o in res.scalars().all()]
    return ops


@router.post("/buses", dependencies=[Depends(role_required(["Admin", "OperatorManager"]))])
async def create_bus(operator_id: int, registration_number: str, capacity: int = 0, model: Optional[str] = None, db: AsyncSession = Depends(get_session), current_user=Depends(get_current_user)):
    bus = Bus(operator_id=operator_id, registration_number=registration_number, capacity=capacity, model=model)
    async with db.begin():
        db.add(bus)
        await log_audit(db, actor_id=current_user.id, action="create_bus", object_type="bus", object_id=registration_number, detail={"operator_id": operator_id, "capacity": capacity})
    return {"bus_id": bus.id, "registration_number": bus.registration_number}


# Schedule CRUD (Trips)
@router.post("/trips", dependencies=[Depends(role_required(["Admin", "OperatorManager"]))])
async def create_trip(route_id: int, departure_time: datetime, arrival_time: Optional[datetime] = None, bus_id: Optional[int] = None, operator_id: Optional[int] = None, db: AsyncSession = Depends(get_session), current_user=Depends(get_current_user)):
    trip = Trip(route_id=route_id, departure_time=departure_time, arrival_time=arrival_time, bus_id=bus_id, operator_id=operator_id, seats_available=0, status="scheduled")
    async with db.begin():
        db.add(trip)
        await log_audit(db, actor_id=current_user.id, action="create_trip", object_type="trip", object_id=str(route_id), detail={"departure": departure_time.isoformat(), "bus_id": bus_id})
    return {"trip_id": trip.id}


@router.get("/trips", dependencies=[Depends(role_required(["Admin", "OperatorManager"]))])
async def list_trips(db: AsyncSession = Depends(get_session)):
    stmt = sa_select(Trip)
    res = await db.execute(stmt)
    trips = []
    for t in res.scalars().all():
        trips.append({"id": t.id, "route_id": t.route_id, "departure_time": t.departure_time, "status": t.status})
    return trips


# Bookings view
@router.get("/bookings", dependencies=[Depends(role_required(["Admin", "OperatorManager", "Agent"]))])
async def view_bookings(trip_id: Optional[int] = None, status: Optional[str] = None, db: AsyncSession = Depends(get_session)):
    stmt = sa_select(Booking)
    if trip_id:
        stmt = stmt.where(Booking.trip_id == trip_id)
    if status:
        stmt = stmt.where(Booking.status == status)
    res = await db.execute(stmt)
    out = [
        {"id": b.id, "trip_id": b.trip_id, "seat_id": b.seat_id, "status": b.status, "booked_at": b.booked_at}
        for b in res.scalars().all()
    ]
    return out


# Reports: revenue and reconciliation
@router.get("/reports/revenue", dependencies=[Depends(role_required(["Admin"]))])
async def revenue_report(start: Optional[datetime] = None, end: Optional[datetime] = None, db: AsyncSession = Depends(get_session), current_user=Depends(get_current_user)):
    stmt = sa_select(Payment)
    if start:
        stmt = stmt.where(Payment.paid_at >= start)
    if end:
        stmt = stmt.where(Payment.paid_at <= end)
    res = await db.execute(stmt)
    payments = res.scalars().all()
    total = sum([float(p.amount) for p in payments if p.amount is not None])
    # audit
    async with db.begin():
        await log_audit(db, actor_id=current_user.id, action="generate_revenue_report", object_type="report", object_id="revenue", detail={"start": start.isoformat() if start else None, "end": end.isoformat() if end else None})
    return {"total": total, "count": len(payments)}


@router.get("/reports/reconciliation", dependencies=[Depends(role_required(["Admin"]))])
async def reconciliation_report(db: AsyncSession = Depends(get_session), current_user=Depends(get_current_user)):
    # Simple reconciliation: list payments without booking or bookings without successful payments
    stmt_p = sa_select(Payment).where((Payment.booking_id == None) | (Payment.status != 'initiated'))
    res_p = await db.execute(stmt_p)
    payments = res_p.scalars().all()

    stmt_b = sa_select(Booking)
    res_b = await db.execute(stmt_b)
    bookings = res_b.scalars().all()
    unpaid = [b for b in bookings if b.id and not any((p.booking_id == b.id and (p.status or '').lower() in ('success','successful','paid','completed')) for p in payments)]

    async with db.begin():
        await log_audit(db, actor_id=current_user.id, action="generate_reconciliation_report", object_type="report", object_id="reconciliation", detail={})

    return {"payments_unlinked_count": len([p for p in payments if not p.booking_id]), "bookings_unpaid_count": len(unpaid)}

