"""Telnyx Auto Config - Placeholder"""
from fastapi import APIRouter

router = APIRouter(prefix="/telnyx-config", tags=["Telnyx Config"])

@router.get("/health")
async def health():
    return {"status": "ok"}
