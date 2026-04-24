"""
Routes API pour la gestion des FAQ.
Inclut la lecture publique et la gestion administrative (CRUD).
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
import structlog

from app.database.connection import get_db
from app.database.models import FAQ
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/faq", tags=["FAQ"])


# === Modèles Pydantic ===

class FAQResponse(BaseModel):
    """Modèle de réponse pour une FAQ."""
    id: int
    question: str
    answer: str
    category: str
    language: str
    tags: list[str]
    view_count: int
    is_active: bool

    class Config:
        from_attributes = True


class FAQCreateRequest(BaseModel):
    """Modèle de création d'une FAQ."""
    question: str = Field(..., min_length=5, max_length=500)
    answer: str = Field(..., min_length=10, max_length=2000)
    category: str = Field(..., min_length=2, max_length=50)
    language: str = Field(default="fr")
    tags: list[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Comment s'inscrire à l'école primaire?",
                "answer": "Pour inscrire votre enfant à l'école primaire, vous devez...",
                "category": "inscription",
                "language": "fr",
                "tags": ["inscription", "primaire", "école"]
            }
        }


class FAQUpdateRequest(BaseModel):
    """Modèle de mise à jour d'une FAQ."""
    question: Optional[str] = Field(None, min_length=5, max_length=500)
    answer: Optional[str] = Field(None, min_length=10, max_length=2000)
    category: Optional[str] = Field(None, min_length=2, max_length=50)
    language: Optional[str] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None


class FAQListResponse(BaseModel):
    """Modèle de réponse pour la liste des FAQ."""
    faqs: list[FAQResponse]
    total: int
    category: Optional[str]


class FAQSearchResponse(BaseModel):
    """Modèle de réponse pour la recherche de FAQ."""
    results: list[dict]
    query: str
    total: int


# === Endpoints publics ===

@router.get(
    "",
    response_model=FAQListResponse,
    summary="Lister toutes les FAQ",
    description="Retourne toutes les FAQ actives avec filtrage optionnel par catégorie."
)
@limiter.limit("100/minute")
async def list_faqs(
    request: Request,
    category: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> FAQListResponse:
    """
    Retourne la liste des FAQ actives.

    Args:
        category: Filtrer par catégorie (inscription, examen, etc.)
        language: Filtrer par langue (fr, wo, ff, ar)
        limit: Nombre maximum de résultats (défaut: 50)
        offset: Décalage pour la pagination
    """
    stmt = select(FAQ).where(FAQ.is_active == True)

    if category:
        stmt = stmt.where(FAQ.category == category)

    if language:
        if language not in settings.SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Langue non supportée. Valeurs valides : {settings.SUPPORTED_LANGUAGES}"
            )
        stmt = stmt.where(FAQ.language == language)

    # Comptage total
    count_stmt = stmt
    result = await db.execute(stmt.offset(offset).limit(min(limit, 200)))
    faqs = result.scalars().all()

    faq_responses = []
    for faq in faqs:
        faq_responses.append(FAQResponse(
            id=faq.id,
            question=faq.question,
            answer=faq.answer,
            category=faq.category,
            language=faq.language,
            tags=faq.get_tags(),
            view_count=faq.view_count or 0,
            is_active=faq.is_active,
        ))

    logger.debug("FAQ listées", count=len(faq_responses), category=category)

    return FAQListResponse(
        faqs=faq_responses,
        total=len(faq_responses),
        category=category
    )


@router.get(
    "/search",
    response_model=FAQSearchResponse,
    summary="Rechercher dans les FAQ",
    description="Recherche sémantique dans les FAQ avec score de pertinence."
)
@limiter.limit("60/minute")
async def search_faqs(
    request: Request,
    q: str,
    limit: int = 5,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> FAQSearchResponse:
    """
    Effectue une recherche sémantique dans les FAQ.

    Args:
        q: Requête de recherche
        limit: Nombre maximum de résultats (défaut: 5, max: 20)
        category: Filtrer par catégorie
    """
    if not q or len(q.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La requête de recherche doit contenir au moins 3 caractères"
        )

    limit = min(limit, 20)

    faq_service = request.app.state.faq_service
    if not faq_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service FAQ n'est pas disponible"
        )

    results = await faq_service.search_faqs(q.strip(), limit=limit, category=category)

    logger.debug("Recherche FAQ effectuée", query=q[:50], results=len(results))

    return FAQSearchResponse(
        results=results,
        query=q,
        total=len(results)
    )


