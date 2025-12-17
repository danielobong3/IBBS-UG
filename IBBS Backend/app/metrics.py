from prometheus_client import Counter, Gauge, Histogram
from app.redis_client import redis_client
from typing import List
import asyncio

# Notification DLQ depth
NOTIF_DLQ_DEPTH = Gauge("ibbs_notification_dlq_depth", "Redis DLQ list length for notifications")

# Payment metrics
PAYMENT_SUCCESS = Counter("ibbs_payments_success_total", "Successful payments processed", ["provider"])
PAYMENT_FAILURE = Counter("ibbs_payments_failure_total", "Failed payments", ["provider"])

# Seat lock metrics
SEAT_LOCK_LATENCY = Histogram("ibbs_seat_lock_latency_seconds", "Latency for seat lock operations")
SEAT_LOCK_ATTEMPTS = Counter("ibbs_seat_lock_attempts_total", "Total seat lock attempts", ["result"])


async def update_queue_depth(keys: List[str] = None):
    """Update queue depth gauges by measuring Redis list lengths for configured keys."""
    keys = keys or ["notification_dlq"]
    async def _get_len(k):
        try:
            return await redis_client.llen(k)
        except Exception:
            return 0

    results = await asyncio.gather(*[_get_len(k) for k in keys])
    # currently map first key to NOTIF_DLQ_DEPTH
    if results:
        NOTIF_DLQ_DEPTH.set(results[0])
