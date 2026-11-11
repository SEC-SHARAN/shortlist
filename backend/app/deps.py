from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, AuditLog
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        user = db.get(User, int(payload["sub"]))
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if not user or not user.is_active:
        raise HTTPException(401, "Account disabled")
    return user


def require(*roles: str):
    """RBAC dependency: `Depends(require('admin','recruiter'))`."""
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Requires role: {' or '.join(roles)}")
        return user
    return dep


def audit(db: Session, user: User | None, action: str, entity: str | None = None, entity_id: int | None = None,
          detail: dict | None = None, request: Request | None = None, email: str | None = None):
    db.add(AuditLog(user_id=user.id if user else None, user_email=user.email if user else email, action=action,
                    entity=entity, entity_id=entity_id, detail=detail or {},
                    ip=(request.client.host if request and request.client else None)))
