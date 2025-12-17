from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def seatmaps_root():
    return {"module": "seatmaps", "status": "ok"}
