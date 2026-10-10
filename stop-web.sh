#!/bin/bash
echo "========================================"
echo "Arret du serveur ModelScope"
echo "========================================"
echo ""
echo "Recherche des processus Python en cours..."
pkill -f "python3 main.py --serve"
if [ 0 -ne 0 ]; then
    echo "INFO Aucun processus serveur trouve ou deja arrete"
else
    echo "OK Serveur arrete avec succes"
fi
echo ""
echo "Verification..."
if ps aux | grep "python3 main.py --serve" | grep -v grep > /dev/null; then
    echo "AVERTISSEMENT Des processus sont encore actifs:"
    ps aux | grep "python3 main.py --serve" | grep -v grep
else
    echo "OK Aucun processus serveur en cours d'execution"
fi
echo ""
