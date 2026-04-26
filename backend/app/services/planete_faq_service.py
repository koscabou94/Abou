"""
Service FAQ dédié à PLANETE (FAQ_PLANETE3.json).

Charge le fichier FAQ_PLANETE3.json (structure imbriquée par catégories),
aplatit les Q&R, et fournit une recherche tres tolérante :
- Normalisation (accents, casse, ponctuation, mots vides)
- Expansion automatique de synonymes (ex: "se connecter" / "me connecter" / "login")
- TF-IDF avec n-grammes étendus et keywords enrichis
- Fuzzy matching (rapidfuzz) pour les fautes de frappe
- Boost par mots-clés métier PLANETE

Ce service est branché EN TÊTE du pipeline de recherche dès qu'une question
est détectée comme PLANETE (explicitement ou implicitement). S'il trouve une
réponse satisfaisante, le pipeline s'arrête là — on n'interroge ni faq_senegal,
ni la KB, ni le LLM.
"""

import json
import os
import re
import unicodedata
import asyncio
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


# ============================================================
# LEXIQUE PLANETE
# ============================================================
# Mots-clés métier qui indiquent une question PLANETE — même si le mot
# "PLANETE" lui-même n'est pas prononcé. Servent à la fois à la détection
# d'intention et au boost de score lors de la recherche.
PLANETE_LEXICON = {
    # Vocabulaire système
    "planete", "planète", "planete3", "planète3", "simen", "mirador",
    # URL / connexion
    "education.sn", "@education.sn", "planete3.education.sn",
    # Concepts généraux
    "tableau de bord", "dashboard", "fiche établissement", "fiche etablissement",
    "polarisation", "bst", "polarisateur",
    # Configuration
    "configuration", "configurer", "environnement physique", "environnement pédagogique",
    "bâtiment", "batiment", "bâtiments", "batiments",
    "salle", "salles", "salle de classe",
    "classe pédagogique", "classe pedagogique", "groupage", "groupage de classes",
    "programme", "discipline", "second semestre", "semestre",
    "frais de scolarité", "frais de scolarite", "scolarité", "scolarite",
    "compte bancaire", "rib", "code banque",
    # Personnel
    "personnel", "agent", "complément horaire", "complement horaire",
    "pointage", "prise de service", "archiver", "archivage", "ien",
    # Élèves
    "inscrire", "inscription", "élève", "eleve", "élèves", "eleves",
    "affecter", "affectation", "transfert", "transfert entrant", "transfert sortant",
    "import élèves", "import eleves", "reprise scolarité", "reprise scolarite",
    "bfem", "bst", "candidat bfem",
    # Emploi du temps
    "emploi du temps", "emplois du temps", "edt", "génération automatique edt",
    "generer edt", "générer edt", "export edt", "export cours",
    # Cours
    "cahier de texte", "cahier texte", "cahier", "absence", "retard",
    "justifier absence", "absence justifiée",
    # Rapport journalier
    "rapport de fin de journée", "rapport journalier", "déclarer un incident",
    "incident",
    # Évaluations
    "évaluation", "evaluation", "notation", "saisir les notes", "verrouiller",
    "verrouillage",
    # Conseils
    "conseil de classe", "conseils de classe", "conseil classe", "appréciation",
    "appreciation", "valider conseil",
    # Utilisateurs
    "utilisateur", "utilisateurs",
    "ajouter utilisateur", "profil utilisateur", "rechercher utilisateur",
    "chef d'établissement", "chef etablissement", "ief", "ia",
}

