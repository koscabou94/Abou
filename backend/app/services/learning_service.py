"""
Service d'apprentissage progressif EduBot.

Gère :
- Le diagnostic initial par matière (EduBot pose des questions à la connexion)
- La création et le déblocage progressif des leçons (style Moodle)
- La soumission et la correction des exercices
- Le calcul des notes et la progression de l'élève
- Les demandes d'aide vers le tuteur ou l'IA
"""

import json
from datetime import datetime, timezone
from typing import Optional
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.database.models import (
    User, Lesson, Exercise, StudentProgress,
    Grade, DiagnosticSession, TutorRequest
)

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────────
# Questions de diagnostic par niveau et matière
# Alignées sur le curriculum CEB officiel sénégalais
# ─────────────────────────────────────────────────────────────────
DIAGNOSTIC_QUESTIONS = {
    "CI": {
        "francais": [
            {
                "id": "ci_fr_1",
                "question": "Combien de lettres y a-t-il dans le mot 'chat' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "3"}, {"label": "B", "text": "4"}, {"label": "C", "text": "5"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "ci_fr_2",
                "question": "Quel mot commence par la lettre 'M' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "papa"}, {"label": "B", "text": "maison"}, {"label": "C", "text": "soleil"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "ci_fr_3",
                "question": "Complète : 'Bonjour, je m'___ Aminata.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "appelle"}, {"label": "B", "text": "appel"}, {"label": "C", "text": "appelles"}],
                "correct": "A",
                "points": 1
            },
        ],
        "mathematiques": [
            {
                "id": "ci_math_1",
                "question": "Combien font 2 + 3 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "4"}, {"label": "B", "text": "5"}, {"label": "C", "text": "6"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "ci_math_2",
                "question": "Quel nombre vient après 7 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "6"}, {"label": "B", "text": "8"}, {"label": "C", "text": "9"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "ci_math_3",
                "question": "J'ai 5 mangues. J'en donne 2. Combien m'en reste-t-il ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "2"}, {"label": "B", "text": "3"}, {"label": "C", "text": "7"}],
                "correct": "B",
                "points": 1
            },
        ],
    },
    "CP": {
        "francais": [
            {
                "id": "cp_fr_1",
                "question": "Quel est le pluriel de 'cheval' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "chevals"}, {"label": "B", "text": "chevaux"}, {"label": "C", "text": "chevales"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "cp_fr_2",
                "question": "Quelle phrase est correcte ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le chat mange une souris."}, {"label": "B", "text": "Mange chat le souris."}, {"label": "C", "text": "Chat le mange souris."}],
                "correct": "A",
                "points": 1
            },
            {
                "id": "cp_fr_3",
                "question": "Quel mot est un verbe ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "maison"}, {"label": "B", "text": "courir"}, {"label": "C", "text": "beau"}],
                "correct": "B",
                "points": 1
            },
        ],
        "mathematiques": [
            {
                "id": "cp_math_1",
                "question": "Combien font 15 + 8 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "21"}, {"label": "B", "text": "23"}, {"label": "C", "text": "22"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "cp_math_2",
                "question": "Quel nombre est le plus grand ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "34"}, {"label": "B", "text": "43"}, {"label": "C", "text": "38"}],
                "correct": "B",
                "points": 1
            },
        ],
    },
    "CE1": {
        "francais": [
            {
                "id": "ce1_fr_1",
                "question": "Quel est le féminin de 'directeur' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "directrice"}, {"label": "B", "text": "directeure"}, {"label": "C", "text": "directoresse"}],
                "correct": "A",
                "points": 1
            },
            {
                "id": "ce1_fr_2",
                "question": "Dans la phrase 'Fatou lit un livre', quel est le sujet ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "lit"}, {"label": "B", "text": "Fatou"}, {"label": "C", "text": "livre"}],
                "correct": "B",
                "points": 1
            },
        ],
        "mathematiques": [
            {
                "id": "ce1_math_1",
                "question": "Combien font 45 + 37 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "72"}, {"label": "B", "text": "82"}, {"label": "C", "text": "83"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "ce1_math_2",
                "question": "Combien y a-t-il de dizaines dans 80 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "8"}, {"label": "B", "text": "80"}, {"label": "C", "text": "18"}],
                "correct": "A",
                "points": 1
            },
        ],
    },
    "CE2": {
        "francais": [
            {
                "id": "ce2_fr_1",
                "question": "Mets ce verbe au passé composé : 'je mange'",
                "type": "qcm",
                "options": [{"label": "A", "text": "j'ai mangé"}, {"label": "B", "text": "je mangeai"}, {"label": "C", "text": "j'avais mangé"}],
                "correct": "A",
                "points": 1
            },
        ],
        "mathematiques": [
            {
                "id": "ce2_math_1",
                "question": "Combien font 7 × 8 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "54"}, {"label": "B", "text": "56"}, {"label": "C", "text": "58"}],
                "correct": "B",
                "points": 1
            },
            {
                "id": "ce2_math_2",
                "question": "Quelle est la moitié de 124 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "60"}, {"label": "B", "text": "62"}, {"label": "C", "text": "64"}],
                "correct": "B",
                "points": 1
            },
        ],
    },
    "CM1": {
        "francais": [
            {
                "id": "cm1_fr_1",
                "question": "Identifie le complément d'objet direct : 'Omar mange une banane.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "Omar"}, {"label": "B", "text": "mange"}, {"label": "C", "text": "une banane"}],
                "correct": "C",
                "points": 1
            },
        ],
        "mathematiques": [
            {
                "id": "cm1_math_1",
                "question": "Combien font 324 ÷ 4 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "81"}, {"label": "B", "text": "82"}, {"label": "C", "text": "80"}],
                "correct": "A",
                "points": 1
            },
            {
                "id": "cm1_math_2",
                "question": "Quel est le périmètre d'un carré de côté 6 cm ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "12 cm"}, {"label": "B", "text": "24 cm"}, {"label": "C", "text": "36 cm"}],
                "correct": "B",
                "points": 1
            },
        ],
    },
    "CM2": {
        "francais": [
            {
                "id": "cm2_fr_1",
                "question": "Quel est le mode de ce verbe : 'Que tu viennes !'",
                "type": "qcm",
                "options": [{"label": "A", "text": "indicatif"}, {"label": "B", "text": "subjonctif"}, {"label": "C", "text": "impératif"}],
                "correct": "B",
                "points": 1
            },
        ],
        "mathematiques": [
            {
                "id": "cm2_math_1",
                "question": "Quel est 15% de 200 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "25"}, {"label": "B", "text": "30"}, {"label": "C", "text": "35"}],
                "correct": "B",
                "points": 1
            },
        ],
    },
}

