# IBBS - FastAPI Boilerplate

Scaffolded FastAPI project with:
- Async SQLAlchemy setup
- Alembic migrations (async-ready)
- Redis integration
- Celery tasks (Redis broker)
- Pydantic `BaseSettings` configuration
- App modules: auth, users, operators, routes, trips, buses, seatmaps, bookings, payments, tickets, notifications, admin, reports

See `requirements.txt` for required packages and `app/config.py` for environment variables.

Quick start (development):

1. Create virtualenv and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create `.env` (copy `.env.example`) and set `DATABASE_URL` and `REDIS_URL`.

3. Start the app:

```powershell
uvicorn app.main:app --reload
```

4. Start Celery worker:

```powershell
celery -A app.celery_app.celery_app worker --loglevel=info
```
