from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def trips_root():
    return {"module": "trips", "status": "ok"}
