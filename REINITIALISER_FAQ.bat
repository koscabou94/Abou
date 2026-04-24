@echo off
chcp 65001 > nul
title Reinitialisation FAQ - Chatbot Educatif
color 0A

echo.
echo =====================================================
echo   REINITIALISATION DE LA BASE FAQ
echo =====================================================
echo.
echo  Cette operation va supprimer et recharger
echo  toutes les FAQ avec les nouvelles entrees.
echo.
echo  Appuyez sur une touche pour continuer...
pause > nul

cd /d "%~dp0backend"

echo.
echo  Suppression de la base de donnees...
del /f /q edu_chatbot.db 2>nul
echo  Base supprimee.

echo.
echo  Reinitialisation terminee !
echo  Lancez maintenant LANCER_DPTIC.bat
echo.
pause
