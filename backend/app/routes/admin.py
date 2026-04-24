"""
Routes d'administration pour la gestion du système.
Inclut l'import en masse de FAQ, les statistiques et le contrôle des modèles.
"""

import os
import psutil
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from app.database.connection import get_db, check_db_connection
from app.database.models import FAQ, User, Conversation, Message
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Administration"])


# === Modèles Pydantic ===

class HealthStatus(BaseModel):
    """Statut de santé détaillé du système."""
    status: str
    timestamp: str
    version: str
    services: dict
    system: dict


class ImportResult(BaseModel):
    """Résultat d'un import de FAQ."""
    imported: int
    failed: int
    total: int
    message: str


class StatsResponse(BaseModel):
    """Statistiques d'utilisation du système."""
    total_users: int
    total_conversations: int
    total_messages: int
    faq_hits: int
    llm_calls: int
    languages: dict
    top_intents: list[dict]
    top_faqs: list[dict]
    period: str


# === Endpoints ===

@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Vérification détaillée de santé",
    description="Retourne l'état de santé détaillé de tous les composants du système."
)
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> HealthStatus:
    """
    Vérification complète de la santé du système.
    Teste la base de données, Redis, Ollama et les modèles NLP.
    """
    services = {}

    # Test base de données
    try:
        db_ok = await check_db_connection()
        services["database"] = {"status": "healthy" if db_ok else "unhealthy"}
    except Exception as exc:
        services["database"] = {"status": "error", "error": str(exc)}

    # Test Redis
    try:
        redis_client = request.app.state.redis_client
        if redis_client and not settings.USE_LIGHTWEIGHT_MODE:
            await redis_client.ping()
            services["redis"] = {"status": "healthy"}
        else:
            services["redis"] = {"status": "disabled" if settings.USE_LIGHTWEIGHT_MODE else "not_configured"}
    except Exception as exc:
        services["redis"] = {"status": "error", "error": str(exc)}

    # Test Groq LLM
    services["llm"] = {
        "status": "cloud",
        "provider": "Groq",
        "model": settings.LLM_MODEL,
        "api_key_set": bool(settings.GROQ_API_KEY),
    }

    # Statut des modèles NLP
    nlp_service = request.app.state.nlp_service
    faq_service = request.app.state.faq_service
    translation_service = request.app.state.translation_service

    services["nlp_models"] = {
        "groq_client_ready": nlp_service._groq_client is not None if nlp_service else False,
        "embedding_model_loaded": faq_service._model_loaded if faq_service else False,
        "translation_model_loaded": translation_service.is_available if translation_service else False,
        "faq_cache_size": len(faq_service._faq_cache) if faq_service else 0,
    }

    # Métriques système
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=0.1)

    system_info = {
        "cpu_percent": cpu_percent,
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "memory_used_percent": memory.percent,
        "memory_available_gb": round(memory.available / (1024 ** 3), 2),
    }

    # Statut global
    critical_services = ["database"]
    overall_status = "healthy"
    for svc in critical_services:
        if services.get(svc, {}).get("status") not in ("healthy", "disabled"):
            overall_status = "degraded"
            break

    return HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        services=services,
        system=system_info
    )