# Synonymes / reformulations courantes — étendent la requête utilisateur
# Côté GAUCHE = forme rencontrée. Côté DROIT = formes équivalentes ajoutées
# au moment de la recherche.
SYNONYMS = {
    # Formules d'interrogation
    "comment puis-je": ["comment", "comment faire pour", "comment dois-je"],
    "comment dois-je": ["comment", "comment faire pour", "comment puis-je"],
    "comment devrais-je": ["comment", "comment faire pour", "comment puis-je"],
    "comment faire pour": ["comment", "comment puis-je", "comment dois-je"],
    "que faire pour": ["comment", "comment faire", "comment dois-je"],
    "comment je peux": ["comment", "comment puis-je"],
    "c'est quoi": ["qu'est-ce que", "définition", "qu'est ce que"],
    "qu'est-ce que": ["c'est quoi", "définition"],
    "à quoi sert": ["c'est quoi", "qu'est-ce que", "utilité"],
    # Verbes équivalents
    "se connecter": ["connexion", "me connecter", "se loguer", "login", "accéder"],
    "me connecter": ["se connecter", "connexion", "login", "accéder"],
    "se loguer": ["se connecter", "connexion", "login"],
    "accéder": ["se connecter", "ouvrir", "entrer"],
    "ouvrir": ["accéder", "lancer", "démarrer"],
    "configurer": ["paramétrer", "régler", "mettre en place", "définir"],
    "paramétrer": ["configurer", "régler", "définir"],
    "créer": ["ajouter", "déclarer", "enregistrer", "saisir"],
    "ajouter": ["créer", "enregistrer", "déclarer"],
    "supprimer": ["effacer", "retirer", "enlever", "supprimer définitivement"],
    "modifier": ["changer", "mettre à jour", "éditer", "corriger"],
    "mettre à jour": ["modifier", "actualiser", "changer", "éditer"],
    "réinitialiser": ["reset", "remettre à zéro", "récupérer"],
    "oublié": ["perdu", "ne sais plus", "récupérer"],
    # Substantifs équivalents
    "mot de passe": ["password", "code", "mdp"],
    "adresse e-mail": ["email", "courriel", "adresse mail", "mail"],
    "e-mail": ["email", "mail", "courriel"],
    "tableau de bord": ["dashboard", "accueil", "page d'accueil"],
    "dashboard": ["tableau de bord", "accueil"],
    "élève": ["étudiant", "apprenant"],
    "élèves": ["étudiants", "apprenants"],
    "professeur": ["enseignant", "prof"],
    "enseignant": ["professeur", "prof", "maître"],
    "établissement": ["école", "lycée", "collège"],
    "salle": ["classe", "local"],
    "bâtiment": ["bloc", "édifice"],
    "transfert": ["mutation", "déplacement"],
    "absence": ["non-présence", "absentéisme"],
    "évaluation": ["devoir", "contrôle", "test", "examen", "composition"],
    "notation": ["saisie des notes", "noter", "saisir les notes"],
    "conseil de classe": ["réunion pédagogique", "conseil pédagogique"],
    "emploi du temps": ["edt", "planning des cours", "horaires", "planning"],
    "edt": ["emploi du temps", "planning"],
    # Variations PLANETE
    "planete 3": ["planete3", "planete v3", "planete trois"],
    "planete3": ["planete 3", "planete v3"],
}


# Mots vides FR à ignorer dans la normalisation pour TF-IDF
FR_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d'", "l'",
    "ce", "cet", "cette", "ces", "ça", "ca",
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
    "notre", "votre", "leur", "leurs",
    "et", "ou", "où", "ni", "mais", "donc", "or", "car",
    "à", "a", "au", "aux", "en", "dans", "sur", "sous", "par", "pour",
    "avec", "sans", "vers", "chez", "entre", "depuis", "pendant",
    "qui", "que", "quoi", "dont", "lequel", "laquelle",
    "est", "sont", "était", "etait", "ont", "ai", "as", "a", "avons", "avez",
    "y", "n'", "ne", "pas", "plus", "moins",
    "si", "comme", "alors", "puis", "ensuite",
    # On retire volontairement les mots-clés métier ("comment", "quand"...)
}


def normalize_text(text: str) -> str:
    """Normalise un texte pour la recherche : minuscules, sans accents,
    sans ponctuation, espaces normalisés."""
    if not text:
        return ""
    text = text.lower().strip()
    # Décomposer accents puis filtrer les diacritiques
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Remplacer ponctuation par espaces
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    # Espaces multiples → simple
    text = re.sub(r"\s+", " ", text).strip()
    return text


def expand_query_with_synonyms(query: str) -> str:
    """Étend la requête en ajoutant les synonymes connus. Retourne une
    chaîne enrichie (la requête originale + tous les synonymes pertinents
    concaténés) pour le TF-IDF."""
    q_norm = normalize_text(query)
    expansions = [q_norm]
    for trigger, syns in SYNONYMS.items():
        trigger_norm = normalize_text(trigger)
        if trigger_norm in q_norm:
            for s in syns:
                expansions.append(normalize_text(s))
    return " ".join(expansions)


def is_planete_question(text: str) -> tuple[bool, int]:
    """Détecte si une question concerne PLANETE, même implicitement.

    Retourne (is_planete, score) où score est le nombre de mots-clés
    PLANETE détectés. Plus le score est élevé, plus la confiance est forte.
    """
    if not text:
        return (False, 0)
    text_norm = normalize_text(text)
    hits = 0
    matched = []
    for kw in PLANETE_LEXICON:
        kw_norm = normalize_text(kw)
        if not kw_norm:
            continue
        # Mot-clé multi-mots → recherche substring
        if " " in kw_norm:
            if kw_norm in text_norm:
                hits += 1
                matched.append(kw_norm)
        else:
            # Mot simple → match par limites de mots
            if re.search(rf"\b{re.escape(kw_norm)}\b", text_norm):
                hits += 1
                matched.append(kw_norm)
    is_planete = hits >= 1
    return (is_planete, hits)


