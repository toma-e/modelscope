@echo off
REM Lanceur pour l'interface web ModelScope
REM Ce script lance le serveur dans WSL et ouvre le navigateur Windows

echo ========================================
echo ModelScope - Interface Web Locale
echo ========================================
echo.

REM Lancer le serveur dans WSL en arriere-plan
echo [1/2] Demarrage du serveur dans WSL...
wsl bash -c "cd /home/thomas/code/projets/ModelScope-Anti/modelscope-Anti && python3 main.py --serve 8765 > /tmp/modelscope-web.log 2>&1 &"
if errorlevel 1 (
    echo [ERREUR] Impossible de lancer le serveur WSL
    pause
    exit /b 1
)

REM Attendre que le serveur soit pret
echo [2/2] Attente du demarrage du serveur...
timeout /t 3 /nobreak >nul

REM Ouvrir le navigateur
echo Ouverture du navigateur...
start http://127.0.0.1:8765/

echo.
echo ========================================
echo Serveur lance sur http://127.0.0.1:8765/
echo Pour arreter le serveur, fermez cette fenetre ou utilisez Ctrl+C
echo ========================================
echo.
echo Logs disponibles dans WSL: /tmp/modelscope-web.log
echo.

REM Garder la fenetre ouverte pour que le serveur continue de tourner
wsl bash -c "tail -f /tmp/modelscope-web.log"
