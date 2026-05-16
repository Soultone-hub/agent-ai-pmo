# ─── Stage 1 : Builder ───────────────────────────────────────────────────────
# Installe les dépendances dans un environnement isolé
FROM python:3.11-slim AS builder

WORKDIR /app

# Dépendances système nécessaires à la compilation de psycopg2, PyMuPDF, spaCy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    libpq-dev \
    libffi-dev \
    libxml2-dev libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Télécharger le modèle spaCy français (NER pour l'anonymisation)
RUN python -m spacy download fr_core_news_lg


# ─── Stage 2 : Production ────────────────────────────────────────────────────
# Image finale allégée, sans outils de compilation
FROM python:3.11-slim AS production

WORKDIR /app

# Dépendances système runtime uniquement (pas de compilateurs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxml2 \
    && rm -rf /var/lib/apt/lists/*

# Copier les packages Python installés depuis le builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copier le code source (sans venv, tests, cache grâce au .dockerignore)
COPY . .

# Script de démarrage : migrations + lancement serveur
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Healthcheck pour que docker-compose sache quand le backend est prêt
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
