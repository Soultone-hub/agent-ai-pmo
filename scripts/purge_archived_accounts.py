"""
Purge manuelle des comptes archivés au-delà de la fenêtre de rétention RGPD.

Utile pour un déclenchement externe (cron, tâche planifiée) ou un one-shot,
en complément du planificateur intégré à l'application.

Usage (depuis backend_FastAPI/agent-ia-pmo/) :
    python scripts/purge_archived_accounts.py
"""
import os
import sys
import logging

# Permettre l'import de `backend` quel que soit le mode d'invocation
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from backend.config import settings
from backend.database.db import SessionLocal
from backend.services.maintenance_service import purge_archived_users


def main() -> None:
    db = SessionLocal()
    try:
        result = purge_archived_users(db, retention_days=settings.PURGE_RETENTION_DAYS)
        print(f"Purge terminée : {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
