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
# Pour limiter les faux positifs ("exercices pour mes élèves CM2" ne doit
# PAS être détecté comme PLANETE), on sépare en deux ensembles :
#
#  - STRONG : termes spécifiques et non-ambigus (multi-mots ou techniques).
#    Un seul match = question PLANETE.
#  - WEAK : mots communs qui peuvent apparaître dans d'autres contextes
#    (élève, personnel, absence, classe…). Il en faut au moins 2 pour
#    déclencher la détection PLANETE.

# Termes forts : un seul match → PLANETE garanti
PLANETE_STRONG_LEXICON = {
    # Vocabulaire système
    "planete", "planète", "planete3", "planète3", "simen", "mirador",
    # URL / connexion
    "education.sn", "@education.sn", "planete3.education.sn",
    # Concepts métier multi-mots (tres specifiques à PLANETE)
    "tableau de bord", "fiche établissement", "fiche etablissement",
    "polarisation bst", "bst polarisateur",
    "environnement physique", "environnement pédagogique", "environnement pedagogique",
    "classe pédagogique", "classe pedagogique",
    "groupage de classes", "second semestre",
    "frais de scolarité", "frais de scolarite",
    "compte bancaire", "code banque",
    "complément horaire", "complement horaire",
    "prise de service", "mise à jour personnel", "mise a jour personnel",
    "import élèves", "import eleves", "import personnel",
    "transfert entrant", "transfert sortant",
    "reprise scolarité", "reprise scolarite",
    "candidat bfem", "élève bst", "eleve bst",
    "emploi du temps", "emplois du temps",
    "génération automatique edt", "generation automatique edt",
    "generer edt", "générer edt", "export edt", "export cours",
    "cahier de texte", "cahier texte",
    "justifier absence", "absence justifiée", "absence justifiee",
    "rapport de fin de journée", "rapport de fin de journee",
    "rapport journalier", "déclarer un incident", "declarer un incident",
    "saisir les notes", "saisir les absences",
    "justifier une absence", "justifier les absences",
    "verrouiller évaluation", "verrouiller evaluation",
    "conseil de classe", "conseils de classe", "conseil classe",
    "valider conseil", "validation conseil",
    "ajouter utilisateur", "profil utilisateur", "rechercher utilisateur",
    "chef d'établissement", "chef etablissement",
    # Termes techniques courts mais non-ambigus
    "bfem", "bst", "edt", "ien", "ief",
    "polarisation", "polarisateur",
    # Bâtiments dans le contexte PLANETE (peu d'autres contextes éducatifs
    # parlent de "bâtiments" dans une question type)
    "bâtiment", "batiment", "bâtiments", "batiments",
}

# Termes faibles : très communs, ambigus. Il en faut 2+ pour déclencher PLANETE
PLANETE_WEAK_LEXICON = {
    "configuration", "configurer", "paramétrer", "parametrer",
    "salle", "salles", "salle de classe",
    "groupage", "programme", "discipline", "semestre",
    "scolarité", "scolarite",
    "personnel", "agent", "pointage", "archiver", "archivage",
    "inscrire", "inscription", "élève", "eleve", "élèves", "eleves",
    "affecter", "affectation", "transfert",
    "absence", "retard",
    "incident",
    "évaluation", "evaluation", "notation", "verrouiller", "verrouillage",
    "appréciation", "appreciation",
    "utilisateur", "utilisateurs", "profil",
    "ia",
}

# Lexique unifié pour le boost de score (utilisé dans find_best_match)
PLANETE_LEXICON = PLANETE_STRONG_LEXICON | PLANETE_WEAK_LEXICON


