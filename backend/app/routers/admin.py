# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.rootcall_call_log import RootCallCallLog

router = APIRouter(tags=["Admin"])

def is_admin(user_id: int, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    return user and user.is_superuser

@router.get("/api/admin/dashboard/{admin_id}")
async def admin_dashboard(admin_id: int, db: Session = Depends(get_db)):
    if not is_admin(admin_id, db):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    total_users = db.query(User).count()
    total_numbers = db.query(PhoneNumber).filter(PhoneNumber.is_active == True).count()
    total_calls = db.query(RootCallCallLog).count()
    spam_blocked = db.query(RootCallCallLog).filter(RootCallCallLog.action == "spam_blocked").count()
    
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    
    return {
        "stats": {
            "total_users": total_users,
            "total_shield_numbers": total_numbers,
            "total_calls": total_calls,
            "spam_blocked": spam_blocked
        },
        "recent_users": [
            {"id": u.id, "email": u.email, "full_name": u.full_name}
            for u in recent_users
        ]
    }

@router.get("/api/admin/users/{admin_id}")
async def get_all_users(admin_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    if not is_admin(admin_id, db):
        raise HTTPException(status_code=403)
    
    users = db.query(User).offset(skip).limit(limit).all()
    
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ],
        "total": db.query(User).count()
    }
