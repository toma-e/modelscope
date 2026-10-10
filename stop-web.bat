@echo off
REM Arrete le serveur ModelScope en cours d'execution dans WSL

echo ========================================
echo Arret du serveur ModelScope
echo ========================================
echo.

echo Recherche des processus Python en cours...
wsl bash -c "pkill -f 'python3 main.py --serve'"

if errorlevel 1 (
    echo [INFO] Aucun processus serveur trouve ou deja arrete
) else (
    echo [OK] Serveur arrete avec succes
)

echo.
echo Verification...
wsl bash -c "ps aux | grep 'python3 main.py --serve' | grep -v grep"
if errorlevel 1 (
    echo [OK] Aucun processus serveur en cours d'execution
) else (
    echo [AVERTISSEMENT] Des processus sont encore actifs
)

echo.
pause
