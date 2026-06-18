#!/bin/bash
set -e

echo "⏳ Attente de la base de données PostgreSQL..."
# Attendre que Postgres soit prêt avant de continuer
until python -c "
import os, psycopg2
try:
    psycopg2.connect(os.environ['DATABASE_URL'])
    print('✅ PostgreSQL prêt.')
except Exception as e:
    print(f'⏳ PostgreSQL pas encore prêt : {e}')
    exit(1)
"; do
  sleep 2
done

echo "🔄 Initialisation du schéma de base de données..."
# Sur une base vierge, il n'existe pas de migration initiale créant les tables de
# base (users/projects/documents) — elles l'étaient via create_all() en dev. On
# crée donc toutes les tables directement depuis les modèles (source de vérité),
# puis on marque la base au niveau de la dernière migration pour la cohérence.
python -c "
from backend.database.db import Base, engine
from backend.models import user, project, document, analysis, chat_message  # noqa: F401 (enregistre les tables)
Base.metadata.create_all(engine)
print('✅ Schéma synchronisé (create_all).')
"
alembic stamp head

echo "🚀 Démarrage du serveur FastAPI..."
# 1 worker : chaque worker recharge spaCy lg + embeddings (RAM) et écrit sur le
# même ChromaDB embarqué (verrous SQLite). Augmenter seulement avec un Chroma serveur.
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
