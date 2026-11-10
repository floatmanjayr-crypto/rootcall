# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from pydantic import BaseModel, EmailStr, validator
from jose import JWTError, jwt
from datetime import datetime, timedelta
from urllib.parse import urlparse
from urllib.error import URLError
from python_http_client.exceptions import HTTPError as EmailHTTPError
import hashlib
import logging
from app.config import settings
from app.core.deps import get_current_active_user
from app.core.security import create_access_token, get_password_hash, verify_password, signing_key, token_user_id
from app.services.customer_onboarding import new_onboarding, next_url
from app.services.email_service import EmailService
router = APIRouter(tags=["Auth"])

logger = logging.getLogger(__name__)

RESET_TOKEN_EXPIRE_MINUTES = 30

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8 or len(v.encode("utf-8")) > 72:
            raise ValueError("Use at least 8 characters and at most 72 UTF-8 bytes.")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8 or len(v.encode("utf-8")) > 72:
            raise ValueError("Use at least 8 characters and at most 72 UTF-8 bytes.")
        return v

def create_token(user_id: int):
    return create_access_token({"sub": str(user_id)}, expires_delta=timedelta(hours=24))


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
    return jwt.encode(payload, signing_key(), algorithm=settings.JWT_ALGORITHM)


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


def deliver_reset_email(email: str, reset_link: str) -> None:
    try:
        result = EmailService.send_email(
            email, "Reset your RootCall password", _reset_email_html(reset_link),
        )
    except (EmailHTTPError, URLError, OSError):
        # Provider exception text can contain recipient details or reset-token HTML.
        logger.error("Password recovery email delivery failed; check the email provider.")
        return
    if result.get("status") != 202:
        logger.error("Password recovery email was not accepted by the provider.")


@router.post("/api/auth/forgot-password", status_code=202)
async def forgot_password(
    data: ForgotPasswordRequest, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Acknowledge the request, not email delivery, without revealing account existence."""
    generic_response = {
        "message": "Your request was received. If an account exists for that email, check your inbox for a password reset link."
    }
    signing_key()
    base_url = settings.APP_BASE_URL.rstrip("/")
    parsed = urlparse(base_url)
    if (not settings.SENDGRID_API_KEY or not settings.SENDER_EMAIL
            or parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment):
        logger.error("Password recovery is unavailable: configure SendGrid, sender, and an HTTPS APP_BASE_URL origin.")
        raise HTTPException(status_code=503, detail="Password recovery is temporarily unavailable. Please contact support.")

    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.is_active:
        return generic_response

    token = create_reset_token(user)
    reset_link = f"{base_url}/static/reset-password.html#token={token}"

    background_tasks.add_task(deliver_reset_email, user.email, reset_link)

    return generic_response


@router.post("/api/auth/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    invalid = HTTPException(
        status_code=400,
        detail="This reset link is invalid or has expired. Please request a new one.",
    )
    try:
        payload = jwt.decode(
            data.token, signing_key(), algorithms=[settings.JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError:
        raise invalid

    if payload.get("purpose") != "pwd_reset":
        raise invalid

    user_id = token_user_id(payload)
    if user_id is None:
        raise invalid
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user or not user.is_active:
        raise invalid

    # Single-use: the fingerprint changes once the password is updated.
    if payload.get("pwf") != _password_fingerprint(user.hashed_password):
        raise invalid

    user.hashed_password = get_password_hash(data.new_password)
    db.commit()

    return {"message": "Password updated successfully. You can now sign in."}

@router.post("/api/auth/signup")
async def signup(data: UserSignup, db: Session = Depends(get_db)):
    signing_key()
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
    db.flush()
    db.add(new_onboarding(user.id))
    db.commit()
    
    token = create_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name},
        "next_url": next_url(db, user.id),
    }

@router.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name},
        "next_url": next_url(db, user.id),
    }

@router.get("/api/auth/me")
async def get_me(
    user: User = Depends(get_current_active_user), db: Session = Depends(get_db),
):
    return {
        "id": user.id, "email": user.email, "full_name": user.full_name,
        "is_superuser": bool(user.is_superuser), "next_url": next_url(db, user.id),
    }
