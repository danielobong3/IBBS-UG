import json
from uuid import uuid4
from datetime import datetime, timedelta
import time
from app.metrics import SEAT_LOCK_LATENCY, SEAT_LOCK_ATTEMPTS
from typing import Optional
from app.redis_client import redis_client


LOCK_KEY_TPL = "seat_lock:{trip_id}:{seat_id}"


async def lock_seat(trip_id: int, seat_id: int, ttl: int = 300) -> Optional[dict]:
    """Attempt to create a lock for a seat. Returns dict with token and expires_at on success, or None if already locked."""
    key = LOCK_KEY_TPL.format(trip_id=trip_id, seat_id=seat_id)
    start = time.perf_counter()
    token = str(uuid4())
    # store token only (keeps compare-and-delete simple)
    ok = await redis_client.set(key, token, ex=ttl, nx=True)
    if not ok:
        SEAT_LOCK_ATTEMPTS.labels(result="failed").inc()
        return None
    expires_at = datetime.utcnow() + timedelta(seconds=ttl)
    SEAT_LOCK_ATTEMPTS.labels(result="success").inc()
    SEAT_LOCK_LATENCY.observe(time.perf_counter() - start)
    return {"token": token, "expires_at": expires_at}


_CAS_DEL_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


async def validate_and_consume_lock(trip_id: int, seat_id: int, token: str) -> bool:
    """Atomically validate that the lock token matches and delete it.
    Returns True if consumed, False otherwise."""
    key = LOCK_KEY_TPL.format(trip_id=trip_id, seat_id=seat_id)
    # Use Lua script to compare and delete atomically
    start = time.perf_counter()
    try:
        res = await redis_client.eval(_CAS_DEL_SCRIPT, keys=[key], args=[token])
        ok = bool(res)
        SEAT_LOCK_LATENCY.observe(time.perf_counter() - start)
        SEAT_LOCK_ATTEMPTS.labels(result=("consumed" if ok else "invalid")).inc()
        return ok
    except Exception:
        SEAT_LOCK_ATTEMPTS.labels(result="error").inc()
        return False


async def release_lock(trip_id: int, seat_id: int, token: Optional[str] = None) -> bool:
    """Release a lock. If token is provided, only deletes when matching; if not, deletes unconditionally (admin).
    Returns True if deleted (or didn't exist), False if token mismatch."""
    key = LOCK_KEY_TPL.format(trip_id=trip_id, seat_id=seat_id)
    if token is None:
        # unconditional delete
        await redis_client.delete(key)
        return True
    # conditional delete
    try:
        res = await redis_client.eval(_CAS_DEL_SCRIPT, keys=[key], args=[token])
        return bool(res)
    except Exception:
        return False
