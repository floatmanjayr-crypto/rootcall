import re

with open('app/routers/auth.py', 'r') as f:
    content = f.read()

# Replace the get_me function
old_function = '''@router.get("/api/auth/me")
async def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401)
        return {"id": user.id, "email": user.email, "full_name": user.full_name}
    except JWTError:
        raise HTTPException(status_code=401)'''

new_function = '''@router.get("/api/auth/me")
async def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {"id": user.id, "email": user.email, "full_name": user.full_name}
    except JWTError as e:
        # Return detailed error for debugging
        raise HTTPException(status_code=401, detail=f"JWT Error: {type(e).__name__} - {str(e)}")'''

content = content.replace(old_function, new_function)

with open('app/routers/auth.py', 'w') as f:
    f.write(content)

print("✅ Updated get_me function with detailed errors")
