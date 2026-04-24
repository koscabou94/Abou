@echo off
chcp 65001 > nul
title DPTIC - Assistant Educatif
color 0A

echo.
echo  =====================================================
echo    DPTIC - ASSISTANT EDUCATIF
echo    Ministere de l'Education Nationale du Senegal
echo  =====================================================
echo.

cd /d "%~dp0"

set "PYEXE=C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe"
set "OLLAMA=C:\Users\hp\AppData\Local\Programs\Ollama\ollama.exe"

REM -- DEMARRER OLLAMA --
echo  Demarrage d'Ollama...
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if %errorlevel%==0 (
    echo  Ollama deja lance.
) else (
    start "" "%OLLAMA%" serve
    echo  Ollama demarre. Attente 5 secondes...
    timeout /t 5 /nobreak >nul
)
echo.

REM -- OUVRIR LE NAVIGATEUR DANS 10 SECONDES --
start "" cmd /c "timeout /t 10 /nobreak >nul && start http://127.0.0.1:8000"

REM -- LANCER LE CHATBOT --
echo  =====================================================
echo    Lancement du chatbot sur http://127.0.0.1:8000
echo    Le navigateur va s'ouvrir dans 10 secondes.
echo    Pour arreter : fermez cette fenetre.
echo  =====================================================
echo.

cd /d "%~dp0backend"
"%PYEXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

echo.
echo  Le serveur s'est arrete.
pause
