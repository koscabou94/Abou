# EduBot — Documentation Complète du Projet
**Ministère de l'Éducation Nationale du Sénégal**
Mise à jour : 24 avril 2026

---

## ⭐ INSTRUCTIONS POUR LA PROCHAINE SESSION CLAUDE

> **Abou n'a pas de compétences en codage. Claude doit tout faire à sa place.**
> Commencer directement par lire ce fichier, puis enchaîner les tâches dans l'ordre ci-dessous.

### Contexte de reprise
- Projet EduBot v=9 est **déployé et fonctionnel** sur https://educonnect-w7tr.onrender.com
- Dernière chose faite (v9) : PDF réel jsPDF + questions de clarification avec boutons + fix bug exercice fallback + mobile amélioré
- Script de déploiement v9 : `POUSSER_PDF_PROFESSIONNEL.bat`

### Tâches à faire dans la prochaine session (dans cet ordre)

#### ✅ TÂCHE 1 — PDF professionnel téléchargeable (vrais fichiers .pdf) — TERMINÉE v9
**Ce qui a été fait :**
- jsPDF + html2canvas intégrés via CDN dans `frontend/index.html`
- `window.downloadPDF()` dans `frontend/chat.js` génère un vrai fichier `.pdf` téléchargeable
- Entête : drapeau sénégalais, titre, date
- Pied de page : EduBot · educonnect-w7tr.onrender.com
- Questions de clarification avec boutons cliquables (niveau, matière)
- Fix bug réponses vides pour intent "exercice"
- Versions CSS/JS en v=9
- Script `POUSSER_PDF_PROFESSIONNEL.bat` créé

#### TÂCHE 2 — Sujets BAC et BFEM téléchargeables
**Ce qu'il faut faire :**
- Créer le fichier `data/examens_data.json` avec des sujets types BAC/BFEM par matière et série
- Ajouter les sujets dans la knowledge base (knowledge_service.py)
- Ajouter les mots-clés "sujet bac", "sujet bfem", "épreuve", "annales" dans INTENT_RULES
- Quand un élève demande un sujet, le bot le fournit et propose le PDF téléchargeable
- Exemple de questions à tester : "Donne-moi le sujet du BAC maths série S", "Je cherche des annales de BFEM français"

#### TÂCHE 3 — Distinguer enseignants et élèves (authentification légère)
**Ce qu'il faut faire :**
- Ajouter un écran de sélection au démarrage : "Je suis un **Élève**" / "Je suis un **Enseignant**" / "Je suis un **Parent**"
- Adapter les cartes d'accueil rapide selon le profil choisi
- Stocker le profil dans localStorage
- Enseignants → cartes axées fiches pédagogiques, MIRADOR, carrière
- Élèves → cartes axées exercices, examens, PLANETE
- Parents → cartes axées inscription, orientation, bourse

#### TÂCHE 4 — Migration vers serveurs du Ministère
**Ce qu'il faut faire :**
- Créer un guide de déploiement pas-à-pas sur serveur Linux Ubuntu
- Créer les scripts shell d'installation automatique
- Créer la configuration Nginx (reverse proxy + SSL)
- Créer le fichier docker-compose.yml de production
- Documenter les étapes pour la DSI du Ministère

#### TÂCHE 5 — Enrichissement de la base de connaissances
**Ce qu'il faut faire :**
- Enrichir `data/faq_data.json` avec les procédures administratives par direction du Ministère
- Ajouter les programmes officiels du Sénégal par matière et niveau dans `data/knowledge_base/`
- Intégrer les circulaires et notes de service courantes

### Fichiers importants
- Code : `C:\Users\hp\Desktop\delussil\edu-chatbot`
- Version actuelle : CSS v=9, JS v=9
- Script push dernier : `POUSSER_PDF_PROFESSIONNEL.bat`
- Ce fichier de doc : `DOCUMENTATION_PROJET.md`

### Comment démarrer la session
Dire à Claude : *"Lis le fichier DOCUMENTATION_PROJET.md dans C:\Users\hp\Desktop\delussil\edu-chatbot et commence la TÂCHE 1"*

---

## 1. Vue d'ensemble

| Élément | Valeur |
|---|---|
| Nom du bot | **EduBot** |
| URL de production | https://educonnect-w7tr.onrender.com |
| Hébergement | Render.com (free tier, Docker) |
| Dépôt GitHub | koscabou94/Abou (branche `main`) |
| Dossier local | `C:\Users\hp\Desktop\delussil\edu-chatbot` |
| Contact support | +221 77 696 15 45 (WhatsApp) |
| Email | abou.ndiathe@education.sn |

