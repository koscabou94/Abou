# Chatbot Éducatif — Ministère de l'Éducation du Sénégal

Assistant éducatif intelligent multilingue pour le système scolaire sénégalais.
Supporte le **français**, le **wolof**, le **pulaar** et l'**arabe**.

## Architecture

Le chatbot traite chaque message selon ce pipeline :

1. **Détection de langue** — heuristiques wolof/pulaar + langdetect + détection de script arabe
2. **Traduction vers le français** — NLLB-200 (langue pivot : français)
3. **Classification d'intention** — 8 catégories par mots-clés (inscription, examen, bourse…)
4. **Recherche FAQ** — similarité cosinus avec sentence-transformers (all-MiniLM-L6-v2)
5. **Recherche base de connaissances** — documents sur le système éducatif (RAG)
6. **Génération LLM** — Ollama/Mistral 7B (fallback TinyLlama)
7. **Traduction retour** — NLLB-200 vers la langue de l'utilisateur
8. **Sauvegarde** — PostgreSQL (conversations, messages, statistiques)

## Stack technique

| Composant | Technologie |
|-----------|------------|
| Backend | FastAPI + Uvicorn |
| Base de données | PostgreSQL 16 (ou SQLite en mode allégé) |
| Cache | Redis 7 |
| LLM | Ollama (Mistral 7B) + TinyLlama (fallback) |
| Traduction | facebook/nllb-200-distilled-600M |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Frontend | HTML/CSS/JS vanilla (sans frameworks) |
| Proxy | Nginx |
| Conteneurs | Docker Compose |

## Démarrage rapide

```bash
# 1. Cloner le projet
git clone <url-du-repo>
cd edu-chatbot

# 2. Configurer l'environnement
cp .env.example .env
# Modifier les valeurs dans .env (mots de passe, clés...)

# 3. Lancer avec Docker
docker compose up -d

# 4. Ouvrir dans le navigateur
# http://localhost
```

Le script `scripts/setup.sh` automatise l'installation complète (prérequis, .env, modèles, migrations).

## Mode allégé (sans GPU/Docker)

Pour les environnements à ressources limitées :

```bash
docker compose -f docker-compose.lite.yml up -d
```

Ce mode utilise SQLite, désactive Redis et Ollama, et se replie sur TinyLlama.

## Démo standalone (sans Docker)

```bash
pip install fastapi uvicorn
python demo.py
# Ouvrir http://localhost:8000
```

## Structure du projet

```
edu-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py              # Point d'entrée FastAPI
│   │   ├── config.py            # Configuration (pydantic-settings)
│   │   ├── database/            # Modèles SQLAlchemy + connexion
│   │   ├── routes/              # Endpoints API (chat, faq, admin)
│   │   ├── services/            # Logique métier
│   │   │   ├── chat_service.py      # Orchestrateur principal
│   │   │   ├── language_service.py  # Détection de langue
│   │   │   ├── translation_service.py # Traduction NLLB-200
│   │   │   ├── nlp_service.py       # LLM + classification
│   │   │   ├── faq_service.py       # Recherche FAQ sémantique
│   │   │   └── knowledge_service.py # Base de connaissances (RAG)
│   │   └── middleware/          # Auth + rate limiting
│   ├── alembic/                 # Migrations de base de données
│   ├── tests/                   # Tests pytest
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                    # Interface web (HTML/CSS/JS)
├── data/                        # Données FAQ + connaissances
├── nginx/                       # Configuration Nginx
├── scripts/                     # Scripts d'installation
├── docker-compose.yml           # Stack complète
├── docker-compose.lite.yml      # Stack allégée
└── .env.example                 # Template de configuration
```

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `POST /api/chat` | POST | Envoyer un message au chatbot |
| `GET /api/chat/history/{session_id}` | GET | Historique de conversation |
| `DELETE /api/chat/history/{session_id}` | DELETE | Effacer l'historique |
| `GET /api/faq` | GET | Lister les FAQ |
| `GET /api/faq/search?q=...` | GET | Rechercher dans les FAQ |
| `GET /api/admin/health` | GET | Santé détaillée (admin) |
| `GET /api/admin/stats` | GET | Statistiques d'utilisation |
| `POST /api/admin/faq/import` | POST | Importer des FAQ (JSON) |
| `GET /health` | GET | Healthcheck simple |
| `GET /docs` | GET | Documentation Swagger (mode debug) |

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

## Langues supportées

| Code | Langue | Détection | Traduction |
|------|--------|-----------|------------|
| `fr` | Français | langdetect | pivot |
| `wo` | Wolof | heuristiques (mots-clés) | NLLB-200 |
| `ff` | Pulaar | heuristiques (mots-clés) | NLLB-200 |
| `ar` | Arabe | détection de script | NLLB-200 |

## Licence

Usage gouvernemental — Ministère de l'Éducation Nationale du Sénégal.
