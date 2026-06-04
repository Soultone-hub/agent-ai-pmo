from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import datetime
import uuid

from backend.database.db import get_db
from backend.models.user import User
from backend.services.auth_service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, get_current_user,
)
from backend.services.email_service import (
    send_reset_password_email,
    send_welcome_email,
    send_verification_email,
)
from backend.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentification"])

# Import du limiter global (défini dans main.py)
from backend.limiter import limiter

COOKIE_NAME = "refresh_token"
COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600  # secondes


# ── Schemas ──────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    first_name: str
    last_name: str


class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


def _user_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_confirmed": user.is_confirmed,
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
@limiter.limit("10/minute")  # Max 10 créations de compte par IP/min
def register(request: Request, req: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email déjà utilisé")

    # Génération du token de confirmation email
    token = str(uuid.uuid4())

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        first_name=req.first_name,
        last_name=req.last_name,
        is_confirmed=False,
        confirmation_token=token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Envoi des emails (non bloquant en cas d'erreur SMTP)
    try:
        send_welcome_email(user.email, req.first_name)
        send_verification_email(user.email, req.first_name, token)
    except Exception as e:
        print(f"[WARNING] Emails non envoyés lors de l'inscription: {e}")

    # Auto-login après inscription
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, refresh_token)

    return {"access_token": access_token, "token_type": "bearer", "user": _user_response(user)}


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login")
@limiter.limit("10/minute")  # Max 10 tentatives de connexion par IP/min
def login(request: Request, req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, str(user.password_hash)):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if getattr(user, "archived_at", None):
        if datetime.datetime.now() > user.archived_at + datetime.timedelta(days=90):
            raise HTTPException(status_code=403, detail="Compte définitivement supprimé.")
        else:
            user.archived_at = None
            db.commit()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, refresh_token)

    return {"access_token": access_token, "token_type": "bearer", "user": _user_response(user)}


# ── Password Reset ────────────────────────────────────────────────────────────
@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(request: Request, req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if user:
        token = str(uuid.uuid4())
        user.reset_password_token = token
        user.reset_password_expires = datetime.datetime.now() + datetime.timedelta(hours=1)
        db.commit()
        send_reset_password_email(user.email, token)
        
    return {"message": "Si cet email existe, un lien de réinitialisation a été envoyé."}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.reset_password_token == req.token,
        User.reset_password_token.isnot(None)
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Jeton invalide ou expiré")
        
    if user.reset_password_expires and datetime.datetime.now() > user.reset_password_expires:
        raise HTTPException(status_code=400, detail="Jeton invalide ou expiré")
        
    user.password_hash = hash_password(req.new_password)
    user.reset_password_token = None
    user.reset_password_expires = None
    db.commit()
    
    return {"message": "Mot de passe réinitialisé avec succès"}


# ── Verify Email ──────────────────────────────────────────────────────────────
@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Endpoint de confirmation d'adresse email via le lien reçu par email."""
    user = db.query(User).filter(
        User.confirmation_token == token,
        User.confirmation_token.isnot(None),
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Lien de vérification invalide ou déjà utilisé.")

    user.is_confirmed = True
    user.confirmation_token = None
    db.commit()

    return {"message": "Adresse email confirmée avec succès. Vous pouvez maintenant utiliser toutes les fonctionnalités."}


# ── Resend Verification Email ─────────────────────────────────────────────────
@router.post("/resend-verification")
@limiter.limit("3/minute")
def resend_verification(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Renvoie l'email de vérification si le compte n'est pas encore confirmé."""
    if current_user.is_confirmed:
        return {"message": "Votre adresse email est déjà confirmée."}

    token = str(uuid.uuid4())
    current_user.confirmation_token = token
    db.commit()

    try:
        send_verification_email(current_user.email, current_user.first_name or "", token)
    except Exception as e:
        print(f"[WARNING] Renvoi email de vérification échoué: {e}")
        raise HTTPException(status_code=500, detail="Impossible d'envoyer l'email de vérification.")

    return {"message": "Email de vérification renvoyé."}


# ── Refresh ───────────────────────────────────────────────────────────────────
@router.post("/refresh")
def refresh_token_endpoint(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token manquant")

    user_id = decode_token(token, expected_type="refresh")
    import uuid
    try:
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalide")
    user = db.query(User).filter(User.id == user_uuid).first()
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

@router.put("/me")
def update_me(req: UpdateProfileRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.first_name = req.first_name
    current_user.last_name = req.last_name
    db.commit()
    return _user_response(current_user)

@router.put("/me/password")
def update_password(req: UpdatePasswordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(req.current_password, str(current_user.password_hash)):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "Mot de passe mis à jour"}

@router.delete("/me")
def delete_me(response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.archived_at = datetime.datetime.now()
    db.commit()
    # On déconnecte l'utilisateur
    response.delete_cookie(key=COOKIE_NAME, path="/api/auth")
    return {"message": "Compte archivé en vue de suppression"}
