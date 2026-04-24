@echo off
chcp 65001 > nul
title DPTIC - Nettoyage et Relancement
color 0A

echo.
echo  =====================================================
echo    NETTOYAGE ET RELANCEMENT DU CHATBOT DPTIC
echo  =====================================================
echo.
echo  Cette operation va :
echo    1. Supprimer les anciens fichiers inutiles
echo    2. Reinitialiser la base de donnees FAQ
echo    3. Relancer le chatbot avec les nouvelles FAQ
echo.
echo  Appuyez sur une touche pour continuer...
pause > nul

cd /d "%~dp0"

REM -- SUPPRIMER LES FICHIERS INUTILES --
echo.
echo  Nettoyage des fichiers inutiles...
if exist "LANCER_CHATBOT.bat"     del /f /q "LANCER_CHATBOT.bat"
if exist "REINITIALISER_FAQ.ps1"  del /f /q "REINITIALISER_FAQ.ps1"
if exist "start_server.bat"       del /f /q "start_server.bat"
if exist "run_server.ps1"         del /f /q "run_server.ps1"
if exist "None"                   del /f /q "None"
if exist "list[dict]"             del /f /q "list[dict]"
if exist "max_chars"              del /f /q "max_chars"
if exist "str"                    del /f /q "str"
if exist "test_out.txt"           del /f /q "test_out.txt"
if exist "server.log"             del /f /q "server.log"
if exist "data\faq_senegal_backup2.json" del /f /q "data\faq_senegal_backup2.json"
echo  Nettoyage termine.

REM -- SUPPRIMER LA BASE DE DONNEES --
echo.
echo  Suppression de l'ancienne base de donnees FAQ...
if exist "backend\edu_chatbot.db" del /f /q "backend\edu_chatbot.db"
echo  Base supprimee.

REM -- LANCER OLLAMA --
echo.
set "OLLAMA=C:\Users\hp\AppData\Local\Programs\Ollama\ollama.exe"
echo  Demarrage d'Ollama...
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if %errorlevel%==0 (
    echo  Ollama deja lance.
) else (
    start "" "%OLLAMA%" serve
    echo  Ollama demarre. Attente 5 secondes...
    timeout /t 5 /nobreak >nul
)

REM -- OUVRIR LE NAVIGATEUR --
start "" cmd /c "timeout /t 15 /nobreak >nul && start http://127.0.0.1:8000"

REM -- LANCER LE CHATBOT --
echo.
echo  =====================================================
echo    Lancement du chatbot sur http://127.0.0.1:8000
echo    Le navigateur s'ouvre dans 15 secondes.
echo    PATIENTEZ : la 1ere fois prend 1-2 minutes
echo    (chargement des modeles d'IA)
echo    Pour arreter : fermez cette fenetre.
echo  =====================================================
echo.

set "PYEXE=C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe"
cd /d "%~dp0backend"
"%PYEXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

echo.
echo  Le serveur s'est arrete.
pause
