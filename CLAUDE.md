# CLAUDE.md - Directives pour Claude Code / Agents Anthropic

Ce fichier synthétise les commandes et conventions du projet ModelScope pour une prise en main rapide.

## Commandes Canoniques

### Tests Unitaires
```bash
# Exécuter l'intégralité de la suite de tests (24 tests)
python3 -m unittest discover tests

# Exécuter un fichier de test spécifique
python3 -m unittest tests/test_selector.py
python3 -m unittest tests/test_budget.py
python3 -m unittest tests/test_fetcher.py
python3 -m unittest tests/test_exporter.py
```

### Exécution du Projet
```bash
# Attribution automatique et affichage console
python3 main.py

# Attribution avec export pour OpenCode (config/opencode.json)
python3 main.py --export

# Forcer la synchronisation des modèles OpenRouter (avec backup horodaté)
python3 main.py --sync
```

## Structure du Projet
- `src/selector.py` : Logique pure d'évaluation, filtrage et surclassement (fallback). **Zéro I/O**.
- `src/fetcher.py` : Téléchargement dynamique des modèles OpenRouter et archivage dans `data/backups/`.
- `src/budget.py` : Calculs de coûts prévisionnels mensuels et alertes de quotas free-tier.
- `src/exporter.py` : Génération du fichier de configuration standard pour OpenCode.
- `config/agents_requirements.json` : Profils de contraintes des agents.
- `data/models.json` : Catalogue actif des modèles LLM.

## Invariants Techniques
1. **Pureté :** `src/selector.py` ne doit contenir aucun appel réseau ni lecture de fichier.
2. **Typage strict :** Utiliser `dataclass(frozen=True)` et les annotations de types complètes (`typing`).
3. **Backups systématiques :** Toute écriture dans `data/models.json` via `src/fetcher.py` doit générer une sauvegarde horodatée dans `data/backups/` et un fichier `data/models.json.bak`.
4. **Documentation :** Docstrings claires rédigées en français.
5. **Tests obligatoires :** Toujours valider `python3 -m unittest discover tests` avant toute validation de code.
