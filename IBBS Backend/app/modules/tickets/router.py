from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def tickets_root():
    return {"module": "tickets", "status": "ok"}
