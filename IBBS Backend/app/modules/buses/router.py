from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def buses_root():
    return {"module": "buses", "status": "ok"}
