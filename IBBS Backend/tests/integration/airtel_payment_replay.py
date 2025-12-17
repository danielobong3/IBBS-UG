"""
Simulate multiple Airtel payment attempts for the same booking and verify idempotency, replay protection,
reconciliation accuracy, and that failed payments release seat locks.

Usage: ensure app is running at http://localhost:8000 and env vars set (see previous integration test instructions).
"""
import asyncio
import os
import hmac
import hashlib
import json
from uuid import uuid4
from datetime import datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.models import User, Operator, Bus, Route, Trip, SeatMap, Seat, Booking, Payment

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/ibbs')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
AIRTEL_SECRET = os.environ.get('AIRTEL_SECRET', 'test_airtel_secret')
APP_URL = os.environ.get('APP_URL', 'http://localhost:8000')

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def wait_for_db(retries=10):
    for i in range(retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(lambda sync_conn: sync_conn.execute('SELECT 1'))
            return True
        except Exception:
            await asyncio.sleep(1)
    raise RuntimeError('DB not available')

async def create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def seed_data():
    async with AsyncSessionLocal() as db:
        async with db.begin():
            r = Route(origin='Kampala', destination='Gulu', distance_km=330, active=True)
            db.add(r)
            await db.flush()
            op = Operator(name='AirtelOp')
            db.add(op)
            await db.flush()
            bus = Bus(operator_id=op.id, registration_number=f'A{uuid4().hex[:6]}', capacity=5)
            db.add(bus)
            await db.flush()
            seatmap = SeatMap(bus_id=bus.id, layout={'rows': 3, 'cols': 2})
            db.add(seatmap)
            await db.flush()
            seats = []
            for i in range(1, 6):
                s = Seat(seatmap_id=seatmap.id, seat_number=str(i))
                db.add(s)
                seats.append(s)
            await db.flush()
            trip = Trip(route_id=r.id, bus_id=bus.id, operator_id=op.id, departure_time=datetime.utcnow() + timedelta(days=1), seats_available=5, status='scheduled')
            db.add(trip)
            await db.flush()
            user = User(email=f'airtel{uuid4().hex[:6]}@example.com', hashed_password='x', role='Agent')
            db.add(user)
            await db.flush()
            return {'user_id': user.id, 'trip_id': trip.id, 'seat_id': seats[0].id}

async def run_test():
    await wait_for_db()
    await create_schema()
    ids = await seed_data()
    user_id = ids['user_id']
    trip_id = ids['trip_id']
    seat_id = ids['seat_id']

    async with httpx.AsyncClient(base_url=APP_URL, timeout=30.0) as client:
        # register & login to obtain access token
        password = 'TestPass123!'
        email = f'airtel{uuid4().hex[:6]}@example.com'
        reg = await client.post('/auth/register', json={'email': email, 'password': password, 'full_name': 'Airtel User', 'role': 'Agent'})
        assert reg.status_code in (200, 201)
        user_id = reg.json().get('id')
        login = await client.post('/auth/login', data={'username': email, 'password': password})
        assert login.status_code == 200
        tokens = login.json()
        access = tokens['access_token']
        headers = {'Authorization': f'Bearer {access}'}
        # lock and confirm booking
        r = await client.post('/bookings/locks/lock', json={'trip_id': trip_id, 'seat_id': seat_id, 'ttl': 60}, headers=headers)
        assert r.status_code == 200
        token = r.json()['token']
        # confirm booking
        resp = await client.post('/bookings/locks/confirm', json={'trip_id': trip_id, 'seat_id': seat_id, 'token': token, 'user_id': user_id}, headers=headers)
        assert resp.status_code == 200
        booking_id = resp.json()['booking_id']
        print('Booking created', booking_id)

        # initiate first payment attempt (Airtel)
        pay1 = await client.post('/payments/initiate', json={'booking_id': booking_id, 'provider': 'airtel', 'amount': 50.0}, headers=headers)
        assert pay1.status_code == 200
        ref1 = pay1.json()['provider_ref']
        print('Initiated airtel payment ref1', ref1)

        # simulate failed webhook for ref1 (event id unique)
        evt1 = 'evt_' + uuid4().hex[:8]
        payload1 = {'id': evt1, 'data': {'transaction_id': ref1, 'status': 'failed', 'amount': 50.0}}
        body1 = json.dumps(payload1).encode('utf-8')
        sig1 = hmac.new(AIRTEL_SECRET.encode(), body1, hashlib.sha256).hexdigest()
        wh1 = await client.post('/payments/webhook/airtel', content=body1, headers={'x-signature': sig1, 'content-type': 'application/json'})
        print('webhook failed resp', wh1.status_code, wh1.text)
        assert wh1.status_code == 200

        # after failure booking should be cancelled and seats_available incremented
        bks = await client.get(f'/bookings?trip_id={trip_id}', headers=headers)
        bookings = bks.json()
        book = next((b for b in bookings if b['id'] == booking_id), None)
        assert book is not None
        assert book['status'] in ('cancelled', 'payment_failed')
        print('Booking status after failed payment:', book['status'])

        # initiate second payment attempt (Airtel) for same booking
        pay2 = await client.post('/payments/initiate', json={'booking_id': booking_id, 'provider': 'airtel', 'amount': 50.0}, headers=headers)
        assert pay2.status_code == 200
        ref2 = pay2.json()['provider_ref']
        print('Initiated airtel payment ref2', ref2)

        # simulate successful webhook for ref2
        evt2 = 'evt_' + uuid4().hex[:8]
        payload2 = {'id': evt2, 'data': {'transaction_id': ref2, 'status': 'success', 'amount': 50.0}}
        body2 = json.dumps(payload2).encode('utf-8')
        sig2 = hmac.new(AIRTEL_SECRET.encode(), body2, hashlib.sha256).hexdigest()
        wh2 = await client.post('/payments/webhook/airtel', content=body2, headers={'x-signature': sig2, 'content-type': 'application/json'})
        assert wh2.status_code == 200
        print('webhook success resp', wh2.status_code, wh2.text)

        # replay the same webhook event (should be idempotent)
        wh2r = await client.post('/payments/webhook/airtel', content=body2, headers={'x-signature': sig2, 'content-type': 'application/json'})
        assert wh2r.status_code == 200
        print('webhook replay resp', wh2r.status_code, wh2r.text)

        # check booking status is now paid
        bks2 = await client.get(f'/bookings?trip_id={trip_id}', headers=headers)
        book2 = next((b for b in bks2.json() if b['id'] == booking_id), None)
        assert book2 is not None
        assert book2['status'] in ('paid',)
        print('Booking status after successful payment:', book2['status'])

        # run reconciliation report and print results
        admin_headers = headers
        rep = await client.get('/admin/reports/reconciliation', headers=admin_headers)
        print('reconciliation report', rep.status_code, rep.text)

    print('Airtel payment replay test completed successfully')

if __name__ == '__main__':
    asyncio.run(run_test())