@router.get(
    "/categories",
    summary="Lister les catégories de FAQ",
    description="Retourne la liste de toutes les catégories de FAQ disponibles."
)
@limiter.limit("100/minute")
async def list_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retourne les catégories de FAQ avec le nombre de questions par catégorie."""
    from sqlalchemy import func

    stmt = (
        select(FAQ.category, func.count(FAQ.id).label("count"))
        .where(FAQ.is_active == True)
        .group_by(FAQ.category)
        .order_by(FAQ.category)
    )
    result = await db.execute(stmt)
    categories = result.all()

    return {
        "categories": [
            {"name": cat, "count": count}
            for cat, count in categories
        ]
    }


@router.get(
    "/{faq_id}",
    response_model=FAQResponse,
    summary="Obtenir une FAQ par ID",
)
@limiter.limit("100/minute")
async def get_faq(
    request: Request,
    faq_id: int,
    db: AsyncSession = Depends(get_db),
) -> FAQResponse:
    """Récupère une FAQ spécifique par son identifiant."""
    stmt = select(FAQ).where(FAQ.id == faq_id, FAQ.is_active == True)
    result = await db.execute(stmt)
    faq = result.scalar_one_or_none()

    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FAQ avec l'id {faq_id} non trouvée"
        )

    # Incrémenter le compteur de vues
    faq.view_count = (faq.view_count or 0) + 1
    await db.flush()

    return FAQResponse(
        id=faq.id,
        question=faq.question,
        answer=faq.answer,
        category=faq.category,
        language=faq.language,
        tags=faq.get_tags(),
        view_count=faq.view_count,
        is_active=faq.is_active,
    )


# === Endpoints administrateurs (requièrent une clé API) ===

@router.post(
    "",
    response_model=FAQResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une FAQ",
    description="Ajoute une nouvelle FAQ (administration uniquement)."
)
async def create_faq(
    request: Request,
    faq_data: FAQCreateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> FAQResponse:
    """
    Crée une nouvelle FAQ avec calcul automatique de l'embedding.
    Requiert une clé API administrateur.
    """
    if faq_data.language not in settings.SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Langue non supportée : {faq_data.language}"
        )

    faq_service = request.app.state.faq_service

    new_faq = await faq_service.add_faq(
        question=faq_data.question,
        answer=faq_data.answer,
        category=faq_data.category,
        lang=faq_data.language,
        tags=faq_data.tags,
        db=db
    )

    logger.info("FAQ créée par l'admin", faq_id=new_faq.id, category=faq_data.category)

    return FAQResponse(
        id=new_faq.id,
        question=new_faq.question,
        answer=new_faq.answer,
        category=new_faq.category,
        language=new_faq.language,
        tags=new_faq.get_tags(),
        view_count=0,
        is_active=True,
    )


@router.put(
    "/{faq_id}",
    response_model=FAQResponse,
    summary="Modifier une FAQ",
    description="Met à jour une FAQ existante (administration uniquement)."
)
async def update_faq(
    request: Request,
    faq_id: int,
    faq_data: FAQUpdateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> FAQResponse:
    """
    Met à jour une FAQ existante. Recalcule l'embedding si la question change.
    Requiert une clé API administrateur.
    """
    stmt = select(FAQ).where(FAQ.id == faq_id)
    result = await db.execute(stmt)
    faq = result.scalar_one_or_none()

    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FAQ avec l'id {faq_id} non trouvée"
        )

    # Mettre à jour les champs fournis
    question_changed = False

    if faq_data.question is not None:
        faq.question = faq_data.question
        question_changed = True

    if faq_data.answer is not None:
        faq.answer = faq_data.answer

    if faq_data.category is not None:
        faq.category = faq_data.category

    if faq_data.language is not None:
        if faq_data.language not in settings.SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Langue non supportée : {faq_data.language}"
            )
        faq.language = faq_data.language

    if faq_data.tags is not None:
        faq.set_tags(faq_data.tags)

    if faq_data.is_active is not None:
        faq.is_active = faq_data.is_active

    await db.flush()

    # Recalculer l'embedding si la question a changé
    if question_changed:
        faq_service = request.app.state.faq_service
        await faq_service.update_faq_embedding(faq_id, db)

    logger.info("FAQ mise à jour", faq_id=faq_id)

    return FAQResponse(
        id=faq.id,
        question=faq.question,
        answer=faq.answer,
        category=faq.category,
        language=faq.language,
        tags=faq.get_tags(),
        view_count=faq.view_count or 0,
        is_active=faq.is_active,
    )


@router.delete(
    "/{faq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une FAQ",
    description="Désactive une FAQ (suppression logique, administration uniquement)."
)
async def delete_faq(
    faq_id: int,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> None:
    """
    Désactive une FAQ (suppression logique - la FAQ n'est pas physiquement supprimée).
    Requiert une clé API administrateur.
    """
    stmt = select(FAQ).where(FAQ.id == faq_id)
    result = await db.execute(stmt)
    faq = result.scalar_one_or_none()

    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FAQ avec l'id {faq_id} non trouvée"
        )

    faq.is_active = False
    await db.flush()

    logger.info("FAQ désactivée", faq_id=faq_id)
