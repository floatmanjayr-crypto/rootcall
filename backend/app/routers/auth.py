# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from pydantic import BaseModel, EmailStr, validator
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from app.config import settings
router = APIRouter(tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    
    @validator('password')
    def truncate_password(cls, v):
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
