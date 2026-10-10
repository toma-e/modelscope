#!/bin/bash
echo "========================================"
echo "ModelScope - Interface Web Locale"
echo "========================================"
echo ""
cd ""/bin"
echo "[1/2] Demarrage du serveur..."
python3 main.py --serve 8765 &
SERVER_PID=
echo "[2/2] Attente du demarrage du serveur..."
sleep 3
if curl -s http://127.0.0.1:8765/ > /dev/null 2>&1; then
    echo "OK Serveur demarre avec succes"
else
    echo "AVERTISSEMENT Le serveur ne repond pas encore"
fi
echo ""
echo "========================================"
echo "Serveur lance sur http://127.0.0.1:8765/"
echo "PID du serveur: "
echo "========================================"
echo ""
echo "Pour arreter le serveur, appuyez sur Ctrl+C ou executez:"
echo "  kill "
echo ""
tail -f /tmp/modelscope-web.log 2>/dev/null || echo "Aucun fichier de log disponible"
wait 
