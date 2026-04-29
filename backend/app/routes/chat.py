"""
Routes API pour le chat - endpoint principal du chatbot éducatif.
Gère les messages entrants, l'historique et la suppression des sessions.
"""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database.connection import get_db
from app.middleware.auth import validate_session_id
from app.middleware.rate_limit import limiter
from app.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# === Modèles Pydantic ===

class ChatRequest(BaseModel):
    """Modèle de requête pour l'endpoint de chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Message de l'utilisateur (1 à 1000 caractères)"
    )
    session_id: str = Field(
        ...,
        description="Identifiant de session UUID"
    )
    language: Optional[str] = Field(
        None,
        description="Forcer une langue spécifique (fr, wo, ff, ar) - ignore la détection auto"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        """Valide le format UUID du session_id."""
        if not validate_session_id(v):
            raise ValueError("session_id doit être un UUID valide")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """Valide que la langue est supportée."""
        if v is not None and v not in settings.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Langue non supportée. Langues valides : {settings.SUPPORTED_LANGUAGES}"
            )
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Quelles sont les dates d'inscription pour l'année scolaire?",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "language": None
            }
        }


class ClarificationData(BaseModel):
    """Données de clarification renvoyées au frontend pour afficher des boutons de choix."""
    options: list[str] = Field(..., description="Liste des options proposées à l'utilisateur")


class ChatResponse(BaseModel):
    """Modèle de réponse de l'endpoint de chat."""

    response: str = Field(..., description="Réponse générée par le chatbot")
    session_id: str = Field(..., description="Identifiant de session")
    language: str = Field(..., description="Langue détectée de l'utilisateur")
    intent: str = Field(..., description="Intention classifiée de la question")
    confidence: float = Field(..., description="Score de confiance de la classification")
    source: str = Field(..., description="Source de la réponse : 'faq' ou 'llm'")
    response_time_ms: int = Field(..., description="Temps de traitement en millisecondes")
    timestamp: str = Field(..., description="Horodatage de la réponse (ISO 8601)")
    clarification: Optional[ClarificationData] = Field(
        None,
        description="Options de clarification à afficher comme boutons cliquables (si besoin)"
    )
    suggestions: Optional[list[str]] = Field(
        default=None,
        description="2-3 questions de relance contextuelles à proposer à l'utilisateur"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Les inscriptions se déroulent généralement de juillet à septembre...",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "language": "fr",
                "intent": "inscription",
                "confidence": 0.85,
                "source": "faq",
                "response_time_ms": 245,
                "timestamp": "2024-09-01T10:30:00Z",
                "clarification": None
            }
        }


class MessageHistory(BaseModel):
    """Modèle d'un message dans l'historique."""

    id: int
    role: str
    content: str
    language: str
    intent: Optional[str]
    source: Optional[str]
    timestamp: Optional[str]


class HistoryResponse(BaseModel):
    """Modèle de réponse pour l'historique de conversation."""

    session_id: str
    messages: list[MessageHistory]
    total: int


class NewSessionResponse(BaseModel):
    """Modèle de réponse pour la création d'une session."""

    session_id: str
    message: str


# === Endpoints ===

@router.post(
    "",
    response_model=ChatResponse,
    summary="Envoyer un message au chatbot",
    description="Endpoint principal pour interagir avec le chatbot éducatif du Ministère."
)
@limiter.limit("20/minute")
async def send_message(
    request: Request,
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Traite un message utilisateur et retourne une réponse du chatbot.

    Le pipeline de traitement inclut :
    - Détection automatique de la langue (français, wolof, pulaar, arabe)
    - Traduction vers le français (langue pivot)
    - Classification de l'intention
    - Recherche dans les FAQ avec correspondance sémantique
    - Génération de réponse par le LLM (Mistral 7B via Ollama)
    - Traduction de la réponse vers la langue de l'utilisateur
    """
    # Obtenir le service de chat depuis l'état de l'application
    chat_service = request.app.state.chat_service

    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de chat n'est pas disponible"
        )

    logger.info(
        "Requête de chat reçue",
        session_id=chat_request.session_id[:8],
        message_length=len(chat_request.message)
    )

    result = await chat_service.process_message(
        user_message=chat_request.message,
        session_id=chat_request.session_id,
        db=db,
        language_override=chat_request.language,
    )

    # Vérifier si une erreur s'est produite
    if result.get("intent") == "error":
        logger.warning("Erreur de traitement", session_id=chat_request.session_id[:8])

    # Construire la clarification si présente (boutons de choix pour le frontend)
    clarification_data = None
    raw_clarification = result.get("clarification")
    if raw_clarification and raw_clarification.get("options"):
        clarification_data = ClarificationData(options=raw_clarification["options"])

    return ChatResponse(
        response=result["response"],
        session_id=result["session_id"],
        language=result["language"],
        intent=result["intent"],
        confidence=result.get("confidence", 0.0),
        source=result["source"],
        response_time_ms=result.get("response_time_ms", 0),
        timestamp=result["timestamp"],
        clarification=clarification_data,
        suggestions=result.get("suggestions") or None,
    )


@router.get(
    "/session/new",
    response_model=NewSessionResponse,
    summary="Créer une nouvelle session",
    description="Génère un identifiant de session UUID pour un nouvel utilisateur."
)
async def create_session() -> NewSessionResponse:
    """Crée un nouvel identifiant de session pour l'utilisateur."""
    new_session_id = str(uuid.uuid4())
    logger.info("Nouvelle session créée", session_id=new_session_id[:8])

    return NewSessionResponse(
        session_id=new_session_id,
        message="Session créée avec succès. Utilisez ce session_id pour toutes vos requêtes."
    )


@router.get(
    "/history/{session_id}",
    response_model=HistoryResponse,
    summary="Obtenir l'historique de conversation",
    description="Récupère l'historique des messages pour une session donnée."
)
@limiter.limit("30/minute")
async def get_history(
    request: Request,
    session_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """
    Retourne l'historique de conversation pour une session.

    Args:
        session_id: Identifiant de session UUID
        limit: Nombre maximum de messages (défaut: 20, max: 100)
    """
    if not validate_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id invalide : doit être un UUID valide"
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le paramètre 'limit' doit être entre 1 et 100"
        )

    chat_service = request.app.state.chat_service

    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de chat n'est pas disponible"
        )

    history = await chat_service.get_session_history(session_id, db, limit=limit)

    messages = [
        MessageHistory(
            id=msg["id"],
            role=msg["role"],
            content=msg["content"],
            language=msg["language"],
            intent=msg.get("intent"),
            source=msg.get("source"),
            timestamp=msg.get("timestamp"),
        )
        for msg in history
    ]

    return HistoryResponse(
        session_id=session_id,
        messages=messages,
        total=len(messages)
    )


@router.delete(
    "/history/{session_id}",
    summary="Effacer l'historique de conversation",
    description="Efface tout l'historique de conversation pour une session donnée."
)
@limiter.limit("10/minute")
async def clear_history(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Efface l'historique de conversation pour une session.

    Args:
        session_id: Identifiant de session UUID
    """
    if not validate_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id invalide : doit être un UUID valide"
        )

    chat_service = request.app.state.chat_service

    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de chat n'est pas disponible"
        )

    success = await chat_service.clear_session(session_id, db)

    if success:
        logger.info("Historique effacé", session_id=session_id[:8])
        return {"message": "Historique de conversation effacé avec succès", "session_id": session_id}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression de l'historique"
        )
