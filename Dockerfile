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

# Télécharger les modèles spaCy français : lg (détection NER) + sm (validation)
RUN python -m spacy download fr_core_news_lg \
    && python -m spacy download fr_core_news_sm

# Pré-télécharger le modèle d'embeddings (chargé en mode hors-ligne au runtime).
# Indispensable : rag_service.py le charge avec local_files_only=True → sans ce
# cache, le backend planterait au démarrage.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', cache_folder='/app/models_cache')"


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

# Copier le cache du modèle d'embeddings téléchargé au build
# (models_cache/ est exclu par .dockerignore → on prend celui du builder)
COPY --from=builder /app/models_cache /app/models_cache

# Copier le code source (sans venv, tests, cache grâce au .dockerignore)
COPY . .

# Script de démarrage : migrations + lancement serveur
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Healthcheck pour que docker-compose sache quand le backend est prêt.
# On utilise Python (curl n'est PAS installé dans l'image de production).
# start-period long car le chargement des modèles (spaCy lg + embeddings) est lent.
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
