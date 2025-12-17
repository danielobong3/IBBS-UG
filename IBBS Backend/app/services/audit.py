from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AuditLog
from datetime import datetime


async def log_audit(db: AsyncSession, actor_id: int, action: str, object_type: str = None, object_id: str = None, detail: dict = None, ip_address: str = None):
    audit = AuditLog(
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(audit)
    # do not commit here; caller should include in transaction context
    return audit
