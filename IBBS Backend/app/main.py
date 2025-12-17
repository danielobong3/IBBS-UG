from fastapi import FastAPI, Request, Response
from app.config import settings
import importlib
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.logging_setup import setup_logging, TRACE_ID_CTX
import uuid
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from app.metrics import update_queue_depth


app = FastAPI(title=settings.APP_NAME)

# initialize logging and Sentry
setup_logging()
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN)
    app.add_middleware(SentryAsgiMiddleware)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    TRACE_ID_CTX.set(trace_id)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response

# List of module names to include as routers
MODULES = [
    "auth",
    "users",
    "operators",
    "routes",
    "trips",
    "buses",
    "seatmaps",
    "bookings",
    "payments",
    "tickets",
    "notifications",
    "admin",
    "reports",
]


for mod in MODULES:
    try:
        pkg = importlib.import_module(f"app.modules.{mod}.router")
        if hasattr(pkg, "router"):
            app.include_router(pkg.router, prefix=f"/{mod}")
    except Exception:
        # module may be missing during initial scaffold
        pass


@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "status": "ok"}


@app.get("/metrics")
async def metrics():
    # update dynamic gauges before scraping
    try:
        await update_queue_depth()
    except Exception:
        pass
    content = generate_latest()
    return Response(content=content, media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    # simple readiness: check redis
    try:
        await __import__("app.redis_client").redis_client.ping()
    except Exception:
        return Response(status_code=503, content="redis unavailable")
    # DB check could be added here
    return {"status": "ready"}
