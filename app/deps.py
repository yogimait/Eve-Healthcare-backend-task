from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import app_error
from app.models import User
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise app_error("UNAUTHORIZED", "Authentication required")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise app_error("INVALID_TOKEN", "Invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise app_error("INVALID_TOKEN", "Invalid or expired token")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise app_error("ADMIN_REQUIRED", "Admin privileges required")
    return user
