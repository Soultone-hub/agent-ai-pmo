from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from backend.database.db import get_db
from backend.models.user import User
from backend.services.auth_service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, get_current_user,
)
from backend.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentification"])

COOKIE_NAME = "refresh_token"
COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600  # secondes


# ── Schemas ──────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    role: str = "pmo"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _user_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
    }


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,       # True en production (HTTPS)
        max_age=COOKIE_MAX_AGE,
        path="/api/auth",   # cookie envoyé uniquement vers /api/auth/*
    )


# ── Register ─────────────────────────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email déjà utilisé")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        first_name=req.first_name,
        last_name=req.last_name,
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Auto-login après inscription
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, refresh_token)

    return {"access_token": access_token, "token_type": "bearer", "user": _user_response(user)}


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login")
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, refresh_token)

    return {"access_token": access_token, "token_type": "bearer", "user": _user_response(user)}


# ── Refresh ───────────────────────────────────────────────────────────────────
@router.post("/refresh")
def refresh_token_endpoint(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token manquant")

    user_id = decode_token(token, expected_type="refresh")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    new_access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))  # rotation du refresh token
    _set_refresh_cookie(response, new_refresh)

    return {"access_token": new_access, "token_type": "bearer"}


# ── Logout ────────────────────────────────────────────────────────────────────
@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/api/auth")
    return {"message": "Déconnecté"}


# ── Me ────────────────────────────────────────────────────────────────────────
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)
