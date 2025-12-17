from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def users_root():
    return {"module": "users", "status": "ok"}
