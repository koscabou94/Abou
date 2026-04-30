"""
Endpoint de feedback utilisateur (👍 / 👎) sur les réponses du chatbot.

Persiste les votes dans un fichier JSONL append-only (data/feedback.jsonl)
pour permettre une analyse offline ultérieure :
  - taux d'approbation par intent / par source
  - questions fréquemment notées négativement (à corriger)
  - répartition cache vs LLM vs FAQ officielle

Pas de DB : append-only fichier suffit pour le volume attendu et reste
compatible avec le plan Render gratuit (disque éphémère mais regénéré).
"""

import json
import os
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Request, status, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.middleware.auth import validate_session_id
from app.middleware.rate_limit import limiter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["Feedback"])


def _resolve_feedback_path() -> str:
    """Résout le chemin du fichier de log feedback."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_root = os.path.dirname(base_dir)
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "feedback.jsonl")


class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="Identifiant UUID de la session")
    vote: str = Field(..., description="'up' ou 'down'")
    intent: Optional[str] = None
    source: Optional[str] = None
    question: Optional[str] = Field(None, max_length=2000)
    answer: Optional[str] = Field(None, max_length=2000)

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        if not validate_session_id(v):
            raise ValueError("session_id doit être un UUID valide")
        return v

    @field_validator("vote")
    @classmethod
    def validate_vote(cls, v: str) -> str:
        if v not in ("up", "down"):
            raise ValueError("vote doit être 'up' ou 'down'")
        return v


@router.post(
    "",
    summary="Envoyer un feedback sur une réponse du bot",
    description="Enregistre un vote 👍/👎 utilisateur pour piloter l'amélioration.",
)
@limiter.limit("30/minute")
async def submit_feedback(request: Request, payload: FeedbackRequest) -> dict:
    """Reçoit un vote et l'append dans data/feedback.jsonl."""
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": payload.session_id,
        "vote": payload.vote,
        "intent": payload.intent,
        "source": payload.source,
        # Tronquer aux limites Pydantic + retirer les sauts de ligne pour JSONL
        "question": (payload.question or "").replace("\n", " ")[:500],
        "answer_excerpt": (payload.answer or "").replace("\n", " ")[:500],
    }

    try:
        path = _resolve_feedback_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(
            "Feedback enregistré",
            vote=payload.vote,
            intent=payload.intent,
            source=payload.source,
        )
        return {"status": "ok", "message": "Merci pour votre retour"}
    except Exception as exc:
        logger.error("Erreur enregistrement feedback", error=str(exc))
        # Ne pas faire échouer l'utilisateur si le disque est plein :
        # le vote reste persisté côté localStorage frontend
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service feedback temporairement indisponible",
        )


@router.get(
    "/stats",
    summary="Statistiques agrégées des feedbacks",
    description="Retourne le nombre de votes 👍/👎 par intent et par source.",
)
@limiter.limit("10/minute")
async def feedback_stats(request: Request) -> dict:
    """Lit data/feedback.jsonl et calcule des stats simples."""
    path = _resolve_feedback_path()
    if not os.path.exists(path):
        return {"total": 0, "up": 0, "down": 0, "by_intent": {}, "by_source": {}}

    total = up = down = 0
    by_intent: dict[str, dict[str, int]] = {}
    by_source: dict[str, dict[str, int]] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                vote = rec.get("vote")
                if vote not in ("up", "down"):
                    continue
                total += 1
                if vote == "up":
                    up += 1
                else:
                    down += 1
                intent = rec.get("intent") or "unknown"
                source = rec.get("source") or "unknown"
                by_intent.setdefault(intent, {"up": 0, "down": 0})[vote] += 1
                by_source.setdefault(source, {"up": 0, "down": 0})[vote] += 1
    except Exception as exc:
        logger.error("Erreur lecture feedback.jsonl", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lecture statistiques",
        )

    return {
        "total": total,
        "up": up,
        "down": down,
        "approval_rate": round(up / total, 3) if total else None,
        "by_intent": by_intent,
        "by_source": by_source,
    }
