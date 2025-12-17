from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def reports_root():
    return {"module": "reports", "status": "ok"}
