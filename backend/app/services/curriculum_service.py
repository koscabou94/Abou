"""
Service de recherche dans le Curriculum officiel sénégalais (CEB).

Charge data/curriculum_ceb.json (extrait des PDFs officiels du Ministère
de l'Éducation Nationale du Sénégal — 7 documents, 1500+ pages).

Permet :
- Répondre aux questions sur le programme officiel
  ("Quel est le programme de maths CE1 ?", "Que doit savoir un CM2 ?")
- Fournir le contexte aligné au curriculum pour la génération d'exercices
- Citer les paliers, compétences et OS officiels

Utilise une recherche TF-IDF légère (compatible Render gratuit).
"""

import json
import os
import re
import asyncio
from typing import Optional
import structlog

from app.services.planete_faq_service import (
    normalize_text,
    expand_query_with_synonyms,
)

logger = structlog.get_logger(__name__)


# Niveaux scolaires reconnus (élémentaire + collège + lycée)
NIVEAUX_VALIDES = {
    "ci", "cp", "ce1", "ce2", "cm1", "cm2",
    "prescolaire", "préscolaire",
    "6eme", "6ème", "5eme", "5ème", "4eme", "4ème", "3eme", "3ème",
    "seconde", "2nde",
    "premiere", "première", "1ere", "1ère",
    "terminale",
}

# Matieres reconnues (alias normalisés)
MATIERES_ALIAS = {
    "francais": "francais", "français": "francais",
    "lecture": "francais lecture", "ecriture": "francais ecriture",
    "écriture": "francais ecriture",
    "expression orale": "francais oral", "expression écrite": "francais ecriture",
    "production ecrite": "francais ecriture", "production écrite": "francais ecriture",
    "grammaire": "francais", "conjugaison": "francais", "orthographe": "francais",
    "vocabulaire": "francais", "redaction": "francais", "rédaction": "francais",
    "compréhension": "francais lecture", "comprehension": "francais lecture",
    "dictée": "francais", "dictee": "francais",
    "math": "mathematiques", "maths": "mathematiques",
    "mathematique": "mathematiques", "mathematiques": "mathematiques",
    "mathématique": "mathematiques", "mathématiques": "mathematiques",
    "calcul": "mathematiques", "geometrie": "mathematiques", "géométrie": "mathematiques",
    "arithmetique": "mathematiques", "arithmétique": "mathematiques",
    "algebre": "mathematiques", "algèbre": "mathematiques",
    "anglais": "anglais", "english": "anglais",
    "arabe": "arabe",
    "eps": "eps", "education physique": "eps", "éducation physique": "eps",
    "sport": "eps", "sportive": "eps",
    "arts": "arts", "musique": "arts", "art plastique": "arts",
    "histoire": "decouverte du monde", "geographie": "decouverte du monde",
    "géographie": "decouverte du monde", "histoire-géo": "decouverte du monde",
    "decouverte": "decouverte du monde", "découverte": "decouverte du monde",
    "vivre ensemble": "vivre ensemble", "civisme": "vivre ensemble",
    "education civique": "vivre ensemble", "éducation civique": "vivre ensemble",
    "ist": "decouverte du monde", "sciences": "decouverte du monde",
    "science": "decouverte du monde",
}


def detect_niveau(text: str) -> Optional[str]:
    """Detecte le niveau scolaire dans un texte (du préscolaire à Terminale)."""
    t = normalize_text(text)

    # Mappings : pattern dans le texte normalisé → forme canonique de retour
    # Ordre important : préfixes plus longs avant les courts (ex: "ce1" avant "ce")
    NIVEAU_MAPS = [
        ("ci", "CI"),
        ("cp", "CP"),
        ("ce1", "CE1"), ("ce2", "CE2"),
        ("cm1", "CM1"), ("cm2", "CM2"),
        ("prescolaire", "Préscolaire"),
        # Collège — plusieurs orthographes possibles après normalize
        ("6eme", "6ème"), ("6e", "6ème"),
        ("5eme", "5ème"), ("5e", "5ème"),
        ("4eme", "4ème"), ("4e", "4ème"),
        ("3eme", "3ème"), ("3e", "3ème"),
        # Lycée
        ("seconde", "2nde"), ("2nde", "2nde"),
        ("premiere", "1ère"), ("1ere", "1ère"),
        ("terminale", "Terminale"),
    ]
    for token, canonical in NIVEAU_MAPS:
        if re.search(rf"\b{re.escape(token)}\b", t):
            return canonical
    return None


def detect_matiere(text: str) -> Optional[str]:
    """Detecte la matiere dans un texte."""
    t = normalize_text(text)
    for alias, canon in MATIERES_ALIAS.items():
        alias_n = normalize_text(alias)
        if " " in alias_n:
            if alias_n in t:
                return canon
        else:
            if re.search(rf"\b{re.escape(alias_n)}\b", t):
                return canon
    return None


