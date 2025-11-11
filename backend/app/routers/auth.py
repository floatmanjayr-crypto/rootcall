# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, get_password_hash, create_access_token
from pydantic import BaseModel, EmailStr, validator
from datetime import timedelta

router = APIRouter(tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# ============================================
# Pydantic Models
# ============================================

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @validator('password')
    def truncate_password(cls, v):
        # bcrypt has a 72 byte limit, truncate if necessary
        return v[:72] if len(v.encode('utf-8')) > 72 else v

class LoginRequest(BaseModel):
    """Login with JSON body (not form data)"""
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

# ============================================
# Auth Endpoints
# ============================================

@router.post("/api/auth/signup", response_model=TokenResponse)
async def signup(data: UserSignup, db: Session = Depends(get_db)):
    """Register new user"""
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

    # Create access token using centralized function
    access_token = create_access_token(
        data={"sub": user.id}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id, 
            "email": user.email, 
            "full_name": user.full_name
        }
    }

@router.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: Session = Depends(get_db, response: Response)):
    """
    Login with email and password (JSON format)
    
    Example request body:
    {
        "email": "user@example.com",
        "password": "yourpassword"
    }
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    
    # Verify credentials
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": user.id}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id, 
            "email": user.email, 
            "full_name": user.full_name
        }
    }

@router.get("/api/auth/me")
async def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current user info from token"""
    from app.core.security import decode_access_token
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return {
        "id": user.id, 
        "email": user.email, 
        "full_name": user.full_name,
        "is_active": user.is_active
    }

@router.get("/api/auth/debug-config")
async def debug_config():
    """Debug endpoint - remove after testing"""
    from app.config import settings
    return {
        "jwt_secret_key_exists": bool(settings.JWT_SECRET_KEY),
        "jwt_secret_key_length": len(settings.JWT_SECRET_KEY),
        "jwt_algorithm": settings.JWT_ALGORITHM,
        "jwt_secret_first_4": settings.JWT_SECRET_KEY[:4] if settings.JWT_SECRET_KEY else None
    }
