@echo off
chcp 65001 > nul
cd /d "%~dp0"

set "LOG=%~dp0diagnostic.log"

echo ====== DIAGNOSTIC DPTIC ====== > "%LOG%"
echo Date : %date% %time% >> "%LOG%"
echo. >> "%LOG%"

echo --- PYTHON --- >> "%LOG%"
where python >> "%LOG%" 2>&1
echo. >> "%LOG%"

python --version >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- PYTHON 312 --- >> "%LOG%"
if exist "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" (
    echo Python312 EXISTE >> "%LOG%"
    "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" --version >> "%LOG%" 2>&1
) else (
    echo Python312 PAS TROUVE >> "%LOG%"
)
echo. >> "%LOG%"

echo --- PYTHON 314 --- >> "%LOG%"
if exist "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe" (
    echo Python314 EXISTE >> "%LOG%"
    "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe" --version >> "%LOG%" 2>&1
) else (
    echo Python314 PAS TROUVE >> "%LOG%"
)
echo. >> "%LOG%"

echo --- UVICORN --- >> "%LOG%"
python -c "import uvicorn; print('uvicorn OK')" >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- FASTAPI --- >> "%LOG%"
python -c "import fastapi; print('fastapi OK')" >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- OLLAMA --- >> "%LOG%"
where ollama >> "%LOG%" 2>&1
ollama --version >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- OLLAMA MODELS --- >> "%LOG%"
ollama list >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- TEST LANCEMENT BACKEND --- >> "%LOG%"
cd /d "%~dp0backend"
python -c "from app.config import settings; print('Config OK, mode:', 'LIGHT' if settings.USE_LIGHTWEIGHT_MODE else 'NORMAL')" >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo ====== FIN DIAGNOSTIC ====== >> "%LOG%"

echo Diagnostic termine. Le fichier diagnostic.log a ete cree.
echo Vous pouvez fermer cette fenetre.
pause
