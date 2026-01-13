"""VoIP Platform Main Application"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routers import rootcall_portal
from app.routers import payments, number_management, auth, admin

# Import routers
from app.routers import (
    provision_inbound,
    telnyx_webhooks,
    texml,
    retell,
    auto_retell,
    client_onboarding,
    outbound_calls
)
from app.routers import telnyx as telnyx_router
from app.routers import bulk as bulk_router
from app.routers.retell_inbound import router as retell_inbound_router
from app.api.v1 import provision_finalize
from app.routers import agent_templates
from app.routers.rootcall_screen import router as rootcall_screen_router

# Create database tables

# Initialize FastAPI
app = FastAPI(
    title="VoIP Platform API",
    description="Complete VoIP platform with conversational AI",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files FIRST - before routers
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include all routers
app.include_router(telnyx_webhooks.router)
app.include_router(texml.router)
app.include_router(retell.router)
app.include_router(retell_inbound_router)
app.include_router(auto_retell.router)
app.include_router(provision_inbound.router)
app.include_router(client_onboarding.router)
app.include_router(telnyx_router.router)
app.include_router(bulk_router.router)
app.include_router(provision_finalize.router)
app.include_router(outbound_calls.router)
app.include_router(rootcall_portal.router)
app.include_router(agent_templates.router)
app.include_router(rootcall_screen_router)  # RootCall Call Screening
app.include_router(payments.router)
app.include_router(number_management.router)
app.include_router(auth.router)
app.include_router(admin.router)

@app.get("/")
async def root():
    return {
        "message": "VoIP Platform API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
