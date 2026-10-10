# Directives pour GitHub Copilot & OpenAI Codex 🤖

Ce fichier configure GitHub Copilot et OpenAI Codex pour le projet **ModelScope**.

## Règle d'or
Avant de proposer un commit ou de valider du code :
```bash
python3 -m unittest discover tests
```
Tous les tests doivent obligatoirement réussir.

## Principes d'architecture
1. **`src/selector.py` est strictement pur :** Aucune lecture de fichier, aucun appel réseau, aucun HTTP, aucune modification d'état global. Le CLI et le web passent par `src/service.py`.
2. **Typage strict et immuable :** Utiliser `dataclass(frozen=True)` et les types complets de `typing`.
3. **Sauvegardes automatiques :** Toute mise à jour de `data/models.json` via `src/fetcher.py` doit d'abord appeler `create_backup()`.
4. **Documentation en français :** Les docstrings et commentaires doivent être rédigés en français.

## Documentation de référence
Pour plus de détails sur le flux de données, les responsabilités des modules et la roadmap, consultez :
- [AGENTS.md](file:///home/thomas/code/projets/ModelScope-Anti/modelscope-Anti/AGENTS.md)
- [.cursorrules](file:///home/thomas/code/projets/ModelScope-Anti/modelscope-Anti/.cursorrules)
