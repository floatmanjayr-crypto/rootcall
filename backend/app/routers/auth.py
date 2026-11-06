# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from pydantic import BaseModel, EmailStr, validator
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import hashlib
import logging
import os
from app.config import settings
router = APIRouter(tags=["Auth"])

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM

RESET_TOKEN_EXPIRE_MINUTES = 30

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    
    @validator('password')
    def truncate_password(cls, v):
        # bcrypt has a 72 byte limit, truncate if necessary
        return v[:72] if len(v.encode('utf-8')) > 72 else v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        # bcrypt has a 72 byte limit, truncate if necessary
        return v[:72] if len(v.encode('utf-8')) > 72 else v

def get_password_hash(password):
    # Ensure password is truncated to 72 bytes for bcrypt
    password = password[:72]
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    # Ensure password is truncated to 72 bytes for bcrypt
    plain = plain[:72]
    return pwd_context.verify(plain, hashed)

def create_token(user_id: int):
    expire = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _password_fingerprint(hashed_password: str) -> str:
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def create_reset_token(user: User) -> str:
    """Short-lived, single-use password reset token.

    The token embeds a fingerprint of the current password hash, so it
    becomes invalid as soon as the password is changed.
    """
    expire = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "exp": expire,
        "purpose": "pwd_reset",
        "pwf": _password_fingerprint(user.hashed_password),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _reset_email_html(reset_link: str) -> str:
    return f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;color:#16201b;">
  <div style="text-align:center;margin-bottom:24px;">
    <div style="font-size:22px;font-weight:800;letter-spacing:2px;color:#0d3d2f;">ROOTCALL</div>
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#2d7a5f;text-transform:uppercase;">AI Scam Call Shield</div>
  </div>
  <div style="background:#f9f6f3;border:1px solid #e7e2db;border-radius:14px;padding:28px 24px;">
    <h2 style="margin:0 0 12px;font-size:18px;color:#0d3d2f;">Reset your password</h2>
    <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#5b6b64;">
      We received a request to reset your RootCall password.
      Click the button below to choose a new one. This link expires in {RESET_TOKEN_EXPIRE_MINUTES} minutes.
    </p>
    <div style="text-align:center;margin:24px 0;">
      <a href="{reset_link}" style="display:inline-block;background:#0d3d2f;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:13px 32px;border-radius:10px;">Reset Password</a>
    </div>
    <p style="margin:0;font-size:12px;line-height:1.6;color:#9aa8a1;">
      If you didn't request this, you can safely ignore this email — your password will stay the same.
    </p>
  </div>
  <p style="text-align:center;font-size:11px;color:#9aa8a1;margin-top:20px;">© RootCall — Peace-of-Mind Guarantee</p>
</div>"""


@router.post("/api/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Send a password reset link. Always returns the same generic response
    so the endpoint can't be used to discover registered emails."""
    generic_response = {
        "message": "If an account exists for that email, a password reset link has been sent."
    }

    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        return generic_response

    token = create_reset_token(user)
    base_url = settings.APP_BASE_URL.rstrip("/") or str(request.base_url).rstrip("/")
    reset_link = f"{base_url}/static/reset-password.html?token={token}"

    if getattr(settings, "SENDGRID_API_KEY", None):
        try:
            from app.services.email_service import EmailService
            EmailService.send_email(
                user.email,
                "Reset your RootCall password",
                _reset_email_html(reset_link),
            )
        except Exception:
            logger.exception("Failed to send password reset email to %s", user.email)
    else:
        # No email provider configured (e.g. local development) — log the link.
        logger.warning("SENDGRID_API_KEY not set; password reset link for %s: %s", user.email, reset_link)

    return generic_response


@router.post("/api/auth/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    invalid = HTTPException(
        status_code=400,
        detail="This reset link is invalid or has expired. Please request a new one.",
    )
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise invalid

    if payload.get("purpose") != "pwd_reset":
        raise invalid

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise invalid

    # Single-use: the fingerprint changes once the password is updated.
    if payload.get("pwf") != _password_fingerprint(user.hashed_password):
        raise invalid

    user.hashed_password = get_password_hash(data.new_password)
    db.commit()

    return {"message": "Password updated successfully. You can now sign in."}

@router.post("/api/auth/signup")
async def signup(data: UserSignup, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=data.email,
        username=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        is_active=True,
        balance=0.0
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name}
    }

@router.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name}
    }

@router.get("/api/auth/me")
async def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401)
        return {"id": user.id, "email": user.email, "full_name": user.full_name}
    except JWTError:
        raise HTTPException(status_code=401)


@router.get("/api/auth/debug-jwt")
async def debug_jwt():
    """Debug: Check if JWT secrets match"""
    import os
    from app.config import settings
    
    env_secret = os.getenv("JWT_SECRET_KEY", "NOT_SET")
    
    return {
        "env_JWT_SECRET_KEY_first20": env_secret[:20] + "..." if env_secret != "NOT_SET" else "NOT_SET",
        "settings_JWT_SECRET_KEY_first20": settings.JWT_SECRET_KEY[:20] + "...",
        "auth_SECRET_KEY_first20": SECRET_KEY[:20] + "...",
        "env_equals_settings": env_secret == settings.JWT_SECRET_KEY,
        "settings_equals_auth": settings.JWT_SECRET_KEY == SECRET_KEY,
        "all_match": env_secret == settings.JWT_SECRET_KEY == SECRET_KEY,
        "algorithm": ALGORITHM,
        "settings_algorithm": settings.JWT_ALGORITHM
    }


@router.get("/api/auth/test-token-decode")
async def test_token_decode(token: str, db: Session = Depends(get_db)):
    """Debug: Show each step of token validation"""
    from jose import JWTError
    
    try:
        # Step 1: Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Step 2: Get user_id
        user_id = payload.get("sub")
        
        # Step 3: Query database
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        
        return {
            "step1_decode": "SUCCESS",
            "step2_payload": payload,
            "step3_user_id": user_id,
            "step4_user_exists": user is not None,
            "step5_user_details": {"id": user.id, "email": user.email} if user else None
        }
    except JWTError as e:
        return {"error": "JWT decode failed", "detail": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "detail": str(e)}