# ============================================================
# CONCEPTS PLANETE (objets concrets manipulés)
# ============================================================
# Quand l'utilisateur mentionne un de ces concepts ET qu'il apparaît
# aussi dans la QUESTION d'un candidat (pas juste dans son contenu),
# on donne un GROS bonus à ce candidat. Évite que "configurer un batiment"
# tombe sur Q18 ("environnement physique") qui mentionne "bâtiments" parmi
# les éléments à configurer mais n'est PAS la bonne réponse.
#
# Format : { concept_canonical: [variantes possibles dans le texte] }
PLANETE_CONCEPTS = {
    "batiment":        ["batiment", "batiments", "bloc", "edifice"],
    "salle":           ["salle", "salles"],
    "classe":          ["classe pedagogique", "classes pedagogiques",
                        "classe", "classes"],
    "groupage":        ["groupage", "groupages"],
    "compte_bancaire": ["compte bancaire"],
    "frais_scolarite": ["frais de scolarite", "scolarite"],
    "personnel":       ["personnel", "agent", "agents"],
    "complement":      ["complement horaire"],
    "pointage":        ["pointage"],
    "eleve":           ["eleve", "eleves"],
    "inscription":     ["inscription", "inscrire"],
    "affectation":     ["affectation", "affecter"],
    "transfert_in":    ["transfert entrant"],
    "transfert_out":   ["transfert sortant"],
    "reprise":         ["reprise scolarite", "reprise"],
    "bfem":            ["bfem", "candidat bfem"],
    "bst":             ["bst", "eleve bst"],
    "edt":             ["emploi du temps", "emplois du temps", "edt"],
    "cahier":          ["cahier de texte", "cahier texte"],
    "absence":         ["absence", "absences"],
    "rapport":         ["rapport de fin de journee", "rapport journalier"],
    "incident":        ["incident", "incidents"],
    "evaluation":      ["evaluation", "evaluations"],
    "conseil":         ["conseil de classe", "conseils de classe"],
    "utilisateur":     ["utilisateur", "utilisateurs"],
    "url":             ["url", "adresse"],
    "mot_de_passe":    ["mot de passe", "password", "mdp"],
    "connexion":       ["connexion", "se connecter", "me connecter"],
    "tableau_bord":    ["tableau de bord", "dashboard"],
    "etablissement":   ["fiche etablissement"],  # specifique
    "polarisation":    ["polarisation", "polarisateur"],
    "environnement":   ["environnement physique", "environnement pedagogique"],
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
    # IMPORTANT : "configurer" et "créer" sont quasi-synonymes pour les
    # utilisateurs. "configurer un bâtiment" = "créer un bâtiment".
    "configurer": ["paramétrer", "régler", "mettre en place", "définir",
                    "créer", "ajouter", "déclarer", "enregistrer"],
    "paramétrer": ["configurer", "régler", "définir", "créer", "ajouter"],
    "créer": ["ajouter", "déclarer", "enregistrer", "saisir",
              "configurer", "paramétrer", "mettre en place"],
    "ajouter": ["créer", "enregistrer", "déclarer", "configurer", "paramétrer"],
    "déclarer": ["créer", "ajouter", "enregistrer"],
    "enregistrer": ["créer", "ajouter", "déclarer", "saisir"],
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


def _count_lexicon_hits(text_norm: str, lexicon: set) -> int:
    """Compte combien de termes du lexique apparaissent dans le texte normalisé."""
    hits = 0
    for kw in lexicon:
        kw_norm = normalize_text(kw)
        if not kw_norm:
            continue
        if " " in kw_norm:
            if kw_norm in text_norm:
                hits += 1
        else:
            if re.search(rf"\b{re.escape(kw_norm)}\b", text_norm):
                hits += 1
    return hits


def is_planete_question(text: str) -> tuple[bool, int]:
    """Détecte si une question concerne PLANETE, même implicitement.

    Règle :
      - 1+ terme STRONG (multi-mots spécifique ou technique)  → PLANETE
      - 2+ termes WEAK (mots communs comme "élève", "personnel") → PLANETE
      - 1 terme WEAK seul                                       → PAS PLANETE
        (ex : "exercices pour mes élèves" → "élève" seul ne suffit pas)

    Retourne (is_planete, total_hits).
    """
    if not text:
        return (False, 0)
    text_norm = normalize_text(text)
    strong_hits = _count_lexicon_hits(text_norm, PLANETE_STRONG_LEXICON)
    weak_hits = _count_lexicon_hits(text_norm, PLANETE_WEAK_LEXICON)
    total = strong_hits + weak_hits
    is_planete = (strong_hits >= 1) or (weak_hits >= 2)
    return (is_planete, total)


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

    # Questions où l'on DOIT garder "PLANETE 3" (distinction entre versions)
    _PRESERVE_PLANETE3_IDS = {3, 4}

    @staticmethod
    def _normalize_planete_terminology(text: str, question_id: int) -> str:
        """Pour les enseignants, PLANETE = PLANETE 3 (c'est la version
        actuelle). Le bot doit dire "PLANETE" partout, sauf dans les
        questions qui parlent explicitement des versions/différences.

        Cette fonction remplace "PLANETE 3" / "PLANETE V3" par "PLANETE",
        en préservant l'URL planete3.education.sn (qui n'a pas d'espace).
        """
        if question_id in PlaneteFAQService._PRESERVE_PLANETE3_IDS:
            return text

        # Remplacer "PLANETE 3" / "PLANETE V3" / "PLANETE  3" (avec espace)
        # \s+ = au moins un espace, donc planete3.education.sn (URL sans
        # espace) n'est PAS touché — preserve l'URL.
        text = re.sub(r"\bPLANETE\s+(?:V\s*)?3\b", "PLANETE", text)
        text = re.sub(r"\bPlanete\s+(?:V\s*)?3\b", "Planete", text)
        text = re.sub(r"\bplanete\s+(?:v\s*)?3\b", "planete", text)
        return text

    @staticmethod
    def _format_answer(item: dict) -> str:
        """Construit la réponse complète à partir d'une entrée FAQ_PLANETE3.

        Combine `reponse` + listes structurées (etapes, details, causes,
        types, etc.) + note/info finale. Format markdown simple, sans gras.
        Applique la normalisation PLANETE 3 → PLANETE (sauf Q3/Q4)."""
        question_id = item.get("id")
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

        result = "\n".join(p for p in parts if p).strip()

        # Normaliser PLANETE 3 → PLANETE (sauf Q3 et Q4)
        # Pour les enseignants, PLANETE = PLANETE 3 (version actuelle).
        # On préserve l'URL planete3.education.sn (regex exige un espace).
        result = PlaneteFAQService._normalize_planete_terminology(
            result, question_id
        )
        return result

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

        Combine 5 signaux :
        1. TF-IDF sur corpus enrichi (questions + keywords + synonymes)
        2. Boost mots-clés métier PLANETE en commun
        3. Fuzzy matching de la question (rapidfuzz si dispo, fallback simple)
        4. Bonus de correspondance exacte (la requête est ~égale à la question)
        5. Pénalité "mots en trop" : si le candidat contient des mots
           significatifs absents de la requête (ex: "PLANETE 3" candidat
           pour requête "PLANETE"), on pénalise pour préférer le candidat
           le plus précis.
        """
        if not self.is_available or not query.strip():
            return None

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            # 1. Préparer la requête : normaliser + expansion synonymes
            q_norm = normalize_text(query)
            q_expanded = expand_query_with_synonyms(query)

            # 2. TF-IDF cosinus
            q_vec = self._vectorizer.transform([q_expanded])
            tfidf_scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()

            # 3. Boost mots-clés PLANETE en commun (signal lexique)
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
                        # Bonus proportionnel : +0.04 par mot-clé partagé, plafonné à +0.20
                        boosts[i] = min(0.04 * len(common), 0.20)

            # 4. Fuzzy matching question vs requête (rattrape les fautes)
            fuzzy_scores = self._compute_fuzzy_scores(query)

            # 5. Bonus correspondance exacte + pénalité "mots en trop"
            exactness = self._compute_exactness_scores(q_norm)

            # 6. Concept-match : si la requête mentionne "bâtiment" et que
            #    la QUESTION du candidat contient aussi "bâtiment", c'est
            #    fortement indicatif que c'est le bon match. Évite que
            #    "configurer un bâtiment" tombe sur Q18 qui parle de
            #    configurer l'environnement physique (où "bâtiments" est
            #    mentionné dans la liste des éléments mais n'est pas le
            #    sujet principal de la question).
            concept_scores = self._compute_concept_match_scores(q_norm)

            # 7. Combinaison pondérée :
            #    35 % TF-IDF · 15 % fuzzy · 10 % boost lexique
            #    · 20 % exactitude · 20 % concept-match
            combined = (
                0.35 * tfidf_scores
                + 0.15 * fuzzy_scores
                + 0.10 * boosts
                + 0.20 * exactness
                + 0.20 * concept_scores
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
                exactness=round(float(exactness[best_idx]), 3),
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

    def _compute_exactness_scores(self, q_norm: str):
        """Calcule un score d'exactitude [0..1] entre la requête (déjà
        normalisée) et chaque question.

        Principe : on compare les ensembles de mots SIGNIFICATIFS (hors
        stopwords). Si le candidat a peu de mots en plus, c'est un
        match précis ; s'il en a beaucoup, c'est imprécis.

        Cas particulièrement traité :
          requête  = "qu est ce que planete"          → mots {planete}
          cand. Q1 = "qu est ce que planete"          → mots {planete}, extra=0 → 1.0
          cand. Q2 = "qu est ce que planete 3"        → mots {planete, 3}, extra=1 → ~0.5
        """
        import numpy as np
        scores = np.zeros(len(self._items), dtype=float)

        # Filtrer les mots significatifs de la requête
        q_words = self._significant_words(q_norm)
        if not q_words:
            return scores

        for i, item in enumerate(self._items):
            cand_norm = normalize_text(item["question"])
            c_words = self._significant_words(cand_norm)
            if not c_words:
                continue

            shared = q_words & c_words
            extra_in_candidate = c_words - q_words
            missing_in_candidate = q_words - c_words

            if not shared:
                continue

            # Couverture : combien de mots de la requête sont dans le candidat
            coverage = len(shared) / len(q_words)

            # Pénalité pour chaque mot du candidat absent de la requête.
            # Pénalité forte (0.30) car c'est précisément ce signal qui
            # distingue Q1 "Qu'est-ce que PLANETE" (extra=0) de Q2
            # "Qu'est-ce que PLANETE 3" (extra=1, donc -0.30).
            extra_penalty = 0.30 * len(extra_in_candidate)
            missing_penalty = 0.10 * len(missing_in_candidate)

            score = coverage - extra_penalty - missing_penalty

            # Bonus correspondance EXACTE (mêmes mots significatifs)
            if not extra_in_candidate and not missing_in_candidate:
                score += 0.60  # gros bonus pour match parfait

            scores[i] = max(0.0, min(1.0, score))

        return scores

    @staticmethod
    def _significant_words(text_norm: str) -> set[str]:
        """Retourne l'ensemble des mots significatifs (hors stopwords FR)
        d'un texte normalisé.

        IMPORTANT : on garde les chiffres ("3") même s'ils ne font qu'1
        caractère, car ils sont discriminants ("PLANETE" vs "PLANETE 3").
        """
        words = text_norm.split()
        return {
            w for w in words
            if w not in FR_STOPWORDS
            and (len(w) > 1 or w.isdigit())
        }

    def _compute_concept_match_scores(self, q_norm: str):
        """Calcule un score [0..1] qui récompense les candidats dont la
        QUESTION (pas seulement le contenu) partage les mêmes concepts
        PLANETE que la requête.

        Exemple critique :
          Requête : "comment configurer un batiment"
          Concept détecté : 'batiment'
          - Q18 "configurer l'environnement physique" → 'batiment' n'est
            pas dans sa question principale → 0.0
          - Q19 "créer un bâtiment dans PLANETE 3" → 'batiment' est dans
            sa question → 1.0  → préférer Q19

        Si plusieurs concepts matchent, on cumule (max 1.0).
        Si aucun concept dans la requête, retourne tableau de zéros.
        """
        import numpy as np
        scores = np.zeros(len(self._items), dtype=float)

        # 1. Détecter les concepts présents dans la requête
        query_concepts = set()
        for concept_id, variants in PLANETE_CONCEPTS.items():
            for v in variants:
                v_norm = normalize_text(v)
                if " " in v_norm:
                    if v_norm in q_norm:
                        query_concepts.add(concept_id)
                        break
                else:
                    if re.search(rf"\b{re.escape(v_norm)}\b", q_norm):
                        query_concepts.add(concept_id)
                        break

        if not query_concepts:
            return scores

        # 2. Pour chaque candidat, vérifier ses concepts en commun avec
        #    la requête (uniquement dans la QUESTION du candidat).
        for i, item in enumerate(self._items):
            cand_q_norm = normalize_text(item["question"])
            cand_concepts = set()
            for concept_id in query_concepts:  # ne tester que les concepts pertinents
                variants = PLANETE_CONCEPTS[concept_id]
                for v in variants:
                    v_norm = normalize_text(v)
                    if " " in v_norm:
                        if v_norm in cand_q_norm:
                            cand_concepts.add(concept_id)
                            break
                    else:
                        if re.search(rf"\b{re.escape(v_norm)}\b", cand_q_norm):
                            cand_concepts.add(concept_id)
                            break

            common = query_concepts & cand_concepts
            if common:
                # Score = ratio de concepts en commun, plafonné à 1.0
                scores[i] = min(1.0, len(common) / len(query_concepts))

        return scores

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
