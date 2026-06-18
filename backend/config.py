from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    GROQ_API_KEY: str
    CHROMA_PATH: str = "./chroma_db"
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@pilotia.com"
    FRONTEND_URL: str = "http://localhost:5173"

    # Purge RGPD des comptes archivés (suppression douce → définitive)
    PURGE_SCHEDULER_ENABLED: bool = True   # planificateur quotidien intégré
    PURGE_RETENTION_DAYS: int = 90         # fenêtre de récupération avant purge

    class Config:
        env_file = ".env"
        extra = "ignore"   # ignorer les variables d'env non déclarées (ex: TRANSFORMERS_OFFLINE)

settings = Settings()