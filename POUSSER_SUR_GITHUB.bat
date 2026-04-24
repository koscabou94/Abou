@echo off
chcp 65001 >nul
echo ============================================
echo   EduBot Senegal - Envoi du code sur GitHub
echo ============================================
echo.

cd /d "C:\Users\hp\Desktop\delussil\edu-chatbot"

echo [1/4] Suppression de l'ancien depot Git...
rmdir /s /q .git 2>nul

echo [2/4] Initialisation Git...
git init
git config user.email "koscabou94@gmail.com"
git config user.name "koscabou94"

echo [3/4] Ajout de tous les fichiers...
git add .
git commit -m "EduBot Senegal - Groq + TF-IDF + Supabase + Render"

echo [4/4] Envoi vers GitHub...
git remote add origin https://github.com/koscabou94/Abou.git
git branch -M main
git push -u origin main --force

echo.
echo ============================================
echo TERMINE ! Render va redeployer automatiquement.
echo Surveille les logs sur render.com
echo ============================================
pause
