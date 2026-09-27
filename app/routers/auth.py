from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.errors import app_error
from app.http import ok
from app.models import User
from app.rate_limit import rate_limited
from app.schemas import LoginRequest, SignupRequest, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", dependencies=[Depends(rate_limited("auth"))])
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise app_error("EMAIL_TAKEN", "Email already registered")
    user = User(email=email, full_name=body.full_name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return ok(UserOut.model_validate(user), 201)


@router.post("/login", dependencies=[Depends(rate_limited("auth"))])
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise app_error("INVALID_CREDENTIALS", "Invalid email or password")
    token = TokenOut(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return ok(token)