**Rôle :** Assistant éducatif IA pour les élèves, parents et enseignants du Sénégal. Répond aux questions sur PLANETE 3.0, MIRADOR, les examens (CFEE, BFEM, BAC), les carrières enseignantes, et génère des exercices et fiches pédagogiques.

---

## 2. Architecture technique

```
┌─────────────────────────────────────────────────────┐
│                    DOCKER (Render.com)               │
│                                                     │
│  ┌──────────────┐      ┌────────────────────────┐  │
│  │   Frontend   │      │   Backend (FastAPI)    │  │
│  │  HTML/CSS/JS │◄────►│   Port 8000            │  │
│  │  (Lucide,    │      │   Async + SQLAlchemy   │  │
│  │   marked.js) │      └────────────┬───────────┘  │
│  └──────────────┘                   │               │
│                          ┌──────────┼──────────┐   │
│                          ▼          ▼           ▼   │
│                       Groq AI   Jina AI    Supabase │
│                      (LLM)   (Embeddings) (PostgreSQL│
│                   llama-3.3   jina-v3      ⚠️ ENOTF) │
│                   -70b-vers.  512 dims    JSON fallback│
└─────────────────────────────────────────────────────┘
```

### Stack complète

| Couche | Technologie |
|---|---|
| Framework backend | FastAPI + Uvicorn |
| ORM | SQLAlchemy (async) + asyncpg |
| Base de données | Supabase PostgreSQL (⚠️ ENOTFOUND depuis Render) |
| Fallback données | 168 FAQs JSON (toujours actif) |
| LLM | Groq API — `llama-3.3-70b-versatile` |
| Embeddings sémantiques | Jina AI — `jina-embeddings-v3` (512 dims, 1M tokens/mois gratuit) |
| Recherche fallback | TF-IDF (scikit-learn) |
| Rate limiting | SlowAPI |
| Logging | structlog |
| Frontend | HTML/CSS/JS vanilla |
| Markdown rendu | marked.js |
| Icônes | Lucide (unpkg CDN) |
| Polices | Google Fonts — Outfit (titres) + Inter (corps) |
| Déploiement | Docker → Render.com (auto-deploy via GitHub push) |

---

## 3. Structure des fichiers

```
edu-chatbot/
├── frontend/
│   ├── index.html          ← Interface principale (v=8)
│   ├── styles.css          ← Tous les styles (thème clair/sombre)
│   └── chat.js             ← Logique client (v=8)
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                  ← Point d'entrée FastAPI
│       ├── config.py                ← Variables d'environnement (pydantic-settings)
│       ├── database/
│       │   ├── connection.py        ← Pool asyncpg + create_tables()
│       │   └── models.py            ← Modèles SQLAlchemy (FAQ, Conversation, Message)
│       ├── routes/
│       │   ├── chat.py              ← POST /api/chat, GET /api/chat/history/{id}
│       │   ├── faq.py               ← CRUD FAQ (admin)
│       │   └── admin.py             ← Endpoints d'administration
│       └── services/
│           ├── nlp_service.py       ← LLM Groq + classification d'intention
│           ├── faq_service.py       ← Recherche FAQ (Jina + TF-IDF)
│           ├── knowledge_service.py ← Base de connaissances (Jina + TF-IDF)
│           ├── embedding_service.py ← Jina AI embeddings (nouveau)
│           ├── chat_service.py      ← Orchestration (FAQ → KB → LLM)
│           ├── language_service.py  ← Détection de langue
│           └── translation_service.py ← Traduction (wolof, pulaar, arabe → français)
│
├── data/
│   └── faq_data.json        ← 168 FAQs (fallback si DB inaccessible)
│
├── DOCUMENTATION_PROJET.md  ← Ce fichier
├── POUSSER_MOBILE_PDF.bat   ← ⭐ Script push le plus récent (v=8)
├── POUSSER_UI_CARTES.bat
├── POUSSER_FORMAT_EXERCICES.bat
└── ... (autres scripts .bat)
```

---

## 4. Variables d'environnement (Render.com)

À configurer dans **Render → Environment** :

