@echo off
REM ==============================================================
REM  EduBot v10.8 - Integration FAQ_PLANETE3 + bot intelligent
REM ==============================================================
REM
REM Cette version apporte :
REM   1. PlaneteFAQService : nouveau service FAQ dedie a PLANETE,
REM      branche EN TETE du pipeline. Charge FAQ_PLANETE3.json
REM      (61 questions, 13 categories) avec recherche TF-IDF +
REM      synonymes + fuzzy matching + lexique metier.
REM   2. Detection PLANETE implicite : le bot comprend que des
REM      questions comme "comment configurer l'environnement
REM      physique" parlent de PLANETE meme sans le mot "PLANETE".
REM   3. Synonymes et reformulations : "comment se connecter" =
REM      "comment me connecter" = "comment devrais-je faire pour
REM      me connecter" = "comment je peux me loguer".
REM   4. Tolerance aux fautes de frappe (rapidfuzz).
REM   5. Cache LRU des reponses LLM (200 entrees) pour economiser
REM      le quota Groq sur les questions frequentes.
REM   6. Robustesse Groq : retry exponentiel + bascule auto modele
REM      rapide en cas d'echec du modele principal.
REM   7. Memoire de session : suivi de la derniere intention pour
REM      resoudre les references implicites ("et une salle ?"
REM      apres avoir parle d'un batiment).
REM
REM ==============================================================

cd /d "%~dp0"

echo ============================================================
echo  EduBot v10.8 - Integration FAQ_PLANETE3 + intelligence
echo ============================================================
echo.

git add backend/app/services/planete_faq_service.py
git add backend/app/services/__init__.py
git add backend/app/services/chat_service.py
git add backend/app/services/nlp_service.py
git add backend/app/services/faq_service.py
git add backend/app/main.py
git add backend/requirements.txt
git add data/FAQ_PLANETE3.json
git add POUSSER_V10.8_PLANETE_FAQ.bat

echo.
echo --- Statut Git ---
git status --short

echo.
echo --- Commit ---
git commit -m "v10.8: integration FAQ_PLANETE3 + bot intelligent (priorite PLANETE, synonymes, fuzzy, cache, robustesse, precision Q1/Q2, normalisation PLANETE 3 -> PLANETE sauf Q3/Q4)"

echo.
echo --- Push ---
git push origin main

echo.
echo ============================================================
echo  Push termine. Render va redeployer dans ~5 minutes.
echo  Apres deploiement, faire Ctrl+Shift+R sur l'URL du bot.
echo ============================================================
echo.
pause
