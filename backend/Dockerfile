# ============================================================
# EduBot Sénégal - Dockerfile Cloud (sans modèles ML lourds)
# Image ~200MB au lieu de ~4GB
# ============================================================

FROM python:3.11-slim

LABEL maintainer="Ministère de l'Éducation du Sénégal"
LABEL description="Chatbot éducatif - Backend FastAPI"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python (depuis la racine du projet)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code backend
COPY backend/app ./app

# Copier les données FAQ et base de connaissances
COPY data/ /data/

# Copier le frontend
COPY frontend/ /app/frontend/

# Port d'écoute
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Démarrage
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
