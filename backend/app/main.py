"""VoIP Platform Main Application"""
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.core.deps import require_operator
from app.routers import rootcall_portal
from app.routers import payments, number_management, auth, admin
from app.routers import live_calls, onboarding, trusted_inbound

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
app.include_router(provision_inbound.router, dependencies=[Depends(require_operator)])
app.include_router(client_onboarding.router, dependencies=[Depends(require_operator)])
app.include_router(telnyx_router.router)
app.include_router(bulk_router.router, dependencies=[Depends(require_operator)])
app.include_router(provision_finalize.router, dependencies=[Depends(require_operator)])
app.include_router(outbound_calls.router, dependencies=[Depends(require_operator)])
app.include_router(rootcall_portal.router)
app.include_router(agent_templates.router, dependencies=[Depends(require_operator)])
app.include_router(rootcall_screen_router)  # RootCall Call Screening
app.include_router(payments.router)
app.include_router(number_management.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(live_calls.router)
app.include_router(onboarding.router)
app.include_router(trusted_inbound.router)

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

@app.get("/login.html", include_in_schema=False)
def login_redirect():
    return RedirectResponse(url="/static/login.html")

@app.get("/onboarding.html", include_in_schema=False)
def onboarding_redirect():
    return RedirectResponse(url="/static/onboarding.html")

@app.get("/client-portal.html", include_in_schema=False)
def portal_redirect():
    return RedirectResponse(url="/static/client-portal.html")

@app.get("/success.html", include_in_schema=False)
def success_redirect(request: Request):
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(url=f"/static/onboarding.html{query}")

@app.get("/forgot-password.html", include_in_schema=False)
def forgot_password_redirect():
    return RedirectResponse(url="/static/forgot-password.html")

@app.get("/reset-password.html", include_in_schema=False)
def reset_password_redirect(request: Request):
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(url=f"/static/reset-password.html{query}")

@app.get("/privacy.html", include_in_schema=False)
def privacy_redirect():
    return RedirectResponse(url="/static/privacy.html")

@app.get("/terms.html", include_in_schema=False)
def terms_redirect():
    return RedirectResponse(url="/static/terms.html")

if __name__ == "__main__":
    import uvicorn
    # FIXED: Host is 0.0.0.0 and Port is 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)