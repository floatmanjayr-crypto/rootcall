from fastapi import APIRouter
from app.api.v1 import auth, phone_numbers, calls, ai_agents
from app.routers import telnyx as telnyx_router 

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(phone_numbers.router, prefix="/phone-numbers", tags=["Phone Numbers"])
api_router.include_router(calls.router, prefix="/calls", tags=["Calls"])
api_router.include_router(ai_agents.router, prefix="/ai-agents", tags=["AI Agents"])
