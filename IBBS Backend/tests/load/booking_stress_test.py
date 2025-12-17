"""
Load test: run many concurrent booking requests against the app to validate seat lock correctness.

Usage:
1. Start dependencies and the app (see previous instructions).
2. Run this script:
   python tests\load\booking_stress_test.py

Environment variables:
- APP_URL (default http://localhost:8000)
- DATABASE_URL
- CONCURRENT_REQUESTS (default 1000)
- SEAT_COUNT (default 40)

The script will:
- Ensure Kampala-Arua route and a trip exist with a bus and seatmap and `SEAT_COUNT` seats
- Create a test user and use header `X-User-Id` to identify requests
- Fire `CONCURRENT_REQUESTS` booking attempts choosing random seats
- Measure confirm response times and report success/conflict/error counts
- Verify there are no duplicate bookings for the same trip+seat
- Test lock expiry: lock a seat with small TTL and ensure it becomes available after TTL

Note: This is a load test script. Running heavy loads on single-machine dev setups may saturate CPU/network.
"""

import asyncio
import os
import random
import statistics
import time
import json
from datetime import datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select as sa_select, func as sa_func

from app.db.base import Base
from app.models.models import User, Operator, Bus, Route, Trip, SeatMap, Seat, Booking

APP_URL = os.environ.get('APP_URL', 'http://localhost:8000')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/ibbs')
CONCURRENT = int(os.environ.get('CONCURRENT_REQUESTS', '1000'))
SEAT_COUNT = int(os.environ.get('SEAT_COUNT', '40'))

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def ensure_trip_and_seats():
    async with AsyncSessionLocal() as db:
        async with db.begin():
            # find or create route Kampala -> Arua
            stmt = sa_select(Route).where(Route.origin == 'Kampala', Route.destination == 'Arua')
            res = await db.execute(stmt)
            route = res.scalars().first()
            if not route:
                route = Route(origin='Kampala', destination='Arua', distance_km=420.00, active=True)
                db.add(route)
                await db.flush()

            # ensure operator
            opstmt = sa_select(Operator).where(Operator.name == 'StressOperator')
            res = await db.execute(opstmt)
            op = res.scalars().first()
            if not op:
                op = Operator(name='StressOperator')
                db.add(op)
                await db.flush()

            # ensure bus
            busstmt = sa_select(Bus).where(Bus.operator_id == op.id)
            res = await db.execute(busstmt)
            bus = res.scalars().first()
            if not bus:
                bus = Bus(operator_id=op.id, registration_number=f'STRESS{random.randint(1000,9999)}', capacity=SEAT_COUNT)
                db.add(bus)
                await db.flush()

            # seatmap
            sm = SeatMap(bus_id=bus.id, layout={'rows': SEAT_COUNT//4, 'cols': 4})
            db.add(sm)
            await db.flush()

            seats = []
            for i in range(1, SEAT_COUNT+1):
                s = Seat(seatmap_id=sm.id, seat_number=str(i))
                db.add(s)
                seats.append(s)
            await db.flush()

            # trip
            tripstmt = sa_select(Trip).where(Trip.route_id == route.id)
            res = await db.execute(tripstmt)
            trip = res.scalars().first()
            if not trip:
                trip = Trip(route_id=route.id, bus_id=bus.id, operator_id=op.id, departure_time=datetime.utcnow()+timedelta(hours=24), seats_available=SEAT_COUNT, status='scheduled')
                db.add(trip)
                await db.flush()
            else:
                # ensure seats_available aligns
                trip.seats_available = SEAT_COUNT

    # return trip id and seat ids
    async with AsyncSessionLocal() as db:
        stmt = sa_select(Trip).where(Trip.route_id == route.id)
        res = await db.execute(stmt)
        trip = res.scalars().first()
        stmt2 = sa_select(Seat).where(Seat.seatmap_id == sm.id)
        res2 = await db.execute(stmt2)
        seat_objs = res2.scalars().all()
        seat_ids = [s.id for s in seat_objs]
        return trip.id, seat_ids

async def create_test_user():
    async with AsyncSessionLocal() as db:
        async with db.begin():
            u = User(email=f'stress{random.randint(10000,99999)}@example.com', hashed_password='x', role='Agent')
            db.add(u)
            await db.flush()
            return u.id

async def attempt_booking(client, headers, trip_id, seat_id):
    # lock then confirm
    t0 = time.perf_counter()
    lock_resp = await client.post('/bookings/locks/lock', json={'trip_id': trip_id, 'seat_id': seat_id, 'ttl': 10}, headers=headers)
    if lock_resp.status_code != 200:
        return {'result': 'lock_failed', 'latency': None}
    token = lock_resp.json().get('token')
    # confirm and measure latency for confirm
    t1 = time.perf_counter()
    conf = await client.post('/bookings/locks/confirm', json={'trip_id': trip_id, 'seat_id': seat_id, 'token': token, 'user_id': int(headers['X-User-Id'])}, headers=headers)
    t2 = time.perf_counter()
    latency_ms = (t2 - t1) * 1000
    if conf.status_code == 200:
        return {'result': 'booked', 'latency': latency_ms}
    elif conf.status_code == 409:
        return {'result': 'conflict', 'latency': latency_ms}
    else:
        return {'result': f'error_{conf.status_code}', 'latency': latency_ms}

async def run_concurrency(trip_id, seat_ids, user_id):
    headers = {'X-User-Id': str(user_id)}
    async with httpx.AsyncClient(base_url=APP_URL, timeout=10.0) as client:
        tasks = []
        for i in range(CONCURRENT):
            seat = random.choice(seat_ids)
            tasks.append(attempt_booking(client, headers, trip_id, seat))
        results = await asyncio.gather(*tasks)
        return results

async def check_double_bookings(trip_id):
    async with AsyncSessionLocal() as db:
        stmt = sa_select(Booking.seat_id, sa_func.count(Booking.id)).where(Booking.trip_id == trip_id).group_by(Booking.seat_id).having(sa_func.count(Booking.id) > 1)
        res = await db.execute(stmt)
        dupes = res.all()
        return dupes

async def test_lock_expiry(client, headers, trip_id, seat_id):
    # lock with ttl=2s and do not confirm, ensure after 3s we can lock again
    r = await client.post('/bookings/locks/lock', json={'trip_id': trip_id, 'seat_id': seat_id, 'ttl': 2}, headers=headers)
    if r.status_code != 200:
        return False, 'initial_lock_failed'
    token = r.json()['token']
    # do not confirm; wait for ttl
    await asyncio.sleep(3)
    r2 = await client.post('/bookings/locks/lock', json={'trip_id': trip_id, 'seat_id': seat_id, 'ttl': 10}, headers=headers)
    if r2.status_code != 200:
        return False, 'lock_not_expired'
    # cleanup: consume token and confirm a booking to avoid leaving seat locked
    token2 = r2.json()['token']
    conf = await client.post('/bookings/locks/confirm', json={'trip_id': trip_id, 'seat_id': seat_id, 'token': token2, 'user_id': int(headers['X-User-Id'])}, headers=headers)
    return conf.status_code == 200, f'confirm_status_{conf.status_code}'

async def main():
    print('Preparing DB and trip...')
    trip_id, seat_ids = await ensure_trip_and_seats()
    print('Trip id:', trip_id, 'seats:', len(seat_ids))
    user_id = await create_test_user()
    print('Test user id:', user_id)

    print(f'Running {CONCURRENT} concurrent booking attempts...')
    start = time.perf_counter()
    results = await run_concurrency(trip_id, seat_ids, user_id)
    duration = time.perf_counter() - start
    print('Completed in %.2fs' % duration)

    # summarize
    counts = {}
    latencies = [r['latency'] for r in results if r['latency'] is not None]
    for r in results:
        counts[r['result']] = counts.get(r['result'], 0) + 1
    print('Result counts:', counts)
    if latencies:
        print('latency ms: mean=%.2f p50=%.2f p95=%.2f p99=%.2f' % (statistics.mean(latencies), statistics.median(latencies), statistics.quantiles(latencies, n=100)[94], max(latencies)))
        under_200 = sum(1 for l in latencies if l <= 200)
        print(f'{under_200}/{len(latencies)} confirmations under 200ms ({under_200/len(latencies):.2%})')

    # check double-bookings
    dupes = await check_double_bookings(trip_id)
    if dupes:
        print('Double-bookings detected:', dupes)
    else:
        print('No double bookings detected')

    # test lock expiry
    print('Testing lock expiry on a fresh seat...')
    async with httpx.AsyncClient(base_url=APP_URL, timeout=10.0) as client:
        headers = {'X-User-Id': str(user_id)}
        seat_for_expiry = random.choice(seat_ids)
        ok, msg = await test_lock_expiry(client, headers, trip_id, seat_for_expiry)
        print('Lock expiry test:', ok, msg)

if __name__ == '__main__':
    asyncio.run(main())