@router.post(
    "/import-faq",
    response_model=ImportResult,
    summary="Importer des FAQ en masse",
    description="Importe un fichier JSON de FAQ dans la base de données."
)
async def import_faq(
    request: Request,
    file: UploadFile = File(..., description="Fichier JSON contenant les FAQ"),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> ImportResult:
    """
    Importe des FAQ depuis un fichier JSON uploadé.

    Format attendu :
    {
        "faqs": [
            {
                "question": "...",
                "answer": "...",
                "category": "...",
                "language": "fr",
                "tags": ["tag1", "tag2"]
            }
        ]
    }
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit être au format JSON (.json)"
        )

    # Limite de taille : 10MB
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux (maximum 10MB)"
        )

    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"JSON invalide : {str(exc)}"
        )

    faqs_data = data.get("faqs", [])
    if not faqs_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier JSON ne contient aucune FAQ (clé 'faqs' manquante ou vide)"
        )

    faq_service = request.app.state.faq_service
    imported = 0
    failed = 0

    for faq_data in faqs_data:
        try:
            if not faq_data.get("question") or not faq_data.get("answer"):
                failed += 1
                continue

            lang = faq_data.get("language", "fr")
            if lang not in settings.SUPPORTED_LANGUAGES:
                lang = "fr"

            await faq_service.add_faq(
                question=faq_data["question"],
                answer=faq_data["answer"],
                category=faq_data.get("category", "general"),
                lang=lang,
                tags=faq_data.get("tags", []),
                db=db
            )
            imported += 1
        except Exception as exc:
            logger.warning("Erreur import FAQ individuelle", error=str(exc))
            failed += 1

    await db.commit()
    logger.info(
        "Import FAQ terminé",
        imported=imported,
        failed=failed,
        total=len(faqs_data)
    )

    return ImportResult(
        imported=imported,
        failed=failed,
        total=len(faqs_data),
        message=f"{imported} FAQ importées avec succès, {failed} erreurs"
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Statistiques d'utilisation",
    description="Retourne les statistiques d'utilisation du chatbot."
)
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> StatsResponse:
    """Retourne des statistiques agrégées sur l'utilisation du chatbot."""

    # Nombre total d'utilisateurs
    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar() or 0

    # Nombre total de conversations
    convs_result = await db.execute(select(func.count(Conversation.id)))
    total_conversations = convs_result.scalar() or 0

    # Nombre total de messages
    msgs_result = await db.execute(select(func.count(Message.id)))
    total_messages = msgs_result.scalar() or 0

    # Répartition des sources (faq vs llm)
    faq_result = await db.execute(
        select(func.count(Message.id)).where(Message.source == "faq", Message.role == "assistant")
    )
    faq_hits = faq_result.scalar() or 0

    llm_result = await db.execute(
        select(func.count(Message.id)).where(Message.source == "llm", Message.role == "assistant")
    )
    llm_calls = llm_result.scalar() or 0

    # Répartition par langue
    lang_fr = await db.execute(
        select(func.count(Message.id)).where(Message.language == "fr", Message.role == "user")
    )
    lang_wo = await db.execute(
        select(func.count(Message.id)).where(Message.language == "wo", Message.role == "user")
    )
    lang_ff = await db.execute(
        select(func.count(Message.id)).where(Message.language == "ff", Message.role == "user")
    )
    lang_ar = await db.execute(
        select(func.count(Message.id)).where(Message.language == "ar", Message.role == "user")
    )

    languages = {
        "fr": lang_fr.scalar() or 0,
        "wo": lang_wo.scalar() or 0,
        "ff": lang_ff.scalar() or 0,
        "ar": lang_ar.scalar() or 0,
    }

    # Top intentions
    intent_stmt = (
        select(Message.intent, func.count(Message.id).label("count"))
        .where(Message.role == "user", Message.intent.isnot(None))
        .group_by(Message.intent)
        .order_by(func.count(Message.id).desc())
        .limit(5)
    )
    intent_result = await db.execute(intent_stmt)
    top_intents = [
        {"intent": intent, "count": count}
        for intent, count in intent_result.all()
    ]

    # Top FAQ
    faq_stmt = (
        select(FAQ.id, FAQ.question, FAQ.category, FAQ.view_count)
        .where(FAQ.is_active == True)
        .order_by(FAQ.view_count.desc())
        .limit(5)
    )
    faq_result = await db.execute(faq_stmt)
    top_faqs = [
        {"id": faq_id, "question": question[:80], "category": category, "views": views or 0}
        for faq_id, question, category, views in faq_result.all()
    ]

    return StatsResponse(
        total_users=total_users,
        total_conversations=total_conversations,
        total_messages=total_messages,
        faq_hits=faq_hits,
        llm_calls=llm_calls,
        languages=languages,
        top_intents=top_intents,
        top_faqs=top_faqs,
        period="global"
    )


@router.post(
    "/reload-models",
    summary="Recharger les modèles NLP",
    description="Force le rechargement des modèles NLP et du cache FAQ."
)
async def reload_models(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> dict:
    """
    Recharge les modèles NLP et invalide le cache FAQ.
    Utile après une mise à jour des modèles ou des données FAQ.
    """
    results = {}

    # Recharger le cache FAQ
    try:
        faq_service = request.app.state.faq_service
        if faq_service:
            # Vider le cache pour forcer le rechargement
            faq_service._faq_cache = []
            faq_service._faq_embeddings = None
            # Recharger depuis la base de données
            await faq_service.load_faqs(db)
            results["faq_cache"] = {
                "status": "reloaded",
                "count": len(faq_service._faq_cache)
            }
    except Exception as exc:
        logger.error("Erreur rechargement cache FAQ", error=str(exc))
        results["faq_cache"] = {"status": "error", "error": str(exc)}

    logger.info("Rechargement des modèles terminé", results=results)

    return {
        "message": "Rechargement terminé",
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.delete(
    "/clear-conversations",
    summary="Effacer toutes les conversations",
    description="Efface l'historique complet des conversations (ATTENTION : irréversible)."
)
async def clear_all_conversations(
    confirm: bool = False,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> dict:
    """
    Efface toutes les conversations (opération irréversible).
    Requiert le paramètre confirm=true pour éviter les suppressions accidentelles.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ajoutez ?confirm=true pour confirmer la suppression. Cette opération est irréversible."
        )

    from sqlalchemy import update
    from app.database.models import Conversation

    stmt = update(Conversation).values(is_active=False)
    await db.execute(stmt)
    await db.flush()

    logger.warning("Toutes les conversations ont été effacées par un administrateur")

    return {
        "message": "Toutes les conversations ont été effacées",
        "timestamp": datetime.utcnow().isoformat()
    }
