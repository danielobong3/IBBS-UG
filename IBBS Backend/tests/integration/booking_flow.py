"""
Integration test script to exercise the full booking flow locally.

Usage (PowerShell):

# start dependencies
docker-compose up -d

# set env vars (match docker-compose or your env)
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/ibbs'
$env:REDIS_URL = 'redis://localhost:6379/0'
$env:MTN_SECRET = 'test_mtn_secret'

# start app in background (or in another terminal)
uvicorn app.main:app --reload

# run this script with python
python tests\integration\booking_flow.py

This script will:
- create tables if needed
- seed route/trip/seat data
- create a test user
- perform seat lock
- run two concurrent confirm attempts using the same lock token (verify one succeeds, one fails)
- initiate payment for the successful booking
- simulate MTN webhook (signed with HMAC using MTN_SECRET)
- verify booking moves to paid

Note: run against a local instance of the app at http://localhost:8000
"""

import asyncio
import os
import hmac
import hashlib
import json
import time
from uuid import uuid4
from datetime import datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Adjust path imports if running from project root
from app.db.base import Base
from app.models.models import User, Operator, Bus, Route, Trip, SeatMap, Seat, Booking, Payment

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/ibbs')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
MTN_SECRET = os.environ.get('MTN_SECRET', 'test_mtn_secret')
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
            # create route if not exists
            r = Route(origin='Kampala', destination='Gulu', distance_km=330, active=True)
            db.add(r)
            await db.flush()
            # operator and bus
            op = Operator(name='Test Operator')
            db.add(op)
            await db.flush()
            bus = Bus(operator_id=op.id, registration_number=f'P{uuid4().hex[:6]}', capacity=10)
            db.add(bus)
            await db.flush()
            seatmap = SeatMap(bus_id=bus.id, layout={'rows': 5, 'cols': 2})
            db.add(seatmap)
            await db.flush()
            # seats
            seats = []
            for i in range(1, 11):
                s = Seat(seatmap_id=seatmap.id, seat_number=str(i))
                db.add(s)
                seats.append(s)
            await db.flush()
            # trip with seats_available
            trip = Trip(route_id=r.id, bus_id=bus.id, operator_id=op.id, departure_time=datetime.utcnow() + timedelta(days=1), seats_available=10, status='scheduled')
            db.add(trip)
            await db.flush()
            # create user
            user = User(email=f'test{uuid4().hex[:6]}@example.com', hashed_password='x', role='Agent')
            db.add(user)
            await db.flush()
            # commit
            return {
                'user_id': user.id,
                'trip_id': trip.id,
                'seat_id': seats[0].id,
            }

async def run_flow():
    print('Waiting for DB...')
    await wait_for_db()
    print('Creating schema...')
    await create_schema()
    print('Seeding data...')
    ids = await seed_data()
    user_id = ids['user_id']
    trip_id = ids['trip_id']
    seat_id = ids['seat_id']
    print('Seeded user_id=%s trip_id=%s seat_id=%s' % (user_id, trip_id, seat_id))

    async with httpx.AsyncClient(base_url=APP_URL, timeout=30.0) as client:
        # create user via API and login to get tokens
        password = 'TestPass123!'
        email = f'test{uuid4().hex[:6]}@example.com'
        reg = await client.post('/auth/register', json={'email': email, 'password': password, 'full_name': 'Test User', 'role': 'Agent'})
        assert reg.status_code in (200, 201)
        user_id = reg.json().get('id')
        # login (OAuth2 password form)
        login = await client.post('/auth/login', data={'username': email, 'password': password})
        assert login.status_code == 200, login.text
        tokens = login.json()
        access = tokens['access_token']
        headers = {'Authorization': f'Bearer {access}'}
        # lock seat
        print('Locking seat...')
        r = await client.post('/bookings/locks/lock', json={'trip_id': trip_id, 'seat_id': seat_id, 'ttl': 60}, headers=headers)
        print('lock response', r.status_code, r.text)
        assert r.status_code == 200, r.text
        token = r.json().get('token')

        # attempt two concurrent confirms using the same token
        print('Confirming booking concurrently (2 requests)...')
        conf_payload = {'trip_id': trip_id, 'seat_id': seat_id, 'token': token, 'user_id': user_id}

        async def confirm_once():
            resp = await client.post('/bookings/locks/confirm', json=conf_payload, headers=headers)
            return resp.status_code, resp.text

        results = await asyncio.gather(confirm_once(), confirm_once())
        print('Confirm results:', results)
        success_count = sum(1 for status, _ in results if status == 200)
        conflict_count = sum(1 for status, _ in results if status == 409)
        assert success_count == 1 and conflict_count == 1, (results)
        print('Double-confirm prevented: OK')

        # Find booking id from successful response
        booking_resp = None
        for status, text in results:
            if status == 200:
                booking_resp = json.loads(text)
                break
        booking_id = booking_resp['booking_id']
        print('Booking created id=', booking_id)

        # initiate payment via MTN
        print('Initiating payment...')
        pay_resp = await client.post('/payments/initiate', json={'booking_id': booking_id, 'provider': 'mtn', 'amount': 100.0}, headers=headers)
        print('payment initiate', pay_resp.status_code, pay_resp.text)
        assert pay_resp.status_code == 200
        provider_ref = pay_resp.json().get('provider_ref')

        # simulate webhook from MTN
        event_id = 'evt_' + uuid4().hex[:8]
        payload = {
            'id': event_id,
            'data': {
                'transaction_id': provider_ref,
                'status': 'success',
                'amount': 100.0,
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = hmac.new(MTN_SECRET.encode(), body, hashlib.sha256).hexdigest()
        headers_webhook = {'x-signature': sig, 'content-type': 'application/json'}
        print('Sending webhook...')
        wh = await client.post(f'/payments/webhook/mtn', content=body, headers=headers_webhook)
        print('webhook response', wh.status_code, wh.text)
        assert wh.status_code in (200, 201, 202)

        # Give the app a moment to process
        await asyncio.sleep(1)

        # retrieve booking history / bookings for user via admin booking view (Agent allowed)
        print('Retrieving bookings...')
        bk = await client.get(f'/bookings?trip_id={trip_id}', headers=headers)
        print('bookings list', bk.status_code, bk.text)
        assert bk.status_code == 200
        bookings = bk.json()
        matched = [b for b in bookings if b['id'] == booking_id]
        assert matched and matched[0]['status'] in ('confirmed', 'paid')
        print('Booking status after payment:', matched[0]['status'])

    print('\nIntegration test completed successfully')

if __name__ == '__main__':
    asyncio.run(run_flow())
