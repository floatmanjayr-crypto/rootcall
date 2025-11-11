from fastapi import FastAPI, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
from jose import jwt
import os, time

from .deps_autofix import get_current_user

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALG = "HS256"
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://rootcall.onrender.com")

app = FastAPI(title="RootCall (autofix)")

# Trust Render/Cloudflare proxy headers so Secure cookies behave
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Exact-origin CORS with credentials allowed (cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET","POST","PUT","DELETE","OPTIONS"],
    allow_headers=["*"],
)

# Serve your existing static site (already in backend/static)
if os.path.isdir(os.path.join(os.path.dirname(__file__), "..", "static")):
    app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static"), html=True), name="static")

def issue_jwt(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "exp": int(time.time()) + 7*24*3600},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/api/auth/login")
def login(resp: Response):
    # TODO: Replace with real credential check
    user_id = "user-123"
    token = issue_jwt(user_id)
    # Cross-site safe cookie (Render = HTTPS)
    resp.set_cookie(
        key="auth",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7*24*3600,
    )
    return {"ok": True, "token": token}

@app.post("/api/auth/logout")
def logout(resp: Response):
    resp.delete_cookie("auth", path="/")
    return {"ok": True}

@app.get("/api/auth/me")
def me(user = Depends(get_current_user)):
    return {"ok": True, "user": user}

@app.get("/api/rootcall/dashboard")
def dashboard(user = Depends(get_current_user)):
    # Example data; replace with your real stats
    return {"stats": {"calls_today": 12, "blocked": 5}, "user": user}
