# Lanceur PowerShell pour l'interface web ModelScope
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ModelScope - Interface Web Locale" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] Demarrage du serveur dans WSL..." -ForegroundColor Yellow
wsl bash -c "cd /home/thomas/code/projets/ModelScope-Anti/modelscope-Anti && python3 main.py --serve 8765 > /tmp/modelscope-web.log 2>&1 &"

Write-Host "[2/2] Attente du demarrage du serveur..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "Ouverture du navigateur..." -ForegroundColor Yellow
Start-Process "http://127.0.0.1:8765/"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Serveur lance sur http://127.0.0.1:8765/" -ForegroundColor Green
Write-Host "Pour arreter le serveur, executez: stop-web.ps1" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs disponibles dans WSL: /tmp/modelscope-web.log" -ForegroundColor Gray
Write-Host ""

Write-Host "Affichage des logs (Ctrl+C pour arreter):" -ForegroundColor Gray
wsl bash -c "tail -f /tmp/modelscope-web.log"
