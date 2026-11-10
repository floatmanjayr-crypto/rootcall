from datetime import datetime, timedelta
from typing import Optional
import logging
from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
log = logging.getLogger(__name__)


def signing_key() -> str:
    key = settings.JWT_SECRET_KEY
    if not key.strip() or key.strip() == "your-secret-key-change-in-production":
        log.error("JWT signing is unavailable: configure a private JWT_SECRET_KEY.")
        raise HTTPException(status_code=503, detail="Account access is temporarily unavailable. Contact support.")
    return key


def token_user_id(payload: dict) -> Optional[int]:
    subject = payload.get("sub")
    if (not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal()
            or len(subject) > 10):
        return None
    value = int(subject)
    return value if 0 < value <= 2147483647 else None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, signing_key(), algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(
            token, signing_key(), algorithms=[settings.JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
        if payload.get("purpose"):
            return None
        return payload
    except JWTError:
        return None
