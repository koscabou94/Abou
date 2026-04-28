"""
Service NLP principal gérant le LLM (Groq API - llama-3.3-70b-versatile).
Inclut la classification d'intention et la génération de réponses contextuelles.
"""

import re
import asyncio
from typing import Optional
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class NLPService:
    """
    Service NLP qui gère le modèle de langage via Groq API.
    """

    SYSTEM_PROMPT = """Tu es EduBot, l'assistant intelligent du Ministère de l'Éducation Nationale du Sénégal.

RÈGLE ABSOLUE DE FORMATAGE (priorité maximale) :
- N'utilise JAMAIS le gras nulle part. ZÉRO gras dans tes réponses.
- Pas de `**texte**`, pas de `__texte__`, pas de `<strong>`, pas de `<b>`.
- Pas de gras dans les titres, ni dans les listes, ni dans les fiches, ni dans les exercices, ni dans les énumérations, ni nulle part.
- Utilise uniquement ### pour les titres de sections (sans aucun gras dans le titre).
- Si tu veux mettre en valeur un terme, utilise simplement une nouvelle ligne ou une liste, JAMAIS le gras.
- Pour les noms d'éléments dans une liste (étape 1, étape 2…), écris le nom en texte normal suivi de deux points.

TON IDENTITÉ :
- Tu t'appelles EduBot.
- Tu aides les élèves, les parents et les enseignants du Sénégal.
- Tu es chaleureux, naturel et direct — comme un bon professeur particulier.

FAITS ACTUELS (2026) :
- Nous sommes en 2026.
- Président du Sénégal : Bassirou Diomaye Faye (élu au 1er tour en mars 2024).
- Premier Ministre : Ousmane Sonko (nommé en mars 2024).
- Capitale : Dakar. Monnaie : FCFA. Langue officielle : Français.

PLANETE (connaissance obligatoire) :
- POUR LES UTILISATEURS, PLANETE = PLANETE 3. Dans tes réponses, dis simplement "PLANETE" — pas "PLANETE 3".
  Exception : si la question demande explicitement la différence ou les versions, mentionne PLANETE 1, 2, 3.
- PLANETE = Paquet de Logiciels Académiques Normalisés pour les Établissements et Écoles.
- C'est la plateforme officielle de gestion des établissements et écoles du Ministère de l'Éducation du Sénégal.
- PLANETE permet de gérer : l'environnement physique, l'environnement pédagogique, la vie scolaire et la communication entre acteurs.
- Elle facilite aussi la collecte et le traitement des données statistiques.
- Versions (à mentionner uniquement si demandé) : PLANETE 1 (2012-2017), PLANETE 2 (2018-2025), PLANETE 3 (2026 — version actuelle, préscolaire, élémentaire, moyen secondaire).
- Acteurs : administration, enseignants, élèves, parents, IEF/IA, directions pédagogiques (DEE, DEMSG, DEPS).
- Accès : https://planete3.education.sn avec e-mail professionnel (prenom.nom@education.sn).
  L'URL contient "planete3" car c'est la version 3, mais quand tu en parles dis simplement "PLANETE".

NIVEAUX SCOLAIRES AU SÉNÉGAL :
- Préscolaire : Petite, Moyenne, Grande section
- Élémentaire : CI (Cours d'Initiation, 1ère classe), CP, CE1, CE2, CM1, CM2 (examen : CFEE)
- Moyen / Collège : 6ème, 5ème, 4ème, 3ème (examen : BFEM)
- Lycée : 2nde, 1ère, Terminale (examen : BAC)
- Séries au lycée : L (Littéraire), S1/S2/S3 (Scientifique), G (Gestion), T (Technique)
- IMPORTANT : Le CI (Cours d'Initiation) est la PREMIÈRE classe de l'élémentaire au Sénégal, AVANT le CP.

CURRICULUM OFFICIEL CEB (Curriculum de l'Éducation de Base) :
- Tu as accès aux programmes officiels du Ministère de l'Éducation Nationale du Sénégal :
  Étape 1 (CI/CP), Étape 2 (CE1/CE2), Étape 3 (CM1/CM2), guides anglais et arabe.
- Quand un extrait du programme officiel apparaît dans le contexte (sous "[Programme officiel CEB]"),
  TU DOIS t'en inspirer pour formuler tes exercices et tes réponses. Cite les paliers et
  objectifs spécifiques (OS) quand c'est pertinent (ex : "Selon le palier 3 du CM2…").
- Les paliers structurent le programme : 4 paliers par classe (CI: paliers 1-4, CP: paliers 5-8, etc.).
- L'approche pédagogique officielle est l'APC (Approche Par les Compétences) avec la Pédagogie de l'intégration.
- Adapte toujours tes exercices à ce que les élèves doivent savoir à ce palier précis.

GÉNÉRATION D'EXERCICES (TRÈS IMPORTANT) :
Quand un élève, un parent ou un enseignant demande des exercices ou de la remédiation, tu DOIS les générer directement, sans jamais refuser.
- Génère des exercices adaptés au programme officiel du Sénégal et au niveau demandé.
- Si le niveau n'est pas précisé, demande-le avant de générer.
- Numérote chaque exercice (Ex. 1, Ex. 2, Ex. 3...).
- Adapte la difficulté : exercices simples et progressifs pour la remédiation.
- Pour les mathématiques : mélange calcul, problèmes concrets, géométrie selon le niveau.
- Pour le français : dictée, conjugaison, compréhension, expression écrite selon le niveau.
- Ajoute les corrigés à la fin si l'utilisateur le demande, ou propose-les.
- Utilise des contextes locaux sénégalais dans les énoncés (marchés, tirailleurs, agriculture, etc.) pour que ce soit proche de la réalité des élèves.

FORMAT OBLIGATOIRE POUR LES EXERCICES (respecte exactement ce format) :

### Exercices de Mathématiques — CM2

---

### Exercice 1 — Calcul

Moussa a 1 250 FCFA. Il achète 3 cahiers à 350 FCFA chacun. Combien lui reste-t-il ?

---

### Exercice 2 — Problème

Un agriculteur récolte 48 kg de mil par jour. Combien récolte-t-il en une semaine ?

---

### Exercice 3 — Géométrie

Trace un rectangle de longueur 6 cm et de largeur 4 cm. Calcule son périmètre et son aire.

---

Voulez-vous les corrigés ? Je peux aussi proposer d'autres exercices ou changer le niveau.

RÈGLES DE FORMAT EXERCICES :
- Utilise TOUJOURS ### pour le titre général et chaque exercice
- Mets TOUJOURS --- entre chaque exercice (séparateur)
- Laisse une ligne vide entre le titre de l'exercice et son énoncé
- Ne mets JAMAIS le titre et l'énoncé sur la même ligne
- INTERDIT ABSOLU : N'utilise JAMAIS le gras (**...**) nulle part. Zéro gras.
- Respecte EXACTEMENT la quantité d'exercices demandée (si l'utilisateur dit "2 exercices", génère 2, pas 3).
- Respecte EXACTEMENT la matière demandée (physique → physique, chimie → chimie, PAS maths).
- Pour les exercices en ANGLAIS : rédige les textes, questions et énoncés EN ANGLAIS (pas en français). Les consignes générales peuvent être en français.
- Pour les exercices en ESPAGNOL : rédige en espagnol. Pour l'ARABE : rédige en arabe.
- Si l'utilisateur demande plusieurs matières (ex: 3 physique + 2 chimie), génère exactement ça.

---

GÉNÉRATION DE FICHES PÉDAGOGIQUES :
Quand un enseignant demande une fiche de préparation, une fiche de cours, une fiche pédagogique ou une fiche de leçon, génère-la DIRECTEMENT avec ce format :

### Fiche Pédagogique — [Matière] — [Niveau]

Discipline : [Matière]
Niveau : [Classe]
Durée : [ex. 45 minutes]
Compétence visée : [Objectif général]

---

### Objectifs spécifiques

À la fin de la séance, l'élève sera capable de :
1. [Objectif 1]
2. [Objectif 2]
3. [Objectif 3]

---

### Contenu / Notions clés

[Corps du cours : définitions, règles, exemples concrets avec des références sénégalaises]

---

### Déroulement de la séance

| Phase | Activités du maître | Activités des élèves | Durée |
|-------|---------------------|----------------------|-------|
| Introduction | Poser une question de mise en situation | Répondre et participer | 5 min |
| Développement | Expliquer et illustrer au tableau | Écouter, noter, poser des questions | 30 min |
| Application | Proposer des exercices | Résoudre les exercices | 10 min |

---

### Évaluation formative

[2 à 3 questions ou exercices courts pour vérifier la compréhension]

---

Fiche générée par EduBot — Ministère de l'Éducation Nationale du Sénégal

RÈGLES FICHES :
- Une fiche pédagogique N'EST PAS des exercices. Ne JAMAIS générer des exercices quand on demande une fiche.
- La fiche contient : objectifs, contenu/notions, déroulement en tableau, évaluation formative. Pas de liste d'exercices.
- Si le niveau ou la matière n'est pas précisé, demande-le avant de générer.
- Si le niveau EST précisé dans la conversation (même dans un message précédent), utilise-le directement SANS le redemander.
- Adapte le contenu au programme officiel du Sénégal.
- Utilise des exemples locaux sénégalais.
- Génère toujours la fiche complète, jamais de réponse vague.

---

MÉMOIRE DE CONVERSATION :
- Si l'utilisateur a déjà donné le niveau ou la classe dans la conversation, NE PAS le redemander.
- Si l'utilisateur a déjà donné la matière, NE PAS la redemander.
- Utilise toujours les informations déjà fournies dans la conversation pour compléter ta réponse.

---

COMMENT RÉPONDRE (GÉNÉRAL) :
- Va directement à la réponse. La première phrase répond à la question.
- Pour les exercices : génère-les immédiatement avec un beau format.
- Pour les fiches pédagogiques : génère la fiche, PAS des exercices.
- Pour les questions sur PLANETE/MIRADOR : réponse précise en 3-4 phrases.
- Termine toujours par une invitation courte.

---

SOUS-MATIÈRES DU FRANÇAIS (très important) :
Ces sujets font TOUS partie de la matière Français — génère les exercices correspondants directement :
- grammaire → exercices de grammaire (en français)
- conjugaison → exercices de conjugaison (en français)
- orthographe → exercices d'orthographe
- dictée → exercice de dictée
- lecture → exercice de lecture/compréhension
- écriture / expression écrite → exercice d'expression écrite
- vocabulaire → exercice de vocabulaire
- rédaction → exercice de rédaction
Ne JAMAIS demander "quelle matière ?" quand l'utilisateur dit "grammaire", "conjugaison", "orthographe", etc. C'est forcément du Français.

---

CORRECTIONS ET CORRIGÉS :
- Si l'utilisateur dit "avec corrigé", "avec les corrections", "corrigés inclus" → génère les exercices ET leur corrigé complet dans la même réponse, après une section "### Corrigés".
- Si l'utilisateur dit juste "exercices" sans mentionner le corrigé → génère les exercices seulement, puis propose "Voulez-vous les corrigés ?" à la fin.
- Si l'utilisateur demande "les corrections" ou "le corrigé" APRÈS avoir reçu des exercices → génère les corrections des exercices de la conversation précédente, pas de nouveaux exercices.

---

RÉPONSES INTELLIGENTES ET CONTEXTUELLES :
- Si l'utilisateur dit "j'ai une question", "j'ai besoin d'aide", "je voudrais savoir" sans préciser → réponds : "Quelle est votre question ? Je suis là pour vous aider !"
- Si l'utilisateur pose une question courte ou vague, demande des précisions de façon chaleureuse.
- Utilise TOUJOURS le contexte de la conversation. Si le niveau ou la matière ont déjà été mentionnés, ne les redemande pas.

---

RÈGLE ABSOLUE : Ne jamais refuser de générer des exercices ou des fiches. Ne jamais donner une réponse sans rapport avec la question. Ne JAMAIS utiliser le gras (**...**) dans aucune réponse."""

    INTENT_RULES: dict = {
        "salutation": [
            "bonjour", "bonsoir", "salut", "hello", "hi", "hey", "coucou",
            "salam", "assalamu", "nanga def", "na nga def", "jam", "mbaa",
            "merci", "au revoir", "bonne journée", "bonne soirée",
            "comment ça va", "comment ca va", "ça va", "ca va",
            "quoi de neuf", "comment vas-tu", "comment allez"
        ],
        "inscription": [
            "inscri", "enregistr", "dossier", "formulaire", "nouveau", "première fois",
            "comment s'inscrire", "inscription", "inscrire", "matricule"
        ],
        "calendrier": [
            "date", "quand", "calendrier", "rentrée", "vacances", "congé", "trimestre",
            "semestre", "emploi du temps", "horaire", "planning", "fermeture", "ouverture"
        ],
        "examen": [
            "examen", "bfem", "bac", "cfee", "concours", "résultat", "note", "correction",
            "épreuve", "composition", "évaluation", "contrôle", "certificat", "diplôme"
        ],
        "orientation": [
            "orientation", "filière", "lycée", "université", "après le bfem", "après le bac",
            "choisir", "que faire", "quelle filière", "option", "section", "parcours"
        ],
        "bourse": [
            "bourse", "aide", "financement", "allocation", "subvention", "frais",
            "payer", "gratuit", "payant", "argent", "cantine", "transport"
        ],
        "programme": [
            "programme", "matière", "curriculum", "ceb", "contenu", "manuel",
            "livre", "enseignement", "apprentissage", "chapitre",
            "objectifs", "compétences", "competences",
            "palier", "paliers",
            "que doit savoir", "ce que l'élève doit",
            "officiel sénégalais", "officiel senegalais",
        ],
        "administratif": [
            "attestation", "certificat de scolarité", "relevé", "document",
            "administration", "directeur", "proviseur", "inspecteur",
            "académie", "cachet", "signature", "légalisation", "ief"
        ],
        "enseignant": [
            "professeur", "enseignant", "maître", "maîtresse", "prof", "instituteur",
            "formation", "recrutement", "concours enseignant", "FASTEF", "CRFPE"
        ],
        "planete": [
            # Termes explicites
            "planete", "planète", "planete3", "planète3", "planete 3", "planète 3",
            "simen", "education.sn", "@education.sn", "planete3.education.sn",
            # Concepts métier (détection implicite — l'utilisateur ne dit pas "PLANETE"
            # mais parle de la plateforme)
            "gestion scolaire", "tableau de bord", "fiche établissement", "fiche etablissement",
            "polarisation", "bst", "polarisateur",
            # Configuration
            "configurer", "configuration", "paramétrer", "parametrer",
            "environnement physique", "environnement pédagogique", "environnement pedagogique",
            "bâtiment", "batiment", "bâtiments", "batiments",
            "salle de classe", "classe pédagogique", "classe pedagogique",
            "groupage", "groupage de classes",
            "second semestre", "frais de scolarité", "frais de scolarite",
            "compte bancaire",
            # Personnel
            "complément horaire", "complement horaire",
            "pointage", "prise de service", "archiver agent", "archivage agent",
            "ien", "import personnel", "mise à jour personnel",
            # Élèves
            "inscription élève", "inscription eleve", "inscrire un élève", "inscrire un eleve",
            "affectation élève", "affectation eleve", "affecter un élève", "affecter un eleve",
            "transfert entrant", "transfert sortant", "import élèves", "import eleves",
            "reprise scolarité", "reprise scolarite",
            "bfem", "candidat bfem", "élève bst", "eleve bst",
            # Emploi du temps
            "emploi du temps", "edt", "génération automatique edt", "generer edt",
            "export edt",
            # Cours / absences
            "cahier de texte", "cahier texte",
            "justifier absence", "absence justifiée", "absence justifiee",
            "saisir absences", "saisir les absences", "consulter absences",
            # Rapport journalier
            "rapport de fin de journée", "rapport de fin de journee", "rapport journalier",
            "déclarer un incident", "declarer un incident",
            # Évaluations
            "planifier évaluation", "planifier evaluation",
            "saisir les notes", "saisir notes", "notation",
            "verrouiller évaluation", "verrouiller evaluation",
            # Conseils
            "conseil de classe", "conseils de classe", "conseil classe",
            "saisir appréciations", "saisir appreciations",
            "valider conseil", "validation conseil",
            # Utilisateurs
            "ajouter utilisateur", "attribuer profil", "rechercher utilisateur",
            "chef d'établissement", "chef etablissement",
            # Versions
            "planete 1", "planete 2", "planete v3", "planete v1", "planete v2",
            # Cycle / établissement
            "nomade", "cycle", "polarisation bst",
        ],
        "mirador": [
            "mirador", "carrière", "mutation", "mouvement", "affectation",
            "solde", "fiche de paie", "mise à disposition"
        ],
        "identifiant": [
            "ien", "matricule", "identifiant", "code", "trouver ien"
        ],
        "pedagogique": [
            "saisie", "absence", "appel", "pédagogique",
            "discipline", "coefficient", "crédit"
        ],
        "connexion": [
            "connecter", "mot de passe", "email", "professionnel", "compte",
            "accès", "oublié"
        ],
        "exercice": [
            "exercice", "exercices", "exo", "exos", "devoir", "devoirs",
            "problème", "problèmes", "probleme", "problemes",
            "remédiation", "remediation", "soutien scolaire",
            "entrainement", "entraînement", "révision", "revision",
            "quiz", "test", "évaluation", "contrôle",
            "ci", "cp", "ce1", "ce2", "cm1", "cm2", "primaire", "élémentaire", "elementaire",
            "6ème", "5ème", "4ème", "3ème", "6eme", "5eme", "4eme", "3eme",
            "seconde", "première", "terminale", "lycée", "college", "collège",
            "série s", "serie l", "bac", "bfem", "cfee",
            "mathématiques", "mathematiques", "maths", "français", "francais",
            "physique", "chimie", "svt", "biologie", "sciences physiques", "science physique",
            "physique-chimie", "histoire", "géographie", "geographie",
            "anglais", "english", "espagnol", "arabe",
            "philosophie", "calcul", "géométrie", "geometrie", "algèbre",
            "informatique", "technologie", "éducation civique",
            "mon enfant", "mon fils", "ma fille", "mon élève", "niveau",
            "fiche", "fiches", "fiche pédagogique", "fiche pedagogique",
            "fiche de cours", "fiche de préparation", "fiche de preparation",
            "fiche de leçon", "fiche de lecon", "fiche d'enseignant",
            "préparation de cours", "preparation de cours",
            "plan de leçon", "plan de cours", "séance", "seance",
            "objectifs pédagogiques", "objectifs pedagogiques",
            "déroulement", "deroulement", "compétence", "competence"
        ],
    }

    _SHORT_KEYWORDS = {"hi", "he", "hey", "la", "ko", "mi", "an", "on",
                        "mo", "a", "no", "o", "di", "bi", "gi", "yi",
                        "si", "bu", "su", "ku", "nu", "mu", "te", "ci",
                        "ak", "os"}

    def __init__(self) -> None:
        self._groq_client = None
        self._client_lock = asyncio.Lock()
        logger.info("Service NLP initialisé (Groq)", model=settings.LLM_MODEL)

    async def _ensure_client(self):
        if self._groq_client is not None:
            return self._groq_client
        async with self._client_lock:
            if self._groq_client is not None:
                return self._groq_client
            try:
                from groq import AsyncGroq
                self._groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
                logger.info("Client Groq initialisé")
            except Exception as exc:
                logger.error("Échec init Groq", error=str(exc))
                raise
        return self._groq_client

    def classify_intent(self, text: str) -> tuple:
        if not text:
            return ("general", 0.5)
        text_lower = text.lower()
        text_words = set(re.findall(r'\b\w+\b', text_lower))
        scores = {}
        for intent, keywords in self.INTENT_RULES.items():
            score = 0
            for keyword in keywords:
                if keyword in self._SHORT_KEYWORDS or len(keyword) <= 3:
                    if keyword in text_words:
                        score += 1
                elif " " in keyword:
                    if keyword in text_lower:
                        score += 1
                else:
                    if re.search(r'\b' + re.escape(keyword), text_lower):
                        score += 1
            if score > 0:
                scores[intent] = score

        # ── BOOST PLANETE ──
        # Quand PLANETE a au moins 1 hit, on considère que la question
        # PARLE de PLANETE même si d'autres intents matchent. C'est crucial
        # pour les questions implicites du type "comment configurer
        # l'environnement physique", "comment créer un bâtiment", etc.
        # La FAQ_PLANETE3 contient les réponses détaillées et doit être
        # consultée en priorité.
        if scores.get("planete", 0) >= 1:
            # Donne à PLANETE un score artificiellement élevé pour qu'il
            # remporte le tri. On garde le score original pour le calcul
            # de confiance afin de refléter la réalité du texte.
            original_planete_score = scores["planete"]
            # Si PLANETE est déjà le max, rien à faire. Sinon, on l'élève
            # au-dessus du max actuel (sauf si une autre intent très
            # spécifique a beaucoup plus de hits — seuil > 3).
            current_max = max(scores.values())
            other_max = max(
                (v for k, v in scores.items() if k != "planete"),
                default=0,
            )
            # PLANETE l'emporte sauf si une autre intent a 3+ hits ET
            # 2× plus de hits que PLANETE (cas limite)
            if other_max < 3 or other_max < 2 * original_planete_score:
                scores["planete"] = max(current_max + 1, original_planete_score)

        if not scores:
            return ("general", 0.5)
        best_intent = max(scores, key=scores.__getitem__)
        best_score = scores[best_intent]
        max_possible = len(self.INTENT_RULES[best_intent])
        confidence = min(best_score / max_possible + 0.5, 1.0)
        return (best_intent, confidence)

    @staticmethod
    def _clean_llm_response(text: str) -> str:
        for tag in ["<<SYS>>", "<</SYS>>", "[INST]", "[/INST]", "</s>", "<s>"]:
            text = text.replace(tag, "")

        # Supprimer TOUT le gras et l'italique — ordre important : *** avant ** avant *
        # 1. Gras+italique ***...***
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text, flags=re.DOTALL)
        # 2. Gras **...** (avec ou sans espace intérieur)
        text = re.sub(r'\*\*\s*(.+?)\s*\*\*', r'\1', text, flags=re.DOTALL)
        # 3. Gras __...__ (markdown alternatif)
        text = re.sub(r'__\s*(.+?)\s*__', r'\1', text, flags=re.DOTALL)
        # 4. ** seuls orphelins (ne faisant pas partie d'une paire)
        text = re.sub(r'\*\*', '', text)
        # 5. Tags HTML <strong> et <b> au cas où le LLM en produirait
        text = re.sub(r'</?strong[^>]*>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</?b\s*[^>]*>', '', text, flags=re.IGNORECASE)

        lines = [l for l in text.split("\n") if l.strip()]
        text = "\n".join(lines).strip()
        paragraphs = text.split("\n\n")
        seen = set()
        unique = []
        for p in paragraphs:
            normalized = p.strip().lower()[:100]
            if normalized not in seen:
                seen.add(normalized)
                unique.append(p)
        return "\n\n".join(unique).strip()

    async def _call_groq(
        self,
        chat_messages: list,
        max_tokens: int,
        timeout: float,
        model: Optional[str] = None,
    ) -> str:
        """Appel Groq unique — retourne le texte ou lève une exception."""
        client = await self._ensure_client()
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model or settings.LLM_MODEL,
                messages=chat_messages,
                max_tokens=max_tokens,
                temperature=settings.TEMPERATURE,
            ),
            timeout=timeout
        )
        return response.choices[0].message.content.strip()

    async def _call_groq_with_retry(
        self,
        chat_messages: list,
        max_tokens: int,
        timeout: float = 45.0,
        max_attempts: int = 2,
    ) -> Optional[str]:
        """Appel Groq avec retry exponentiel sur erreurs transitoires.
        Bascule sur le modèle rapide au dernier essai si le principal échoue."""
        delay = 0.5
        for attempt in range(1, max_attempts + 1):
            model_to_use = (
                settings.LLM_MODEL
                if attempt < max_attempts
                else settings.LLM_FAST_MODEL  # Dernier essai → modèle rapide
            )
            try:
                text = await self._call_groq(
                    chat_messages, max_tokens, timeout=timeout, model=model_to_use
                )
                if text:
                    if attempt > 1:
                        logger.info(
                            "Groq réussi après retry",
                            attempt=attempt,
                            model=model_to_use,
                        )
                    return text
            except asyncio.TimeoutError:
                logger.warning(
                    "Groq timeout",
                    attempt=attempt,
                    model=model_to_use,
                    timeout=timeout,
                )
            except Exception as exc:
                err_msg = str(exc).lower()
                # Erreurs non-récupérables : auth, quota épuisé → on n'insiste pas
                if any(k in err_msg for k in ("api key", "unauthorized", "401", "403")):
                    logger.error(
                        "Groq erreur non-récupérable", error=str(exc)
                    )
                    return None
                logger.warning(
                    "Groq erreur transitoire",
                    attempt=attempt,
                    model=model_to_use,
                    error=str(exc),
                )
            # Attente exponentielle avant retry
            if attempt < max_attempts:
                await asyncio.sleep(delay)
                delay *= 2
        return None

    async def generate_response(
        self,
        message: str,
        context: list,
        intent: Optional[str] = None,
        knowledge_context: Optional[str] = None
    ) -> str:
        if intent == "salutation":
            return self._get_greeting_response(message)

        chat_messages = self._build_chat_messages(message, context, intent, knowledge_context)

        # Pipeline standard : retry exponentiel avec bascule modèle rapide
        text = await self._call_groq_with_retry(
            chat_messages,
            max_tokens=settings.MAX_TOKENS,
            timeout=45.0,
            max_attempts=2,
        )
        if text:
            return self._clean_llm_response(text)

        # Retry spécifique exercices : prompt allégé pour maximiser les chances
        if intent == "exercice":
            try:
                await asyncio.sleep(1)
                simple_messages = [
                    {"role": "system", "content": (
                        "Tu es EduBot, assistant éducatif sénégalais. "
                        "Génère exactement 3 exercices numérotés pour le niveau et la matière demandés. "
                        "Utilise des contextes sénégalais dans les énoncés. "
                        "N'utilise JAMAIS le gras (**...**) dans les énoncés. "
                        "Format : ### Exercice 1\n[énoncé]\n---\n### Exercice 2\n[énoncé]\n---\n### Exercice 3\n[énoncé]"
                    )},
                    {"role": "user", "content": message}
                ]
                # Utiliser le modèle rapide pour le retry
                fast_model = settings.LLM_FAST_MODEL
                client = await self._ensure_client()
                resp = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=fast_model,
                        messages=simple_messages,
                        max_tokens=1500,
                        temperature=0.4,
                    ),
                    timeout=40.0
                )
                text = resp.choices[0].message.content.strip()
                if text:
                    logger.info("Groq retry réussi (modèle rapide)", model=fast_model)
                    return self._clean_llm_response(text)
            except asyncio.TimeoutError:
                logger.warning("Groq timeout (retry modèle rapide)")
            except Exception as exc:
                logger.warning("Groq indisponible (retry modèle rapide)", error=str(exc))

        if knowledge_context:
            return self._build_lightweight_response(message, knowledge_context, intent)
        return self._get_fallback_response(intent)

    def _build_chat_messages(self, message, context, intent=None, knowledge_context=None):
        system_content = self.SYSTEM_PROMPT
        if intent and intent != "general":
            intent_labels = {
                "inscription": "sur les procédures d'inscription scolaire",
                "calendrier": "sur le calendrier scolaire",
                "bourse": "sur les bourses et aides financières",
                "programme": "programme",  # géré séparément ci-dessous
                "administratif": "sur les démarches administratives",
                "enseignant": "sur le corps enseignant et la formation",
                "planete": "sur l'utilisation de la plateforme PLANETE",
                "mirador": "sur la plateforme de gestion RH MIRADOR",
                "identifiant": "sur les identifiants professionnels (IEN/Matricule)",
                "pedagogique": "sur les aspects pédagogiques (notes, absences, cours)",
                "connexion": "sur les problèmes d'accès et de connexion",
                "exercice": "exercice",  # géré séparément ci-dessous
            }
            if intent in intent_labels:
                if intent == "exercice":
                    msg_lower = message.lower()
                    is_fiche = any(w in msg_lower for w in ["fiche", "préparation de cours", "preparation de cours", "plan de leçon", "plan de cours", "séance", "seance", "objectifs pédagogiques"])
                    if is_fiche:
                        system_content += f"\n⚡ L'utilisateur demande une FICHE PÉDAGOGIQUE. Génère-la DIRECTEMENT et COMPLÈTEMENT avec le format structuré prévu (objectifs, contenu, déroulement en tableau, évaluation). N'attends pas de permission supplémentaire."
                    else:
                        system_content += f"\n⚡ L'utilisateur demande des exercices ou de la remédiation. GÉNÈRE-LES DIRECTEMENT avec un format clair et numéroté. N'attends pas de permission supplémentaire."
                elif intent == "programme":
                    # IMPORTANT : ne pas générer d'exercices ! L'utilisateur veut
                    # une DESCRIPTION du programme officiel (objectifs, paliers,
                    # compétences). Réponds en utilisant les extraits du curriculum
                    # CEB qui te sont fournis dans le contexte.
                    system_content += (
                        "\n⚡ L'utilisateur demande une DESCRIPTION du programme officiel "
                        "(curriculum CEB). NE GÉNÈRE PAS D'EXERCICES. "
                        "Décris le programme en t'appuyant sur les extraits du curriculum "
                        "officiel fournis dans le contexte. "
                        "Structure ta réponse : 1) Objectifs / compétences attendues, "
                        "2) Domaines et sous-domaines, 3) Paliers (CI : 1-4, CP : 5-8, etc.), "
                        "4) Citation textuelle des objectifs spécifiques quand c'est dans le contexte. "
                        "Si l'utilisateur veut ENSUITE des exercices, propose-le à la fin "
                        "(exemple : 'Voulez-vous que je génère des exercices basés sur ce programme ?'). "
                        "N'utilise pas de gras."
                    )
                else:
                    system_content += f"\nL'utilisateur pose une question {intent_labels[intent]}."
        if knowledge_context:
            system_content += f"\n\n{knowledge_context}"

        messages = [{"role": "system", "content": system_content}]
        recent_context = context[-(settings.CONTEXT_WINDOW * 2):]
        for msg in recent_context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        # Pour les exercices et fiches, on donne plus de liberté (pas de contrainte de longueur)
        if intent == "exercice":
            messages.append({"role": "user", "content": message})
        else:
            messages.append({"role": "user", "content": f"{message}\n\n(Réponds SEULEMENT à cette question, de façon concise et directe.)"})
        return messages

    def _build_lightweight_response(self, message, knowledge_context, intent=None):
        stop = {'comment', 'est', 'ce', 'que', 'quoi', 'le', 'la', 'les', 'un', 'une',
                'des', 'du', 'de', 'au', 'aux', 'pour', 'dans', 'sur', 'mon', 'ma',
                'je', 'vous', 'nous', 'a', 'et', 'ou', 'se', 'en', 'qui', 'il', 'elle'}
        lines = knowledge_context.strip().split("\n\n")
        content_blocks = [l.strip() for l in lines if l.strip()
                          and not l.startswith("Contexte de référence")
                          and not l.startswith("Voici des informations")
                          and not l.startswith("Utilise ces informations")]
        if not content_blocks:
            return self._get_fallback_response(intent)
        msg_words = set(message.lower().split())
        scored = sorted([(len(msg_words & set(b.lower().split())), b) for b in content_blocks], reverse=True)
        result = scored[0][1] if scored else ""
        result = "\n".join([l.strip() for l in result.split("\n") if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("Figure")])
        if len(result) > 400:
            cut = result[:400]
            last_period = max(cut.rfind('.'), cut.rfind('\n'))
            result = cut[:last_period + 1] if last_period > 150 else cut + "..."
        return (result + "\n\nN'hésitez pas si vous avez d'autres questions !") if result.strip() else self._get_fallback_response(intent)

    def _get_greeting_response(self, message: str) -> str:
        msg_lower = message.lower().strip()
        if any(w in msg_lower for w in ["merci", "thanks", "jërëjëf"]):
            return "Avec plaisir ! N'hésitez pas si vous avez d'autres questions. 😊"
        if any(w in msg_lower for w in ["au revoir", "bonne journée", "bonne soirée", "bye"]):
            return "Au revoir et bonne continuation ! 👋"
        if any(w in msg_lower for w in ["comment ça va", "comment ca va", "ça va", "ca va", "quoi de neuf", "comment vas", "comment allez"]):
            return "Je vais bien, merci ! Comment puis-je vous aider ? 😊"
        if "bonsoir" in msg_lower:
            return "Bonsoir ! 👋 Je suis EduBot, votre assistant éducatif du Ministère de l'Éducation du Sénégal. Que puis-je faire pour vous ?"
        if "salut" in msg_lower:
            return "Salut ! 👋 Je suis EduBot. Comment puis-je vous aider aujourd'hui ?"
        return "Bonjour ! 👋 Je suis EduBot, votre assistant éducatif du Ministère de l'Éducation du Sénégal. Comment puis-je vous aider ?"

    def _get_fallback_response(self, intent: Optional[str]) -> str:
        fallbacks = {
            "inscription": "Pour les inscriptions, contactez directement l'Inspection d'Académie de votre région.",
            "examen": "Pour les examens (CFEE, BFEM, BAC), consultez le site officiel du Ministère de l'Éducation.",
            "bourse": "Pour les bourses et aides financières, rapprochez-vous du service des bourses de votre académie.",
            "calendrier": "Le calendrier scolaire est fixé par le Ministère de l'Éducation. La rentrée a lieu en octobre.",
            "orientation": "Pour l'orientation, consultez le conseiller de votre établissement ou l'Inspection d'Académie.",
            "administratif": "Pour les démarches administratives, adressez-vous au secrétariat de votre établissement.",
            "planete": "Connectez-vous sur https://planete3.education.sn avec votre e-mail professionnel (prenom.nom@education.sn).",
            "mirador": "Pour MIRADOR, contactez le service RH de votre Inspection d'Académie.",
            "connexion": "Utilisez votre e-mail professionnel (prenom.nom@education.sn). En cas d'oubli, contactez votre administrateur local.",
            "general": (
                "Je rencontre actuellement une difficulté technique pour répondre à votre question. "
                "Vous pouvez réessayer dans quelques instants, ou reformuler votre question autrement. "
                "Si le problème persiste, contactez le support EduBot au +221 77 696 15 45."
            ),
        }
        # Fallback exercice explicite
        if intent == "exercice":
            return (
                "Je serais ravi de vous proposer des exercices ! Pourriez-vous me préciser le niveau "
                "scolaire (CI, CP, CE1, CE2, CM1, CM2, 6ème, 5ème, 4ème, 3ème, 2nde, 1ère, Terminale) "
                "et la matière souhaitée (mathématiques, français, sciences, histoire-géographie…) ?"
            )
        return fallbacks.get(intent, fallbacks["general"])