# Questions génériques si le niveau n'est pas dans le dictionnaire
DEFAULT_DIAGNOSTIC = {
    "francais": [
        {
            "id": "gen_fr_1",
            "question": "Quel est le pluriel de 'œil' ?",
            "type": "qcm",
            "options": [{"label": "A", "text": "œils"}, {"label": "B", "text": "yeux"}, {"label": "C", "text": "œilles"}],
            "correct": "B",
            "points": 1
        },
    ],
    "mathematiques": [
        {
            "id": "gen_math_1",
            "question": "Combien font 12 × 12 ?",
            "type": "qcm",
            "options": [{"label": "A", "text": "124"}, {"label": "B", "text": "144"}, {"label": "C", "text": "134"}],
            "correct": "B",
            "points": 1
        },
    ],
}

SUBJECTS_ORDER = ["francais", "mathematiques", "sciences", "anglais", "histoire-geo"]


class LearningService:
    """Service principal pour la gestion du parcours d'apprentissage."""

    # ─── DIAGNOSTIC ──────────────────────────────────────────────

    async def get_or_create_diagnostic(
        self, db: AsyncSession, user: User
    ) -> dict:
        """
        Retourne le diagnostic existant ou en crée un nouveau.
        Appelé à chaque connexion de l'élève pour vérifier s'il a déjà
        passé le diagnostic.
        """
        result = await db.execute(
            select(DiagnosticSession).where(DiagnosticSession.user_id == user.id)
        )
        session = result.scalar_one_or_none()

        if session and session.status == "completed":
            return {
                "status": "completed",
                "evaluated_level": session.evaluated_level,
                "scores": session.get_scores(),
                "needs_diagnostic": False,
            }

        if not session:
            level = user.level or "CE1"
            questions = self._get_diagnostic_questions(level)
            session = DiagnosticSession(
                user_id=user.id,
                declared_level=level,
                status="in_progress",
            )
            session.questions_asked = json.dumps(questions, ensure_ascii=False)
            db.add(session)
            await db.commit()
            await db.refresh(session)

        questions = session.get_questions()
        return {
            "status": session.status,
            "needs_diagnostic": True,
            "declared_level": session.declared_level,
            "questions": questions,
            "total_questions": len(questions),
        }

    def _get_diagnostic_questions(self, level: str) -> list:
        """Retourne les questions de diagnostic pour un niveau donné."""
        level_upper = level.upper().replace("ÈME", "EME").replace("ÈRE", "ERE")
        bank = DIAGNOSTIC_QUESTIONS.get(level_upper, DEFAULT_DIAGNOSTIC)
        questions = []
        for subject, qs in bank.items():
            for q in qs:
                questions.append({**q, "subject": subject})
        return questions

    async def submit_diagnostic_answers(
        self, db: AsyncSession, user: User, answers: list
    ) -> dict:
        """
        Traite les réponses au diagnostic.
        answers = [{"question_id": "ci_math_1", "answer": "B"}, ...]
        Calcule le score par matière et détermine le niveau évalué.
        """
        result = await db.execute(
            select(DiagnosticSession).where(DiagnosticSession.user_id == user.id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Aucun diagnostic en cours pour cet élève.")

        questions = session.get_questions()
        answers_map = {a["question_id"]: a["answer"] for a in answers}

        scores_by_subject: dict = {}
        total_points = 0
        earned_points = 0

        for q in questions:
            subj = q.get("subject", "general")
            correct = q.get("correct", "")
            pts = q.get("points", 1)
            student_ans = answers_map.get(q["id"], "")

            if subj not in scores_by_subject:
                scores_by_subject[subj] = {"earned": 0, "total": 0}

            scores_by_subject[subj]["total"] += pts
            total_points += pts

            if student_ans.strip().upper() == correct.strip().upper():
                scores_by_subject[subj]["earned"] += pts
                earned_points += pts

        # Convertir en pourcentages
        pct_by_subject = {}
        for subj, sc in scores_by_subject.items():
            pct_by_subject[subj] = round(sc["earned"] / sc["total"] * 100) if sc["total"] else 0

        # Niveau évalué (basé sur le score global)
        overall_pct = round(earned_points / total_points * 100) if total_points else 0
        declared = session.declared_level
        evaluated = self._evaluate_level(declared, overall_pct)

        session.answers_given = json.dumps(answers, ensure_ascii=False)
        session.scores_by_subject = json.dumps(pct_by_subject)
        session.evaluated_level = evaluated
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)

        await db.commit()

        # Débloquer les premières leçons pour chaque matière
        await self._unlock_initial_lessons(db, user, evaluated, pct_by_subject)

        return {
            "evaluated_level": evaluated,
            "overall_score": overall_pct,
            "scores_by_subject": pct_by_subject,
            "message": self._build_result_message(user.full_name, evaluated, overall_pct),
        }

    def _evaluate_level(self, declared: str, score_pct: int) -> str:
        """Ajuste le niveau selon le score obtenu."""
        levels = ["CI", "CP", "CE1", "CE2", "CM1", "CM2", "6EME", "5EME", "4EME", "3EME"]
        try:
            idx = levels.index(declared.upper())
        except ValueError:
            return declared

        if score_pct >= 80:
            # Très bon niveau, reste au niveau déclaré
            return declared
        elif score_pct >= 50:
            # Niveau correct, on confirme
            return declared
        else:
            # Difficultés : on revient au niveau inférieur
            idx = max(0, idx - 1)
            return levels[idx]

    def _build_result_message(self, name: str, level: str, score: int) -> str:
        first = name.split()[0] if name else "élève"
        if score >= 80:
            emoji = "🌟"
            comment = "Excellent travail !"
        elif score >= 60:
            emoji = "👍"
            comment = "Bon travail, continue !"
        elif score >= 40:
            emoji = "💪"
            comment = "Tu peux progresser !"
        else:
            emoji = "📚"
            comment = "On va travailler ensemble !"
        return f"{emoji} {first}, tu as obtenu {score}%. {comment} Ton parcours est prêt pour le niveau {level}."

    # ─── DÉBLOCAGE DES LEÇONS ────────────────────────────────────

    async def _unlock_initial_lessons(
        self, db: AsyncSession, user: User, level: str, scores: dict
    ) -> None:
        """Débloque la première leçon de chaque matière après le diagnostic."""
        result = await db.execute(
            select(Lesson).where(
                and_(
                    Lesson.level == level,
                    Lesson.order_in_subject == 1,
                    Lesson.is_active == True
                )
            )
        )
        first_lessons = result.scalars().all()

        for lesson in first_lessons:
            existing = await db.execute(
                select(StudentProgress).where(
                    and_(
                        StudentProgress.user_id == user.id,
                        StudentProgress.lesson_id == lesson.id
                    )
                )
            )
            if not existing.scalar_one_or_none():
                progress = StudentProgress(
                    user_id=user.id,
                    lesson_id=lesson.id,
                    status="not_started",
                    unlocked=True,
                )
                db.add(progress)

        await db.commit()

    async def unlock_next_lesson(
        self, db: AsyncSession, user: User, completed_lesson: Lesson
    ) -> Optional["Lesson"]:
        """
        Débloque la leçon suivante dans la même matière après qu'une leçon est complétée.
        C'est le mécanisme de progression séquentielle (style Moodle).
        """
        result = await db.execute(
            select(Lesson).where(
                and_(
                    Lesson.level == completed_lesson.level,
                    Lesson.subject == completed_lesson.subject,
                    Lesson.order_in_subject == completed_lesson.order_in_subject + 1,
                    Lesson.is_active == True
                )
            )
        )
        next_lesson = result.scalar_one_or_none()

        if next_lesson:
            existing = await db.execute(
                select(StudentProgress).where(
                    and_(
                        StudentProgress.user_id == user.id,
                        StudentProgress.lesson_id == next_lesson.id
                    )
                )
            )
            prog = existing.scalar_one_or_none()
            if prog:
                prog.unlocked = True
            else:
                prog = StudentProgress(
                    user_id=user.id,
                    lesson_id=next_lesson.id,
                    status="not_started",
                    unlocked=True,
                )
                db.add(prog)
            await db.commit()

        return next_lesson

    # ─── PROGRESSION ─────────────────────────────────────────────

    async def get_student_dashboard(self, db: AsyncSession, user: User) -> dict:
        """
        Retourne toutes les données du tableau de bord élève :
        leçons débloquées, scores, progression par matière.
        """
        result = await db.execute(
            select(StudentProgress, Lesson)
            .join(Lesson, StudentProgress.lesson_id == Lesson.id)
            .where(StudentProgress.user_id == user.id)
            .order_by(Lesson.subject, Lesson.order_in_subject)
        )
        rows = result.all()

        subjects_data: dict = {}
        for prog, lesson in rows:
            subj = lesson.subject
            if subj not in subjects_data:
                subjects_data[subj] = {
                    "subject": subj,
                    "total_lessons": 0,
                    "completed": 0,
                    "avg_score": 0,
                    "scores": [],
                    "lessons": [],
                }
            subjects_data[subj]["total_lessons"] += 1
            if prog.status == "completed":
                subjects_data[subj]["completed"] += 1
                if prog.score is not None:
                    subjects_data[subj]["scores"].append(prog.score)

            subjects_data[subj]["lessons"].append({
                **lesson.to_dict(),
                **prog.to_dict(),
            })

        for subj_data in subjects_data.values():
            scores = subj_data.pop("scores", [])
            subj_data["avg_score"] = round(sum(scores) / len(scores)) if scores else 0
            total = subj_data["total_lessons"]
            done = subj_data["completed"]
            subj_data["progress_pct"] = round(done / total * 100) if total else 0

        # Stats globales
        total_lessons = sum(s["total_lessons"] for s in subjects_data.values())
        total_completed = sum(s["completed"] for s in subjects_data.values())
        all_scores = [s["avg_score"] for s in subjects_data.values() if s["avg_score"] > 0]
        global_avg = round(sum(all_scores) / len(all_scores)) if all_scores else 0

        return {
            "student": {
                "name": user.full_name,
                "level": user.level,
                "ien": user.ien,
            },
            "global_stats": {
                "total_lessons": total_lessons,
                "completed_lessons": total_completed,
                "global_average": global_avg,
                "completion_pct": round(total_completed / total_lessons * 100) if total_lessons else 0,
            },
            "subjects": list(subjects_data.values()),
        }

    async def start_lesson(self, db: AsyncSession, user: User, lesson_id: int) -> dict:
        """Marque une leçon comme 'en cours' et retourne son contenu."""
        result = await db.execute(
            select(Lesson).where(and_(Lesson.id == lesson_id, Lesson.is_active == True))
        )
        lesson = result.scalar_one_or_none()
        if not lesson:
            raise ValueError("Leçon introuvable.")

        prog_result = await db.execute(
            select(StudentProgress).where(
                and_(StudentProgress.user_id == user.id, StudentProgress.lesson_id == lesson_id)
            )
        )
        prog = prog_result.scalar_one_or_none()
        if not prog or not prog.unlocked:
            raise ValueError("Cette leçon n'est pas encore débloquée.")

        if prog.status == "not_started":
            prog.status = "in_progress"
            prog.started_at = datetime.now(timezone.utc)
            await db.commit()

        # Récupérer les exercices
        ex_result = await db.execute(
            select(Exercise).where(
                and_(Exercise.lesson_id == lesson_id, Exercise.is_active == True)
            ).order_by(Exercise.order_in_lesson)
        )
        exercises = ex_result.scalars().all()

        return {
            "lesson": {
                **lesson.to_dict(),
                "content": lesson.content,
            },
            "exercises": [e.to_dict() for e in exercises],
            "progress": prog.to_dict(),
        }

    async def complete_lesson(
        self, db: AsyncSession, user: User, lesson_id: int, exercise_answers: list
    ) -> dict:
        """
        Corrige les exercices, attribue un score et débloque la leçon suivante.
        exercise_answers = [{"exercise_id": 1, "answer": "B"}, ...]
        """
        result = await db.execute(
            select(Lesson).where(Lesson.id == lesson_id)
        )
        lesson = result.scalar_one_or_none()
        if not lesson:
            raise ValueError("Leçon introuvable.")

        ex_result = await db.execute(
            select(Exercise).where(Exercise.lesson_id == lesson_id)
        )
        exercises = {e.id: e for e in ex_result.scalars().all()}

        total_points = 0
        earned_points = 0
        results = []

        for ans in exercise_answers:
            ex_id = ans.get("exercise_id")
            student_ans = str(ans.get("answer", "")).strip()
            exercise = exercises.get(ex_id)
            if not exercise:
                continue

            is_correct = student_ans.upper() == exercise.correct_answer.strip().upper()
            pts_earned = exercise.points if is_correct else 0
            total_points += exercise.points
            earned_points += pts_earned

            grade = Grade(
                user_id=user.id,
                exercise_id=ex_id,
                student_answer=student_ans,
                is_correct=is_correct,
                points_earned=pts_earned,
            )
            db.add(grade)

            results.append({
                "exercise_id": ex_id,
                "is_correct": is_correct,
                "correct_answer": exercise.correct_answer,
                "explanation": exercise.explanation,
                "points_earned": pts_earned,
            })

        score_pct = round(earned_points / total_points * 100) if total_points else 0
        passed = score_pct >= 50  # Seuil de réussite : 50%

        # Mettre à jour la progression
        prog_result = await db.execute(
            select(StudentProgress).where(
                and_(StudentProgress.user_id == user.id, StudentProgress.lesson_id == lesson_id)
            )
        )
        prog = prog_result.scalar_one_or_none()
        if prog:
            prog.status = "completed" if passed else "in_progress"
            prog.score = score_pct
            prog.attempts += 1
            if passed:
                prog.completed_at = datetime.now(timezone.utc)

        await db.commit()

        next_lesson = None
        if passed:
            next_lesson_obj = await self.unlock_next_lesson(db, user, lesson)
            if next_lesson_obj:
                next_lesson = next_lesson_obj.to_dict()

        return {
            "score": score_pct,
            "passed": passed,
            "earned_points": earned_points,
            "total_points": total_points,
            "results": results,
            "next_lesson": next_lesson,
            "message": self._build_lesson_message(score_pct, passed, lesson.title),
        }

    def _build_lesson_message(self, score: int, passed: bool, lesson_title: str) -> str:
        if passed:
            if score == 100:
                return f"🎉 Parfait ! Tu as eu 100% sur '{lesson_title}'. La leçon suivante est débloquée !"
            elif score >= 75:
                return f"✅ Très bien ! {score}% sur '{lesson_title}'. La leçon suivante est maintenant accessible."
            else:
                return f"👍 Réussi ! {score}% sur '{lesson_title}'. Continue ainsi !"
        else:
            return f"💪 {score}% pour '{lesson_title}'. Il te faut 50% pour continuer. Relis la leçon et réessaie !"

    # ─── AIDE TUTEUR / IA ────────────────────────────────────────

    async def create_help_request(
        self, db: AsyncSession, user: User,
        message: str, lesson_id: Optional[int] = None,
        exercise_id: Optional[int] = None, request_type: str = "ai"
    ) -> dict:
        """Crée une demande d'aide vers le tuteur ou l'IA."""
        req = TutorRequest(
            student_id=user.id,
            lesson_id=lesson_id,
            exercise_id=exercise_id,
            message=message,
            request_type=request_type,
            status="pending",
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req.to_dict()

    async def get_student_grades(self, db: AsyncSession, user: User) -> dict:
        """Retourne le carnet de notes complet de l'élève."""
        result = await db.execute(
            select(Grade, Exercise, Lesson)
            .join(Exercise, Grade.exercise_id == Exercise.id)
            .join(Lesson, Exercise.lesson_id == Lesson.id)
            .where(Grade.user_id == user.id)
            .order_by(Grade.submitted_at.desc())
        )
        rows = result.all()

        grades_by_lesson: dict = {}
        for grade, exercise, lesson in rows:
            key = f"{lesson.id}"
            if key not in grades_by_lesson:
                grades_by_lesson[key] = {
                    "lesson_id": lesson.id,
                    "lesson_title": lesson.title,
                    "subject": lesson.subject,
                    "exercises": [],
                    "total_points": 0,
                    "earned_points": 0,
                }
            grades_by_lesson[key]["exercises"].append({
                "question": exercise.question[:80] + "..." if len(exercise.question) > 80 else exercise.question,
                "is_correct": grade.is_correct,
                "points_earned": grade.points_earned,
                "total_points": exercise.points,
                "submitted_at": grade.submitted_at.isoformat(),
            })
            grades_by_lesson[key]["total_points"] += exercise.points
            grades_by_lesson[key]["earned_points"] += grade.points_earned

        for ld in grades_by_lesson.values():
            total = ld["total_points"]
            ld["score_pct"] = round(ld["earned_points"] / total * 100) if total else 0

        return {
            "grades": list(grades_by_lesson.values()),
            "total_lessons_graded": len(grades_by_lesson),
        }
