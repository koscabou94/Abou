"""
Point d'entrée principal de l'application FastAPI.
Initialise les services, configure les middlewares et enregistre les routes.
"""

import os
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database.connection import create_tables, check_db_connection
from app.database.models import FAQ
from app.routes import chat_router, faq_router, admin_router
from app.services import (
    LanguageService,
    TranslationService,
    NLPService,
    FAQService,
    KnowledgeService,
    ChatService,
)
from app.middleware.rate_limit import limiter

# === Configuration du logging structuré ===
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.DEBUG if settings.DEBUG else logging.INFO
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Gestionnaire de cycle de vie de l'application.
    Initialise les ressources au démarrage et les libère à l'arrêt.
    """
    # === DÉMARRAGE ===
    logger.info(
        "Démarrage du chatbot éducatif du Ministère de l'Éducation du Sénégal",
        version="1.0.0",
        debug=settings.DEBUG,
        lightweight_mode=settings.USE_LIGHTWEIGHT_MODE
    )

    # 1. Créer les tables de base de données
    logger.info("Initialisation de la base de données...")
    try:
        await create_tables()
        logger.info("Base de données initialisée avec succès")
    except Exception as exc:
        logger.error("Erreur initialisation base de données", error=str(exc))

    # 2. Initialiser les services
    logger.info("Initialisation des services...")

    app.state.language_service = LanguageService()
    app.state.translation_service = TranslationService(app.state.language_service)
    app.state.nlp_service = NLPService()
    app.state.faq_service = FAQService()
    app.state.knowledge_service = KnowledgeService(faq_service=app.state.faq_service)

    app.state.chat_service = ChatService(
        language_service=app.state.language_service,
        translation_service=app.state.translation_service,
        nlp_service=app.state.nlp_service,
        faq_service=app.state.faq_service,
        knowledge_service=app.state.knowledge_service,
    )

    logger.info("Services initialisés avec succès")

    # 3. Connexion Redis
    app.state.redis_client = None
    if not settings.USE_LIGHTWEIGHT_MODE:
        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.ping()
            app.state.redis_client = redis_client
            logger.info("Connexion Redis établie")
        except Exception as exc:
            logger.warning("Redis indisponible, cache désactivé", error=str(exc))

    # 4. Réimporter les FAQ depuis le fichier JSON à chaque démarrage
    #    (garantit que les nouvelles FAQ sont toujours prises en compte)
    logger.info("Rechargement des FAQ depuis le fichier JSON...")
    try:
        from app.database.connection import AsyncSessionLocal, check_db_connection
        from sqlalchemy import select, func, delete

        db_ok = await check_db_connection()
        if not db_ok:
            raise Exception("BD inaccessible")

        async with AsyncSessionLocal() as db:
            # Compter les FAQ existantes
            count_result = await db.execute(select(func.count(FAQ.id)))
            faq_count = count_result.scalar() or 0

            # Vérifier si le fichier JSON a changé (comparaison rapide)
            import os
            json_path = settings.FAQ_DATA_PATH
            need_reseed = False

            if faq_count == 0:
                need_reseed = True
                logger.info("Base FAQ vide, import nécessaire")
            elif os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                json_faq_count = len(json_data.get("faqs", []))
                if json_faq_count != faq_count:
                    need_reseed = True
                    logger.info(
                        "Nombre de FAQ différent, réimport nécessaire",
                        json_count=json_faq_count,
                        db_count=faq_count
                    )

            if need_reseed:
                # Supprimer toutes les anciennes FAQ
                logger.info("Suppression des anciennes FAQ...")
                await db.execute(delete(FAQ))
                await db.commit()
                logger.info("Anciennes FAQ supprimées")

                # Réimporter depuis le JSON
                imported = await app.state.faq_service.seed_from_json(
                    settings.FAQ_DATA_PATH, db
                )
                logger.info("FAQ réimportées avec succès", count=imported)
            else:
                logger.info("FAQ à jour, chargement en cache...", count=faq_count)
                await app.state.faq_service.load_faqs(db)

    except Exception as exc:
        logger.warning("BD inaccessible, chargement FAQ depuis JSON", error=str(exc))
        try:
            faq_count = await app.state.faq_service.load_from_json_direct(settings.FAQ_DATA_PATH)
            if faq_count > 0:
                logger.info("FAQ chargées depuis JSON (fallback BD)", count=faq_count)
        except Exception as exc2:
            logger.error("Erreur lors du chargement des FAQ", error=str(exc2))

    # 5. Initialiser la base de connaissances
    logger.info("Chargement de la base de connaissances...")
    try:
        kb_ok = await app.state.knowledge_service.initialize()
        if kb_ok:
            logger.info(
                "Base de connaissances chargée",
                documents=app.state.knowledge_service.document_count
            )
        else:
            logger.warning("Base de connaissances non disponible")
    except Exception as exc:
        logger.error("Erreur lors du chargement de la base de connaissances", error=str(exc))

    # 6. Chargement anticipé des modèles d'IA (Eager Loading)
    # TF-IDF ne nécessite pas de pré-chargement de modèle lourd
    logger.info("Modèle TF-IDF prêt (pas de pré-chargement nécessaire)")

    logger.info(
        "Application prête",
        host=settings.HOST,
        port=settings.PORT,
        docs_url="/docs"
    )

    yield

    # === ARRÊT ===
    logger.info("Arrêt de l'application...")

    if app.state.redis_client:
        await app.state.redis_client.aclose()
        logger.info("Connexion Redis fermée")

    logger.info("Application arrêtée proprement")


# === Création de l'application FastAPI ===
app = FastAPI(
    title="Chatbot Éducatif - Ministère de l'Éducation du Sénégal",
    description="""
    API du chatbot éducatif multilingue du Ministère de l'Éducation du Sénégal.

    Supporte les langues suivantes :
    - **Français** (fr) - Langue principale
    - **Wolof** (wo) - Langue nationale du Sénégal
    - **Pulaar/Fula** (ff) - Langue peule
    - **Arabe** (ar) - Arabe standard

    Fonctionnalités :
    - Réponses aux questions éducatives via FAQ sémantique
    - Génération de réponses par LLM (Mistral 7B)
    - Traduction automatique multilingue (NLLB-200)
    - Historique de conversation par session
    """,
    version="1.0.0",
    contact={
        "name": "Ministère de l'Éducation du Sénégal",
        "url": "https://education.gouv.sn",
    },
    license_info={
        "name": "Usage gouvernemental",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# === Rate limiting ===
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# === Middleware CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# === Middleware de logging des requêtes ===
@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Journalise toutes les requêtes entrantes avec leurs métriques."""
    import time

    start_time = time.time()

    # Enrichir le contexte de log avec les infos de la requête
    structlog.contextvars.bind_contextvars(
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown",
    )

    try:
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Ne pas logger les health checks pour éviter le bruit
        if request.url.path not in ("/health", "/"):
            logger.info(
                "Requête traitée",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        return response
    except Exception as exc:
        logger.error(
            "Erreur non gérée",
            error=str(exc),
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Erreur interne du serveur"}
        )
    finally:
        structlog.contextvars.unbind_contextvars("method", "path", "client_ip")


# === Enregistrement des routes ===
app.include_router(chat_router, prefix="/api")
app.include_router(faq_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


# === Health check public ===
@app.get(
    "/health",
    tags=["Système"],
    summary="Vérification basique de santé",
    description="Endpoint de health check simple pour les load balancers."
)
async def health_check() -> dict:
    """Retourne l'état de santé basique de l'application."""
    return {
        "status": "healthy",
        "service": "chatbot-educatif-senegal",
        "version": "1.0.0",
    }


# === Fichiers statiques (frontend) ===
# En production Docker, le frontend est copié dans /app/frontend
# En développement, il est dans ../../frontend par rapport au backend
_docker_frontend = "/app/frontend"
_dev_frontend = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
frontend_path = _docker_frontend if os.path.exists(_docker_frontend) else _dev_frontend

if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
    logger.info("Interface frontend montée", path=frontend_path)


# === Page d'accueil (fallback si frontend absent) ===
# Note: la route "/" est gérée par StaticFiles si le frontend existe.
# Ce endpoint ne sera atteint que si le dossier frontend est absent.
@app.get("/info", include_in_schema=False)
async def root() -> Response:
    return JSONResponse({
        "message": "Chatbot Éducatif du Ministère de l'Éducation du Sénégal",
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api",
        "health": "/health",
        "supported_languages": settings.SUPPORTED_LANGUAGES,
    })


# === Point d'entrée pour le développement ===
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS,
        log_level="debug" if settings.DEBUG else "info",
    )
