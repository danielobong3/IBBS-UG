from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def routes_root():
    return {"module": "routes", "status": "ok"}