class CurriculumService:
    """Service de recherche dans le programme officiel CEB.

    Indexe data/curriculum_ceb.json et fournit :
    - search(query) : recherche libre TF-IDF
    - get_for_level_and_subject(niveau, matiere) : extraits ciblés
    - get_curriculum_context(niveau, matiere) : contexte formaté pour
      injection dans le prompt LLM (pour génération d'exercices)
    """

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._vectorizer = None
        self._tfidf_matrix = None
        self._loaded = False
        self._lock = asyncio.Lock()
        logger.info("CurriculumService initialisé")

    @property
    def is_available(self) -> bool:
        return self._loaded and len(self._entries) > 0

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _resolve_path(self) -> Optional[str]:
        candidates = [
            "/data/curriculum_ceb.json",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "..", "data", "curriculum_ceb.json"
            ),
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "curriculum_ceb.json"
            ),
        ]
        for p in candidates:
            p_abs = os.path.abspath(p)
            if os.path.exists(p_abs):
                return p_abs
        return None

    async def initialize(self) -> bool:
        async with self._lock:
            if self._loaded:
                return True
            try:
                path = self._resolve_path()
                if not path:
                    logger.warning("curriculum_ceb.json introuvable")
                    return False
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entries = data.get("entries", [])

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._fit_tfidf)

                self._loaded = True
                logger.info(
                    "Curriculum CEB chargé",
                    entries=len(self._entries),
                    path=path,
                )
                return True
            except Exception as exc:
                logger.error("Erreur chargement curriculum CEB", error=str(exc))
                return False

    def _fit_tfidf(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        if not self._entries:
            return
        # Indexer : title + keywords + content (normalisé + synonymes)
        texts = []
        for e in self._entries:
            base = (
                f"{e.get('title','')} "
                f"{e.get('keywords','')} "
                f"{e.get('domaine','')} "
                f"{e.get('sous_domaine','')} "
                f"{e.get('matiere','')} "
                f"{e.get('niveau','')} "
                f"{e.get('content','')}"
            )
            texts.append(expand_query_with_synonyms(normalize_text(base)))
        self._vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(texts)
        logger.info("TF-IDF curriculum prêt", shape=self._tfidf_matrix.shape)

    # ---------------------------------------------------------
    # API PUBLIQUE
    # ---------------------------------------------------------

    async def search(
        self,
        query: str,
        niveau: Optional[str] = None,
        matiere: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.10,
    ) -> list[dict]:
        """Recherche dans le curriculum.

        Args:
            query: requête utilisateur
            niveau: filtre par niveau (CI, CP, CE1...) — optionnel
            matiere: filtre par matière (mathematiques, anglais...) — optionnel
            limit: nombre maximum de résultats
            threshold: score TF-IDF minimal
        """
        if not self.is_available or not query.strip():
            return []
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            q_expanded = expand_query_with_synonyms(query)
            q_vec = self._vectorizer.transform([q_expanded])
            scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()

            sorted_idx = np.argsort(scores)[::-1]
            results = []
            for idx in sorted_idx:
                if len(results) >= limit:
                    break
                score = float(scores[idx])
                if score < threshold:
                    break
                e = self._entries[idx]
                # Filtres
                if niveau:
                    if niveau.lower() not in (e.get("niveau") or "").lower():
                        continue
                if matiere:
                    e_matiere = (e.get("matiere") or "").lower()
                    e_dom = (e.get("domaine") or "").lower()
                    if matiere.lower() not in e_matiere and matiere.lower() not in e_dom:
                        continue
                results.append({**e, "score": score})
            return results
        except Exception as exc:
            logger.error("Erreur recherche curriculum", error=str(exc))
            return []

    async def get_for_level_and_subject(
        self,
        niveau: str,
        matiere: Optional[str] = None,
        limit: int = 4,
    ) -> list[dict]:
        """Renvoie les extraits du curriculum pour un niveau (et matière) donnés.

        Utilisé pour aligner la génération d'exercices sur le programme officiel.
        """
        if not self.is_available:
            return []
        niveau_l = niveau.lower()
        results = []
        for e in self._entries:
            e_niv = (e.get("niveau") or "").lower()
            if niveau_l not in e_niv:
                continue
            if matiere:
                e_mat = (e.get("matiere") or "").lower()
                e_dom = (e.get("domaine") or "").lower()
                if matiere.lower() not in e_mat and matiere.lower() not in e_dom:
                    continue
            results.append(e)
            if len(results) >= limit:
                break
        return results

    def get_curriculum_context(
        self,
        entries: list[dict],
        max_chars: int = 1500,
    ) -> str:
        """Formate des extraits du curriculum pour injection dans le prompt LLM.

        Retourne un texte compact qui peut être ajouté au SYSTEM_PROMPT
        ou au message utilisateur pour que la génération d'exercices respecte
        les objectifs officiels du programme sénégalais.
        """
        if not entries:
            return ""
        parts = ["[Programme officiel CEB - extraits pertinents]"]
        used = 0
        for e in entries:
            title = e.get("title", "").strip()
            content = e.get("content", "").strip()
            if not content:
                continue
            # Tronquer chaque extrait à ~400 caractères pour économiser
            if len(content) > 400:
                cut = content[:400]
                last = max(cut.rfind("."), cut.rfind("\n"))
                content = cut[:last + 1] if last > 100 else cut + "..."
            block = f"\n• {title}\n  {content}"
            if used + len(block) > max_chars:
                break
            parts.append(block)
            used += len(block)
        if len(parts) == 1:
            return ""
        parts.append(
            "\n[Fin extraits programme officiel — base tes exercices sur ces objectifs]"
        )
        return "\n".join(parts)

    async def get_categories(self) -> list[dict]:
        """Liste les catégories disponibles (pour debug/admin)."""
        if not self.is_available:
            return []
        from collections import Counter
        cats = Counter()
        for e in self._entries:
            key = (
                e.get("etape", "?"),
                e.get("niveau", "?"),
                e.get("matiere", "?") or "—",
            )
            cats[key] += 1
        return [
            {"etape": e, "niveau": n, "matiere": m, "count": c}
            for (e, n, m), c in sorted(cats.items())
        ]
