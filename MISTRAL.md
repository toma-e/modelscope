# Directives pour Mistral AI / Codestral 🤖

Ce fichier configure les agents et outils Mistral (Codestral CLI, Le Chat, Mistral Vibe) pour intervenir sur le projet **ModelScope**.

## Règle d'or
Avant de proposer un commit ou de modifier le code :
```bash
python3 -m unittest discover tests
```
Tous les tests doivent être au vert.

## Commandes d'exécution
- **Attribution des modèles :** `python3 main.py`
- **Export vers OpenCode :** `python3 main.py --export`
- **Synchronisation catalogue :** `python3 main.py --sync`
- **Interface web locale :** `python3 main.py --serve`

## Principes d'architecture
1. **`src/selector.py` :** Fonctions pures uniquement (pas de réseau ni de lecture de fichier).
2. **Typage strict :** Dataclasses immuables (`dataclass(frozen=True)`) et typage exhaustif (`typing`).
3. **Sauvegardes obligatoires :** Toujours archiver `data/models.json` dans `data/backups/` avant écriture.
4. **Langue :** Docstrings et explications en français.

Consultez également [AGENTS.md](file:///home/thomas/code/projets/ModelScope-Anti/modelscope-Anti/AGENTS.md) pour la vue d'ensemble du projet.
