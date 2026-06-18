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

echo "🔄 Exécution des migrations Alembic..."
alembic upgrade head

echo "🚀 Démarrage du serveur FastAPI..."
# 1 worker : chaque worker recharge spaCy lg + embeddings (RAM) et écrit sur le
# même ChromaDB embarqué (verrous SQLite). Augmenter seulement avec un Chroma serveur.
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
