# Lanceurs pour l'Interface Web Locale

Ce dossier contient des scripts pour demarrer et arreter facilement l'interface web locale de ModelScope.

## Windows (via WSL)

### Demarrer le serveur

**Option 1: Script PowerShell (recommande)**
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

PS Microsoft.PowerShell.Core\FileSystem::\wsl.localhost\Ubuntu\home\thomas\code\projets\ModelScope-Anti\modelscope-Anti> 

**Option 2: Script Batch**
Microsoft Windows [version 10.0.26300.9457]
(c) Microsoft Corporation. Tous droits rservs.

C:\Windows>

Ces scripts:
- Lancement automatique du serveur dans WSL
- Ouverture automatique du navigateur Windows sur http://127.0.0.1:8765/
- Affichage des logs en temps reel
- Le serveur continue de tourner meme apres fermeture de la fenetre

### Arreter le serveur

**Option 1: Script PowerShell (recommande)**
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

PS Microsoft.PowerShell.Core\FileSystem::\wsl.localhost\Ubuntu\home\thomas\code\projets\ModelScope-Anti\modelscope-Anti> 

**Option 2: Script Batch**
Microsoft Windows [version 10.0.26300.9457]
(c) Microsoft Corporation. Tous droits rservs.

C:\Windows>

## Linux/WSL Direct

### Demarrer le serveur
========================================
ModelScope - Interface Web Locale
========================================

### Arreter le serveur
========================================
Arret du serveur ModelScope
========================================

Recherche des processus Python en cours...
OK Serveur arrete avec succes

Verification...
OK Aucun processus serveur en cours d'execution

Ou manuellement:


## Depannage

### Le serveur ne demarre pas
- Verifiez que Python 3 est installe dans WSL: python3 --version
- Verifiez que les dependances sont installees: pip install -r requirements.txt
- Consultez les logs: wsl bash -c "cat /tmp/modelscope-web.log"

### Le navigateur ne s'ouvre pas
- Ouvrez manuellement: http://127.0.0.1:8765/
- Verifiez qu'aucun autre processus n'utilise le port 8765

### Erreur "WSL n'est pas disponible"
- Assurez-vous que WSL est installe et active sur Windows
- Redemarrez WSL: wsl --shutdown puis relancez

## Notes

- Les scripts Windows utilisent wsl bash pour executer les commandes dans WSL
- Les logs sont stockes dans /tmp/modelscope-web.log dans WSL
- Le serveur ecoute sur 127.0.0.1:8765 (localhost uniquement)
- Pour changer le port, modifiez le script et remplacez 8765 par le port souhaite
