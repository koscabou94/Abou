@echo off
REM ==============================================================
REM  EduBot v11 - Authentification multi-methodes + Personnalisation
REM ==============================================================
REM
REM Cette release apporte trois lots majeurs :
REM
REM   LOT 1 - 4 corrections critiques (Vague 1)
REM   ----------------------------------------
REM   1. Selecteur showSuggestions corrige (.message.bot etait
REM      jamais matche -> les suggestions de relance n'apparaissaient
REM      pas). Bascule sur .message-node.bot.
REM   2. pendingClarificationContext nettoye proprement : la
REM      concatenation ne s'applique qu'aux reponses courtes
REM      (<= 3 mots). Plus de pollution si l'utilisateur change
REM      de sujet en plein milieu d'une clarification.
REM   3. Cache LRU sensible au contexte : la cle inclut maintenant
REM      le niveau et la matiere courants pour eviter qu'un
REM      follow-up court ("continue", "plus de details") d'une
REM      session serve la reponse d'une autre session.
REM   4. Streaming optimise : re-parse markdown tous les 6 mots
REM      (au lieu de chaque mot), stripBold reduit a 1 passe.
REM      Fini le jank visible sur les longues reponses.
REM
REM   LOT 2 - UX et qualite (Vague 2)
REM   ----------------------------------------
REM   5. Deduplication _get_greeting_response (chat_service delegue
REM      desormais a nlp_service - une seule source de verite).
REM   6. Badge "Source officielle" / "Reponse IA" sous chaque
REM      reponse du bot. L'utilisateur sait immediatement si la
REM      reponse vient de FAQ_PLANETE3, FAQ MEN ou est generee.
REM   7. Boutons feedback (pouce up/down) sur chaque reponse.
REM      Persistance locale + endpoint backend /api/feedback
REM      qui logge dans data/feedback.jsonl. Endpoint stats
REM      /api/feedback/stats pour analyser le taux d'approbation
REM      par intent et par source.
REM
REM   LOT 3 - Authentification multi-methodes (Vague 3)
REM   ----------------------------------------
REM   8. Modele User etendu : auth_method, ien, email, phone,
REM      password_hash, profile_type (enseignant/eleve/parent/autre),
REM      full_name, school, level, last_login_at. Migration
REM      legere automatique au boot (compatible SQLite + Postgres).
REM   9. Service auth complet : bcrypt + JWT HS256 (7 jours)
REM      + OTP (mock 123456 en MVP) + validation IEN/email/phone
REM      + whitelist IEN locale (data/ien_whitelist.json).
REM  10. 5 endpoints d'authentification :
REM      - POST /api/auth/request-otp  : demande OTP email/SMS
REM      - POST /api/auth/login        : IEN+password ou email/tel+OTP
REM      - POST /api/auth/register     : finaliser le profil
REM      - GET  /api/auth/me           : profil courant
REM      - POST /api/auth/logout
REM      - GET  /api/auth/profiles     : meta (types + niveaux)
REM  11. Personnalisation automatique du LLM : SYSTEM_PROMPT
REM      enrichi d'un bloc CONTEXTE UTILISATEUR adapte au
REM      profil. Niveau pre-injecte si user authentifie ->
REM      plus de clarification niveau pour les eleves connectes.
REM  12. Frontend auth : modal de login a 3 onglets
REM      (IEN / Email / Telephone), modal de profil
REM      (type + nom + ecole + niveau), avatar dans la sidebar,
REM      persistance JWT en localStorage. Mode invite preserve.
REM  13. Welcome adapte : "Bonjour Fatou, ..." pour un user
REM      authentifie, suggestions d'accueil personnalisees
REM      par profil (enseignant -> fiches, eleve -> exercices,
REM      parent -> suivi).
REM
REM   COMPTES DE TEST (data/ien_whitelist.json)
REM   ------------------------------------------
REM   Mot de passe par defaut pour tous : edubot2026
REM
REM   IEN 200001 : Aminata Diop, enseignante a Dakar
REM   IEN 200002 : Mamadou Sow, enseignant a Thies
REM   IEN 300001 : Fatou Ndiaye, eleve CM2 a Dakar
REM   IEN 300002 : Ibrahima Fall, eleve Terminale a Guediawaye
REM   IEN 400001 : Aida Sarr, parent eleve CE1
REM
REM   Pour email / telephone : code OTP 123456 (mode MVP).
REM
REM   POINTS DE VIGILANCE PROD
REM   ------------------------------------------
REM   - Render free a un disque ephemere : la table users
REM     sera videe a chaque redemarrage. Brancher Postgres
REM     (Supabase gratuit) avant la mise en prod serieuse.
REM   - OTP mock 123456 a remplacer par vrai SMTP (email)
REM     ou Twilio/Orange (SMS) plus tard.
REM   - Whitelist IEN a remplacer par integration SIMEN/PLANETE.
REM
REM ==============================================================

cd /d "%~dp0"

echo ============================================================
echo  EduBot v11 - Auth multi-methodes + Personnalisation
echo ============================================================
echo.

REM --- Backend : modeles + migration ---
git add backend/app/database/models.py
git add backend/app/database/connection.py
git add backend/app/middleware/auth.py

REM --- Backend : services ---
git add backend/app/services/auth_service.py
git add backend/app/services/chat_service.py
git add backend/app/services/nlp_service.py

REM --- Backend : routes ---
git add backend/app/routes/auth.py
git add backend/app/routes/chat.py
git add backend/app/routes/feedback.py
git add backend/app/routes/__init__.py
git add backend/app/main.py

REM --- Donnees : whitelist IEN ---
git add data/ien_whitelist.json

REM --- Frontend ---
git add frontend/index.html
git add frontend/chat.js
git add frontend/styles.css

REM --- Le script lui-meme ---
git add POUSSER_V11_AUTH_PERSONNALISATION.bat

echo.
echo --- Statut Git ---
git status --short

echo.
echo --- Commit ---
git commit -m "v11: Auth multi-methodes (IEN/email/tel) + personnalisation par profil + feedback up/down + badges source + 4 fixes critiques (showSuggestions, clarification context, cache LRU, streaming throttle) + dedup salutations"

echo.
echo --- Push ---
git push origin main

echo.
echo ============================================================
echo  Push termine. Render va redeployer dans ~5 minutes.
echo.
echo  Apres deploiement, tester :
echo   1. Ctrl+Shift+R sur https://edubot-senegal.onrender.com
echo   2. Cliquer "Se connecter" dans la sidebar
echo   3. Onglet IEN : 300001 / edubot2026 -> eleve CM2
echo   4. Demander "des exercices" -> doit generer pour CM2
echo      directement, sans clarification niveau.
echo   5. Onglet Email/Tel : n'importe quoi + OTP 123456
echo      -> modal profil pour completer.
echo   6. Verifier badges "Source officielle PLANETE" / "IA"
echo      sous les reponses, et boutons pouce up/down.
echo ============================================================
echo.
pause
