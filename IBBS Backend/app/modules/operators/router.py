from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def operators_root():
    return {"module": "operators", "status": "ok"}
