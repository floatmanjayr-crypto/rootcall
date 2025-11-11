# At the top of rootcall_portal.py, change this:
# from app.core.deps import get_current_user

# To this:
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.database import get_db
from app.models.user import User
import os

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme-super-secret-key")
ALGORITHM = "HS256"

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Get current user from JWT token - matches auth.py"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
