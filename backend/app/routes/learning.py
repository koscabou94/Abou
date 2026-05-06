"""
Routes API pour le système d'apprentissage progressif EduBot.

Endpoints :
  POST /api/learning/diagnostic/start     → Démarre/récupère le diagnostic
  POST /api/learning/diagnostic/submit    → Soumet les réponses au diagnostic
  GET  /api/learning/dashboard            → Tableau de bord élève
  GET  /api/learning/lessons              → Liste des leçons débloquées
  GET  /api/learning/lessons/{id}         → Contenu d'une leçon
  POST /api/learning/lessons/{id}/complete → Valide une leçon avec les exercices
  GET  /api/learning/grades               → Carnet de notes
  POST /api/learning/help                 → Demande d'aide (tuteur ou IA)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database.connection import get_db
from app.database.models import User
from app.middleware.auth import get_current_user
from app.services.learning_service import LearningService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/learning", tags=["learning"])
learning_service = LearningService()


# ─── Schémas Pydantic ────────────────────────────────────────────

class DiagnosticAnswer(BaseModel):
    question_id: str
    answer: str


class DiagnosticSubmitRequest(BaseModel):
    answers: List[DiagnosticAnswer]


class ExerciseAnswer(BaseModel):
    exercise_id: int
    answer: str


class LessonCompleteRequest(BaseModel):
    answers: List[ExerciseAnswer]


class HelpRequest(BaseModel):
    message: str
    lesson_id: Optional[int] = None
    exercise_id: Optional[int] = None
    request_type: str = "ai"  # "ai" | "tutor" | "both"


# ─── Endpoints ───────────────────────────────────────────────────

@router.post("/diagnostic/start")
async def start_diagnostic(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Démarre le diagnostic EduBot ou retourne le diagnostic en cours.
    Appelé automatiquement à la connexion de l'élève.
    """
    try:
        result = await learning_service.get_or_create_diagnostic(db, current_user)
        return result
    except Exception as e:
        logger.error("Erreur diagnostic start", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnostic/submit")
async def submit_diagnostic(
    body: DiagnosticSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soumet les réponses au diagnostic et retourne le niveau évalué
    ainsi que le parcours personnalisé recommandé.
    """
    try:
        answers = [{"question_id": a.question_id, "answer": a.answer}
                   for a in body.answers]
        result = await learning_service.submit_diagnostic_answers(db, current_user, answers)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Erreur diagnostic submit", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retourne le tableau de bord complet de l'élève :
    progression par matière, leçons débloquées, scores.
    """
    try:
        data = await learning_service.get_student_dashboard(db, current_user)
        return data
    except Exception as e:
        logger.error("Erreur dashboard", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lessons/{lesson_id}")
async def get_lesson(
    lesson_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retourne le contenu complet d'une leçon et ses exercices.
    La leçon doit être débloquée pour l'élève.
    """
    try:
        data = await learning_service.start_lesson(db, current_user, lesson_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Erreur get_lesson", error=str(e), lesson_id=lesson_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lessons/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: int,
    body: LessonCompleteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soumet les réponses aux exercices d'une leçon.
    Si score >= 50%, la leçon est validée et la suivante débloquée.
    """
    try:
        answers = [{"exercise_id": a.exercise_id, "answer": a.answer}
                   for a in body.answers]
        result = await learning_service.complete_lesson(db, current_user, lesson_id, answers)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Erreur complete_lesson", error=str(e), lesson_id=lesson_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/grades")
async def get_grades(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne le carnet de notes complet de l'élève."""
    try:
        data = await learning_service.get_student_grades(db, current_user)
        return data
    except Exception as e:
        logger.error("Erreur get_grades", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/help")
async def request_help(
    body: HelpRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crée une demande d'aide de l'élève.
    request_type = 'ai' → réponse automatique via EduBot
    request_type = 'tutor' → notification au tuteur assigné
    request_type = 'both' → les deux
    """
    try:
        result = await learning_service.create_help_request(
            db, current_user,
            message=body.message,
            lesson_id=body.lesson_id,
            exercise_id=body.exercise_id,
            request_type=body.request_type,
        )
        return {"success": True, "request": result}
    except Exception as e:
        logger.error("Erreur help request", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Endpoints Tuteur ────────────────────────────────────────────

class TutorReplyRequest(BaseModel):
    response: str


@router.get("/tutor/students")
async def get_tutor_students(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retourne la liste des élèves assignés au tuteur connecté,
    avec leur progression et scores moyens.
    """
    from app.database.models import StudentProgress, Lesson, Grade
    from sqlalchemy import select, func

    try:
        # Vérifier que l'utilisateur est bien un tuteur
        profile = getattr(current_user, "profile_type", None) or getattr(current_user, "role", None)
        if profile not in ("tuteur", "enseignant", "volontaire", "admin"):
            raise HTTPException(status_code=403, detail="Accès réservé aux tuteurs")

        # Récupérer tous les élèves (pour l'instant, un tuteur voit tous les élèves du système)
        # En production : filtrer par tutor_id dans une table d'assignation
        students_query = await db.execute(
            select(User).where(User.profile_type == "eleve")
        )
        students = students_query.scalars().all()

        result = []
        for student in students:
            # Progression
            prog_query = await db.execute(
                select(StudentProgress).where(StudentProgress.user_id == student.id)
            )
            prog_records = prog_query.scalars().all()
            done = [p for p in prog_records if p.status == "completed"]
            lessons_done = len(done)
            lessons_total = len(prog_records)

            # Score moyen
            grades_query = await db.execute(
                select(func.avg(Grade.points_earned)).where(Grade.user_id == student.id)
            )
            avg_raw = grades_query.scalar()
            avg_score = round(float(avg_raw), 1) if avg_raw else 0

            # Progression par matière
            subjects_data = {}
            for p in done:
                lesson = await db.get(Lesson, p.lesson_id)
                if lesson:
                    subj = lesson.subject
                    if subj not in subjects_data:
                        subjects_data[subj] = {"scores": [], "done": 0}
                    subjects_data[subj]["scores"].append(p.score or 0)
                    subjects_data[subj]["done"] += 1

            subjects = {
                k: round(sum(v["scores"]) / len(v["scores"])) if v["scores"] else 0
                for k, v in subjects_data.items()
            }

            progress_pct = round(lessons_done / lessons_total * 100) if lessons_total > 0 else 0

            result.append({
                "id": student.id,
                "full_name": student.full_name or student.ien or student.session_id[:8],
                "level": student.level or "—",
                "lessons_done": lessons_done,
                "lessons_total": lessons_total,
                "progress_pct": progress_pct,
                "avg_score": avg_score,
                "subjects": subjects,
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur tutor students", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tutor/requests")
async def get_tutor_requests(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retourne toutes les demandes d'aide destinées aux tuteurs,
    avec les informations sur l'élève et la leçon concernée.
    """
    from app.database.models import TutorRequest, Lesson
    from sqlalchemy import select

    try:
        profile = getattr(current_user, "profile_type", None) or getattr(current_user, "role", None)
        if profile not in ("tuteur", "enseignant", "volontaire", "admin"):
            raise HTTPException(status_code=403, detail="Accès réservé aux tuteurs")

        query = await db.execute(
            select(TutorRequest)
            .where(TutorRequest.request_type.in_(["tutor", "both"]))
            .order_by(TutorRequest.created_at.desc())
            .limit(100)
        )
        requests = query.scalars().all()

        result = []
        for req in requests:
            student = await db.get(User, req.student_id)
            lesson = await db.get(Lesson, req.lesson_id) if req.lesson_id else None

            result.append({
                "id": req.id,
                "student_id": req.student_id,
                "student_name": (student.full_name or student.ien or student.session_id[:8]) if student else "Élève inconnu",
                "lesson_title": lesson.title if lesson else None,
                "message": req.message,
                "request_type": req.request_type,
                "status": req.status,
                "response": req.response,
                "created_at": req.created_at.isoformat() if req.created_at else None,
                "responded_at": req.responded_at.isoformat() if req.responded_at else None,
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur tutor requests", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tutor/requests/{request_id}/reply")
async def reply_to_request(
    request_id: int,
    body: TutorReplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permet au tuteur de répondre à une demande d'aide d'un élève.
    Met à jour le statut et envoie la réponse.
    """
    from app.database.models import TutorRequest
    from datetime import datetime

    try:
        profile = getattr(current_user, "profile_type", None) or getattr(current_user, "role", None)
        if profile not in ("tuteur", "enseignant", "volontaire", "admin"):
            raise HTTPException(status_code=403, detail="Accès réservé aux tuteurs")

        req = await db.get(TutorRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Demande introuvable")

        req.response = body.response
        req.status = "answered"
        req.tutor_id = current_user.id
        req.responded_at = datetime.utcnow()

        await db.commit()
        await db.refresh(req)

        return {"success": True, "request_id": request_id, "status": "answered"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur tutor reply", error=str(e), request_id=request_id)
        raise HTTPException(status_code=500, detail=str(e))
