from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user, require, audit
from ..models import User
from ..schemas import LoginIn, PasswordChange, UserCreate, UserUpdate, UserOut
from ..security import verify_password, hash_password, create_token, password_policy_error

router = APIRouter(prefix="/api", tags=["auth"])
MAX_FAILS, LOCK_MIN = 5, 15


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    now = datetime.now(timezone.utc)
    if user and user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(429, "Account temporarily locked after repeated failures. Try again later.")
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILS:
                user.locked_until = now + timedelta(minutes=LOCK_MIN); user.failed_logins = 0
        audit(db, None, "login_failed", "user", user.id if user else None, {"email": email}, request, email)
        db.commit()
        raise HTTPException(401, "Invalid email or password")   # same message for unknown user / wrong password
    user.failed_logins, user.locked_until = 0, None
    audit(db, user, "login", "user", user.id, request=request)
    db.commit()
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer", "user": UserOut.model_validate(user)}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/auth/password")
def change_password(body: PasswordChange, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if (err := password_policy_error(body.new_password)):
        raise HTTPException(422, err)
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "password_changed", "user", user.id, request=request); db.commit()
    return {"ok": True}


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(require("admin")), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    if (err := password_policy_error(body.password)):
        raise HTTPException(422, err)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "A user with this email already exists")
    u = User(email=email, name=body.name, role=body.role, password_hash=hash_password(body.password))
    db.add(u); db.flush()
    audit(db, admin, "user_created", "user", u.id, {"role": u.role}, request); db.commit()
    return u


@router.patch("/users/{uid}", response_model=UserOut)
def update_user(uid: int, body: UserUpdate, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if uid == admin.id and (data.get("is_active") is False or ("role" in data and data["role"] != "admin")):
        raise HTTPException(400, "You cannot demote or deactivate yourself")
    if "password" in data:
        if (err := password_policy_error(data["password"])):
            raise HTTPException(422, err)
        u.password_hash = hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(u, k, v)
    audit(db, admin, "user_updated", "user", u.id, {k: v for k, v in data.items()}, request); db.commit()
    return u