# ============================================================
# SERVICE
# ============================================================

class PlaneteFAQService:
    """
    Service de FAQ spécialisé PLANETE.

    Charge FAQ_PLANETE3.json au démarrage, aplatit les questions, prépare
    un index TF-IDF enrichi (synonymes + keywords métier) et expose une
    méthode find_best_match() qui combine TF-IDF + boost lexique + fuzzy.
    """

    def __init__(self) -> None:
        self._items: list[dict] = []        # Q&R aplaties
        self._search_corpus: list[str] = []  # Textes normalisés indexés
        self._vectorizer = None
        self._tfidf_matrix = None
        self._loaded = False
        self._lock = asyncio.Lock()
        logger.info("PlaneteFAQService initialisé")

    @property
    def is_available(self) -> bool:
        return self._loaded and len(self._items) > 0

    @property
    def question_count(self) -> int:
        return len(self._items)

    # ---------------------------------------------------------
    # CHARGEMENT
    # ---------------------------------------------------------

    def _resolve_path(self) -> Optional[str]:
        """Résout le chemin du fichier FAQ_PLANETE3.json en testant
        plusieurs emplacements possibles selon l'environnement."""
        candidates = [
            "/data/FAQ_PLANETE3.json",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "..", "data", "FAQ_PLANETE3.json"
            ),
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "FAQ_PLANETE3.json"
            ),
        ]
        for p in candidates:
            p_abs = os.path.abspath(p)
            if os.path.exists(p_abs):
                return p_abs
        return None

    @staticmethod
    def _format_answer(item: dict) -> str:
        """Construit la réponse complète à partir d'une entrée FAQ_PLANETE3.

        Combine `reponse` + listes structurées (etapes, details, causes,
        types, etc.) + note/info finale. Format markdown simple, sans gras."""
        parts: list[str] = []

        # Réponse principale
        rep = (item.get("reponse") or "").strip()
        if rep:
            parts.append(rep)

        # Champs liste possibles dans FAQ_PLANETE3.json
        list_fields = [
            ("etapes", "Étapes à suivre"),
            ("details", "Détails"),
            ("causes", "Causes possibles"),
            ("fonctions", "Fonctions principales"),
            ("acteurs", "Acteurs concernés"),
            ("informations_visibles", "Informations visibles"),
            ("elements_a_configurer", "Éléments à configurer"),
            ("contenu_dossier", "Contenu du dossier"),
            ("options_export", "Options d'export"),
            ("exemples", "Exemples"),
        ]
        for key, label in list_fields:
            arr = item.get(key)
            if isinstance(arr, list) and arr:
                parts.append(f"\n### {label}\n")
                for elem in arr:
                    if isinstance(elem, str):
                        parts.append(f"- {elem}")
                    elif isinstance(elem, dict):
                        # Formats type "types" / "versions" / "profils_disponibles"
                        title = (
                            elem.get("type")
                            or elem.get("nom")
                            or elem.get("profil")
                            or ""
                        )
                        desc = (
                            elem.get("description")
                            or elem.get("periode")
                            or ""
                        )
                        if title and desc:
                            parts.append(f"- {title} : {desc}")
                        elif title:
                            parts.append(f"- {title}")
                        elif desc:
                            parts.append(f"- {desc}")

        # Champs spéciaux (versions, types, profils_disponibles, format_email, url)
        for key, label in [
            ("versions", "Versions"),
            ("types", "Types disponibles"),
            ("profils_disponibles", "Profils disponibles"),
        ]:
            arr = item.get(key)
            if isinstance(arr, list) and arr and key not in [k for k, _ in list_fields]:
                parts.append(f"\n### {label}\n")
                for elem in arr:
                    if isinstance(elem, dict):
                        title = elem.get("type") or elem.get("nom") or elem.get("profil") or ""
                        desc = elem.get("description") or elem.get("periode") or ""
                        if title and desc:
                            parts.append(f"- {title} : {desc}")

        # Champs simples
        if item.get("url"):
            parts.append(f"\nURL : {item['url']}")
        if item.get("format_email"):
            parts.append(f"\nFormat de l'e-mail : {item['format_email']}")

        # Note / info de bas de réponse
        for key, prefix in [("note", "Note"), ("info", "À savoir")]:
            val = item.get(key)
            if val:
                parts.append(f"\n{prefix} : {val}")

        return "\n".join(p for p in parts if p).strip()

    @staticmethod
    def _build_search_text(item: dict, category_title: str) -> str:
        """Construit le texte indexé pour TF-IDF : question + variantes
        + keywords métier extraits + titre catégorie + extrait réponse."""
        parts = [
            item.get("question", ""),
            category_title or "",
        ]

        # Extraire les mots-clés métier de la réponse pour enrichir l'index
        rep = (item.get("reponse") or "")[:300]
        parts.append(rep)

        # Détails / étapes premiers éléments aussi indexés (pour matcher
        # des questions du type "comment faire X" où X est dans les étapes)
        for key in ("etapes", "details", "elements_a_configurer"):
            arr = item.get(key)
            if isinstance(arr, list):
                # Garder seulement les 3 premiers éléments pour ne pas
                # surcharger l'index avec du contenu trop spécifique
                for elem in arr[:3]:
                    if isinstance(elem, str):
                        parts.append(elem)

        # Joindre + normaliser + expansion synonymes
        raw = " ".join(p for p in parts if p)
        norm = normalize_text(raw)
        expanded = expand_query_with_synonyms(norm)
        return expanded

    async def initialize(self) -> bool:
        """Charge FAQ_PLANETE3.json et construit l'index TF-IDF."""
        async with self._lock:
            if self._loaded:
                return True
            try:
                path = self._resolve_path()
                if not path:
                    logger.warning("FAQ_PLANETE3.json introuvable")
                    return False

                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                items: list[dict] = []
                corpus: list[str] = []

                for cat in data.get("categories", []):
                    cat_id = cat.get("id")
                    cat_title = cat.get("titre", "")
                    for q in cat.get("questions", []):
                        # Construire l'entrée indexée
                        question_text = q.get("question", "").strip()
                        if not question_text:
                            continue
                        answer = self._format_answer(q)
                        if not answer:
                            continue
                        search_text = self._build_search_text(q, cat_title)

                        items.append({
                            "id": q.get("id"),
                            "category_id": cat_id,
                            "category_title": cat_title,
                            "question": question_text,
                            "answer": answer,
                            "raw": q,  # Conservé pour debug
                        })
                        corpus.append(search_text)

                self._items = items
                self._search_corpus = corpus

                # Construire l'index TF-IDF en thread (non bloquant)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._fit_tfidf)

                self._loaded = True
                logger.info(
                    "FAQ PLANETE 3 chargée",
                    questions=len(self._items),
                    categories=len(data.get("categories", [])),
                    path=path,
                )
                return True

            except Exception as exc:
                logger.error("Erreur chargement FAQ_PLANETE3.json", error=str(exc))
                return False

    def _fit_tfidf(self) -> None:
        """Construit l'index TF-IDF avec n-grammes (1-3) sur le corpus normalisé."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        if not self._search_corpus:
            return
        self._vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 3),     # n-grammes 1 à 3 mots → robuste aux reformulations
            min_df=1,
            sublinear_tf=True,
            stop_words=list(FR_STOPWORDS),
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(self._search_corpus)
        logger.info("Index TF-IDF PLANETE construit", shape=self._tfidf_matrix.shape)

    # ---------------------------------------------------------
    # RECHERCHE
    # ---------------------------------------------------------

    async def find_best_match(
        self,
        query: str,
        threshold: float = 0.20,
        high_confidence: float = 0.45,
    ) -> Optional[dict]:
        """Cherche la meilleure réponse PLANETE pour une requête.

        Combine 3 signaux :
        1. TF-IDF sur corpus enrichi (questions + keywords + synonymes)
        2. Boost mots-clés métier PLANETE en commun
        3. Fuzzy matching de la question (rapidfuzz si dispo, fallback simple)

        Args:
            query: requête utilisateur (peut contenir des fautes/variations)
            threshold: score minimum pour retourner un résultat
            high_confidence: score au-dessus duquel le match est considéré certain

        Returns:
            dict avec {id, question, answer, category, score, confidence} ou None
        """
        if not self.is_available or not query.strip():
            return None

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            # 1. Préparer la requête : normaliser + expansion synonymes
            q_expanded = expand_query_with_synonyms(query)

            # 2. TF-IDF cosinus
            q_vec = self._vectorizer.transform([q_expanded])
            tfidf_scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()

            # 3. Boost mots-clés PLANETE en commun (signal lexique)
            q_norm = normalize_text(query)
            q_planete_kws = self._extract_planete_keywords(q_norm)
            boosts = np.zeros(len(self._items), dtype=float)
            if q_planete_kws:
                for i, item in enumerate(self._items):
                    item_norm = normalize_text(
                        item["question"] + " " + item["answer"][:300]
                    )
                    item_kws = self._extract_planete_keywords(item_norm)
                    common = q_planete_kws & item_kws
                    if common:
                        # Bonus proportionnel : +0.05 par mot-clé partagé, plafonné à +0.25
                        boosts[i] = min(0.05 * len(common), 0.25)

            # 4. Fuzzy matching question vs requête (rattrape les fautes)
            fuzzy_scores = self._compute_fuzzy_scores(query)

            # 5. Combinaison pondérée :
            #    - 60 % TF-IDF
            #    - 25 % fuzzy sur la question
            #    - 15 % boost lexique
            combined = (
                0.60 * tfidf_scores
                + 0.25 * fuzzy_scores
                + 0.15 * boosts
            )

            best_idx = int(np.argmax(combined))
            best_score = float(combined[best_idx])

            if best_score < threshold:
                logger.debug(
                    "Pas de match PLANETE FAQ",
                    score=round(best_score, 3),
                    threshold=threshold,
                    query=query[:60],
                )
                return None

            item = self._items[best_idx]
            confidence = "high" if best_score >= high_confidence else "medium"
            logger.info(
                "Match PLANETE FAQ trouvé",
                score=round(best_score, 3),
                tfidf=round(float(tfidf_scores[best_idx]), 3),
                fuzzy=round(float(fuzzy_scores[best_idx]), 3),
                boost=round(float(boosts[best_idx]), 3),
                question=item["question"][:80],
                confidence=confidence,
            )
            return {
                "id": item["id"],
                "question": item["question"],
                "answer": item["answer"],
                "category": item["category_title"],
                "category_id": item["category_id"],
                "score": best_score,
                "confidence": confidence,
            }
        except Exception as exc:
            logger.error("Erreur recherche PLANETE FAQ", error=str(exc), exc_info=True)
            return None

    @staticmethod
    def _extract_planete_keywords(text_norm: str) -> set[str]:
        """Retourne l'ensemble des mots-clés PLANETE présents dans un
        texte déjà normalisé."""
        found = set()
        for kw in PLANETE_LEXICON:
            kw_norm = normalize_text(kw)
            if not kw_norm:
                continue
            if " " in kw_norm:
                if kw_norm in text_norm:
                    found.add(kw_norm)
            else:
                if re.search(rf"\b{re.escape(kw_norm)}\b", text_norm):
                    found.add(kw_norm)
        return found

    def _compute_fuzzy_scores(self, query: str):
        """Calcule un score fuzzy [0..1] entre la requête et chaque
        question. Utilise rapidfuzz si disponible, sinon fallback Python."""
        import numpy as np
        q_norm = normalize_text(query)
        scores = np.zeros(len(self._items), dtype=float)

        try:
            from rapidfuzz import fuzz
            for i, item in enumerate(self._items):
                qn = normalize_text(item["question"])
                # token_set_ratio : insensible à l'ordre, robuste aux mots en plus
                scores[i] = fuzz.token_set_ratio(q_norm, qn) / 100.0
        except ImportError:
            # Fallback : ratio de mots en commun
            q_words = set(q_norm.split())
            for i, item in enumerate(self._items):
                w = set(normalize_text(item["question"]).split())
                if not q_words or not w:
                    continue
                inter = len(q_words & w)
                union = len(q_words | w)
                scores[i] = inter / union if union else 0.0

        return scores

    # ---------------------------------------------------------
    # UTILITAIRES (intro, suggestions, debug)
    # ---------------------------------------------------------

    async def get_categories(self) -> list[dict]:
        """Retourne la liste des catégories PLANETE et le nombre de questions
        dans chacune."""
        if not self.is_available:
            return []
        cats: dict[int, dict] = {}
        for item in self._items:
            cid = item.get("category_id")
            if cid not in cats:
                cats[cid] = {
                    "id": cid,
                    "title": item.get("category_title", ""),
                    "count": 0,
                }
            cats[cid]["count"] += 1
        return sorted(cats.values(), key=lambda c: c["id"] or 0)

    async def search_top_n(self, query: str, n: int = 5) -> list[dict]:
        """Retourne les N meilleures correspondances (utile pour le mode
        suggestions ou les FAQ similaires)."""
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
            for idx in sorted_idx[:n]:
                if scores[idx] < 0.10:
                    break
                item = self._items[idx]
                results.append({
                    "id": item["id"],
                    "question": item["question"],
                    "category": item["category_title"],
                    "score": float(scores[idx]),
                })
            return results
        except Exception as exc:
            logger.error("Erreur top-N PLANETE", error=str(exc))
            return []
