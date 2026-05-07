"""
Routes pour la gestion des candidatures volontaires.

Endpoints :
  POST /api/volunteer/apply          → Soumettre une candidature (questionnaire + doc)
  GET  /api/volunteer/status         → Statut de ma candidature
  GET  /api/admin/volunteers         → Liste toutes les candidatures (admin)
  POST /api/admin/volunteers/{id}/review → Approuver ou rejeter (admin)
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database.connection import get_db
from app.database.models import User, VolunteerApplication
from app.middleware.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["volunteer"])

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads" / "volunteer_docs"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _is_admin(user: User) -> bool:
    return (user.profile_type or "") in ("admin", "superviseur")


def _is_tutor_or_admin(user: User) -> bool:
    return (user.profile_type or "") in ("admin", "superviseur", "tuteur", "enseignant")


# ─────────────────────────────────────────────────────────────────
# CANDIDATURE VOLONTAIRE
# ─────────────────────────────────────────────────────────────────

@router.post("/api/volunteer/apply")
async def apply_as_volunteer(
    request: Request,
    motivation: str = Form(...),
    experience: str = Form(...),
    education: str = Form(...),
    subjects: str = Form(...),
    levels: str = Form(...),
    availability: str = Form(default="both"),
    document: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soumet une candidature de volontaire avec le questionnaire et un document optionnel.
    """
    # Vérifier que l'utilisateur est bien un volontaire
    if current_user.profile_type != "volontaire":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les volontaires peuvent soumettre une candidature.",
        )

    # Vérifier si une candidature existe déjà
    existing = await db.execute(
        select(VolunteerApplication).where(VolunteerApplication.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vous avez déjà soumis une candidature.",
        )

    # Valider les champs JSON
    try:
        subjects_list = json.loads(subjects) if subjects.startswith("[") else [subjects]
        levels_list = json.loads(levels) if levels.startswith("[") else [levels]
    except Exception:
        subjects_list = [subjects]
        levels_list = [levels]

    if not subjects_list:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins une matière.")
    if not levels_list:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins un niveau.")
    if not motivation.strip() or len(motivation.strip()) < 50:
        raise HTTPException(status_code=400, detail="La lettre de motivation doit faire au moins 50 caractères.")

    # Gérer l'upload du document
    doc_path = None
    doc_name = None
    if document and document.filename:
        ext = Path(document.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Format non autorisé. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}",
            )
        content = await document.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 5 Mo).")

        _ensure_upload_dir()
        filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = UPLOAD_DIR / filename
        with open(filepath, "wb") as f:
            f.write(content)
        doc_path = str(filepath)
        doc_name = document.filename

    # Créer la candidature
    application = VolunteerApplication(
        user_id=current_user.id,
        motivation=motivation.strip(),
        experience=experience.strip(),
        education=education.strip(),
        subjects=json.dumps(subjects_list),
        levels=json.dumps(levels_list),
        availability=availability,
        document_path=doc_path,
        document_name=doc_name,
        status="pending",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)

    logger.info("Candidature volontaire soumise", user_id=current_user.id, app_id=application.id)
    return {
        "success": True,
        "application_id": application.id,
        "status": "pending",
        "message": "Votre candidature a été soumise. Un superviseur la traitera prochainement.",
    }


@router.get("/api/volunteer/status")
async def get_my_application_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne le statut de la candidature du volontaire connecté."""
    result = await db.execute(
        select(VolunteerApplication).where(VolunteerApplication.user_id == current_user.id)
    )
    app = result.scalar_one_or_none()
    if not app:
        return {"has_application": False, "status": None}
    return {"has_application": True, **app.to_dict()}


# ─────────────────────────────────────────────────────────────────
# GESTION ADMIN
# ─────────────────────────────────────────────────────────────────

@router.get("/api/admin/volunteers")
async def list_volunteer_applications(
    request: Request,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liste toutes les candidatures de volontaires.
    Accessible aux admins, superviseurs et enseignants.
    """
    if not _is_tutor_or_admin(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux superviseurs.")

    query = select(VolunteerApplication).order_by(VolunteerApplication.created_at.desc())
    if status_filter:
        query = query.where(VolunteerApplication.status == status_filter)

    result = await db.execute(query)
    applications = result.scalars().all()

    output = []
    for app in applications:
        applicant = await db.get(User, app.user_id)
        output.append({
            **app.to_dict(),
            "applicant_name": applicant.full_name if applicant else "Inconnu",
            "applicant_email": applicant.email if applicant else None,
        })
    return output


@router.post("/api/admin/volunteers/{application_id}/review")
async def review_volunteer_application(
    application_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approuve ou rejette une candidature de volontaire."""
    if not _is_tutor_or_admin(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux superviseurs.")

    body = await request.json()
    decision = body.get("decision")  # "approved" ou "rejected"
    notes = body.get("notes", "")

    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision doit être 'approved' ou 'rejected'.")

    app = await db.get(VolunteerApplication, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Candidature introuvable.")

    app.status = decision
    app.reviewer_id = current_user.id
    app.reviewer_notes = notes
    app.reviewed_at = datetime.utcnow()

    # Si approuvé, mettre à jour le profile_type de l'utilisateur
    if decision == "approved":
        applicant = await db.get(User, app.user_id)
        if applicant:
            applicant.profile_type = "tuteur"

    await db.commit()
    return {
        "success": True,
        "application_id": application_id,
        "status": decision,
        "message": "Candidature approuvée." if decision == "approved" else "Candidature rejetée.",
    }