| Variable | Valeur / Description |
|---|---|
| `GROQ_API_KEY` | Clé API Groq (https://console.groq.com) |
| `JINA_API_KEY` | Clé API Jina AI (https://jina.ai) — optionnel, TF-IDF si vide |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:6543/db?ssl=require&statement_cache_size=0` |
| `SECRET_KEY` | Clé secrète JWT |
| `API_KEY` | Clé admin API |
| `DEBUG` | `false` en production |
| `USE_LIGHTWEIGHT_MODE` | `true` (désactive Redis) |

### Paramètres clés dans config.py
```python
MAX_TOKENS = 1500          # Longueur max réponses LLM
TEMPERATURE = 0.3          # Créativité LLM (0=déterministe)
CONTEXT_WINDOW = 5         # Nb d'échanges mémorisés
FAQ_MATCH_THRESHOLD = 0.30
FAQ_HIGH_CONFIDENCE_THRESHOLD = 0.55
LLM_MODEL = "llama-3.3-70b-versatile"
```

---

## 5. Flux de traitement d'une question

```
Utilisateur envoie une question
        ↓
1. Détection de langue (LanguageService)
   → Si wolof/pulaar/arabe → traduction vers français
        ↓
2. Classification d'intention (NLPService.classify_intent)
   → salutation | inscription | examen | exercice | fiche | planete | mirador | ...
        ↓
3. Si intention = salutation → réponse directe (pas de LLM)
        ↓
4. Si "general knowledge" (capitale, président...) → bypass FAQ → direct LLM
        ↓
5. Recherche FAQ (FAQService.find_best_match)
   → Jina AI embedding (sémantique, seuil 0.45) si clé disponible
   → TF-IDF fallback (seuil 0.30)
   → Si score > 0.55 → réponse FAQ directe (pas de LLM)
        ↓
6. Recherche base de connaissances (KnowledgeService.get_context_for_llm)
   → Top 2 documents, max 1000 chars de contexte
        ↓
7. Génération LLM (NLPService.generate_response via Groq)
   → System prompt + contexte KB + historique (5 derniers échanges)
   → Si exercice/fiche → génération libre sans limite de phrases
   → Autres intents → "(Réponds de façon concise et directe)"
        ↓
8. Streaming simulé côté frontend (mot par mot, délai 8ms)
        ↓
9. Sauvegarde en DB (non-bloquant, erreur ignorée si DB inaccessible)
```

---

## 6. Service NLP — Intents reconnus

| Intent | Exemples de déclencheurs |
|---|---|
| `salutation` | bonjour, salut, merci, au revoir, ça va |
| `inscription` | inscri, dossier, formulaire, matricule |
| `calendrier` | date, rentrée, vacances, trimestre |
| `examen` | bfem, bac, cfee, résultat, épreuve |
| `orientation` | filière, après le bac, que faire |
| `bourse` | bourse, aide financière, allocation |
| `programme` | programme, matière, curriculum |
| `administratif` | attestation, relevé, IEF, légalisation |
| `enseignant` | prof, FASTEF, CRFPE, recrutement |
| `planete` | planete 3.0, bulletin, nomade, BST |
| `mirador` | mirador, mutation, solde, fiche de paie |
| `exercice` | exercice, maths, remédiation, CM2, 6ème… |
| `fiche` (via exercice) | fiche pédagogique, fiche de cours, plan de leçon, séance |

---

## 7. Formats de réponse spéciaux

### Format exercices (obligatoire dans le prompt)
```markdown
### 📚 Exercices de Mathématiques — CM2

---

### ✏️ Exercice 1 — Calcul

Moussa a 1 250 FCFA. Il achète 3 cahiers à 350 FCFA chacun...

---

### ✏️ Exercice 2 — Problème

Un agriculteur récolte 48 kg de mil par jour...
```

### Format fiche pédagogique (obligatoire dans le prompt)
```markdown
### 📋 Fiche Pédagogique — [Matière] — [Niveau]

**Discipline :** ...   **Niveau :** ...   **Durée :** 45 min
**Compétence visée :** ...

---

### 🎯 Objectifs spécifiques
1. ...

---

### 📚 Contenu / Notions clés
...

---

### 🏫 Déroulement de la séance
| Phase | Activités du maître | Activités des élèves | Durée |
|-------|---------------------|----------------------|-------|
| Introduction | ... | ... | 5 min |

---

### ✅ Évaluation formative
...
```

---

## 8. Frontend — Fonctionnalités clés

### chat.js (v=8) — Fonctions importantes
| Fonction | Rôle |
|---|---|
| `sendMessage()` | Envoie la question, affiche réponse en streaming |
| `appendBotMessageStreaming()` | Animation mot-par-mot (8ms/mot) |
| `goHome()` | Retour écran d'accueil, reset session |
| `window.copyMessage(btn)` | Copie le texte du message |
| `window.downloadPDF(btn)` | Ouvre fenêtre print avec entête Ministère |
| `toggleSidebar()` | Ouvre/ferme la sidebar (mobile overlay) |
| `applyTheme()` | Bascule thème clair/sombre |
| `renderHistory()` | Affiche l'historique dans la sidebar |

### Cartes d'accueil rapide (quickQs)
```javascript
{ text: "Donne-moi 3 exercices de maths niveau CM2" },
{ text: "Exercices de remédiation en français pour la 6ème" },
{ text: "C'est quoi PLANETE 3.0 ?" },
{ text: "Comment avancer dans ma carrière d'enseignant ?" }
```

### PDF Download — window.downloadPDF()
Ouvre une fenêtre d'impression avec :
- Drapeau sénégalais (vert / jaune ★ / rouge)
- Entête : "EduBot — Ministère de l'Éducation Nationale"
- Date du jour en français
- Contenu HTML du message formaté
- Tableau CSS pour les fiches pédagogiques
- Pied de page avec URL du site

---

## 9. Versions CSS/JS (cache busting)

| Fichier | Version actuelle |
|---|---|
| `styles.css` | `?v=8` |
| `chat.js` | `?v=8` |

À incrémenter dans `index.html` à chaque déploiement important.

---

## 10. Problème Supabase (non bloquant)

**Symptôme :** `ENOTFOUND` au démarrage sur Render.com free tier.

**Cause :** Render free tier bloque les connexions sortantes vers Supabase (DNS non résolu).

**Solution actuelle :** Fallback automatique sur `data/faq_data.json` (168 FAQs). Le bot fonctionne normalement, mais les conversations ne sont pas sauvegardées en base.

**Fix possible (non urgent) :**
- Passer à Render Starter (payant) → connexions DB autorisées
- Ou utiliser Railway.app / Fly.io qui permettent les connexions DB sur free tier

---

## 11. Scripts de déploiement (.bat)

| Script | Usage |
|---|---|
| `POUSSER_MOBILE_PDF.bat` | ⭐ **Dernier en date** — Mobile fix + PDF + Fiches (v=8) |
| `POUSSER_UI_CARTES.bat` | Cartes sans icônes ni sous-titres (v=7) |
| `POUSSER_FORMAT_EXERCICES.bat` | Format exercices séparés (v=6) |
| `POUSSER_RAG_EMBEDDINGS.bat` | Jina AI RAG sémantique |
| `POUSSER_INTELLIGENCE_BOT.bat` | Amélioration IA + faits 2026 |
| `POUSSER_FRONTEND_FIX.bat` | Correction chemins CSS/JS |

Tous les scripts font :
1. Nettoyer les verrous git (`.git/index.lock`, `.git/HEAD.lock`)
2. `git add` des fichiers modifiés
3. `git commit -m "..."`
4. `git push origin main`

Après push → attendre **~5 minutes** sur Render puis `Ctrl+Shift+R` sur le navigateur.

---

## 12. Historique des versions et corrections

| Version | Changement |
|---|---|
| v1–2 | Mise en place initiale FastAPI + frontend |
| v3 | Fix CSS/JS 404 (`/static/...` → `/...`) |
| v4 | Bouton "Retour à l'accueil" + responsive mobile/tablette |
| v5 | Fix mauvaise réponse FAQ (capitale Sénégal) + faits 2026 (Diomaye Faye) |
| v5 | RAG Jina AI embeddings (remplace TF-IDF seul) |
| v6 | Génération exercices scolaires + format séparateurs `---` |
| v7 | Cartes accueil simplifiées (texte seulement, sans icônes ni sous-titres) |
| **v8** | **Fix mobile (Accueil cliquable iPhone) + PDF download + Fiches pédagogiques** |
| **v9** | **PDF réel jsPDF/html2canvas + Questions de clarification (boutons choix) + Fix exercice fallback + Mobile amélioré** |

---

## 13. Faits actuels dans le prompt (2026)

```
- Nous sommes en 2026
- Président : Bassirou Diomaye Faye (élu mars 2024, 1er tour)
- Premier Ministre : Ousmane Sonko (nommé mars 2024)
- Capitale : Dakar | Monnaie : FCFA | Langue officielle : Français
```

---

## 14. Pour reprendre le travail dans une nouvelle fenêtre

**Dire à Claude :**
> "Je travaille sur EduBot, le chatbot éducatif du Ministère de l'Éducation du Sénégal. Le code est dans `C:\Users\hp\Desktop\delussil\edu-chatbot`. Nous sommes à la version v=8. Voici le fichier de documentation : [joindre DOCUMENTATION_PROJET.md]"

**Prochaines améliorations possibles :**
- Corriger la connexion Supabase (passer à Railway ou Render payant)
- Ajouter la langue wolof au frontend (bouton WO dans la nav)
- Ajouter un historique de conversations persistent (actuellement localStorage uniquement)
- Améliorer le PDF : utiliser jsPDF pour un vrai fichier .pdf téléchargeable (pas juste impression)
- Ajouter des images/schémas dans les fiches pédagogiques
- Système d'authentification pour les enseignants

---

*Document généré par EduBot · Ministère de l'Éducation Nationale du Sénégal · 24 avril 2026*
