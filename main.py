"""Interface CLI de synchronisation, sélection et export ModelScope."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from src.budget import simulate_fleet_budget
from src.exporter import export_opencode_config
from src.fetcher import sync_models_from_openrouter
from src.selector import AgentRequirement, Model, SelectionResult, resolve_model_for_agent

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="ModelScope - Attribution automatique de modèles LLM pour agents OpenCode.")
    parser.add_argument("--sync", action="store_true", help="Synchronise le catalogue OpenRouter avec backup.")
    parser.add_argument("--no-fallback", action="store_true", help="Désactive le surclassement automatique.")
    parser.add_argument("--export", nargs="?", const="config/opencode.json", help="Exporte la configuration OpenCode (chemin facultatif).")
    return parser


def _load_json(path: Path, label: str) -> dict[str, object]:
    """Charge un objet JSON et contextualise les erreurs de lecture."""
    try:
        with path.open(encoding="utf-8") as file:
            data: object = json.load(file)
    except FileNotFoundError as error:
        raise ValueError(f"{label} introuvable : {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} invalide ({path}) : JSON mal formé à la ligne {error.lineno}.") from error
    except OSError as error:
        raise ValueError(f"Lecture impossible de {label} ({path}) : {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{label} invalide ({path}) : un objet JSON est attendu.")
    return data


def load_data(models_path: Path, agents_path: Path) -> tuple[list[Model], list[AgentRequirement]]:
    """Charge et valide les catalogues de modèles et d'agents."""
    models_document = _load_json(models_path, "Catalogue de modèles")
    agents_document = _load_json(agents_path, "Configuration des agents")
    raw_models = models_document.get("models", [])
    raw_agents = agents_document.get("agents", [])
    if not isinstance(raw_models, list):
        raise ValueError(f"Catalogue de modèles invalide ({models_path}) : 'models' doit être une liste.")
    if not isinstance(raw_agents, list):
        raise ValueError(f"Configuration des agents invalide ({agents_path}) : 'agents' doit être une liste.")
    try:
        models = [Model.from_dict(item, f"modèle #{index}") for index, item in enumerate(raw_models, start=1) if isinstance(item, dict)]
        if len(models) != len(raw_models):
            raise ValueError("un modèle doit être un objet JSON")
        agents = [AgentRequirement.from_dict(item, f"agent #{index}") for index, item in enumerate(raw_agents, start=1) if isinstance(item, dict)]
        if len(agents) != len(raw_agents):
            raise ValueError("un agent doit être un objet JSON")
    except ValueError as error:
        raise ValueError(f"Configuration invalide : {error}") from error
    return models, agents


def render_results(results: Sequence[SelectionResult], agents: Sequence[AgentRequirement]) -> None:
    """Affiche les attributions et la simulation budgétaire."""
    print(f"\n🤖 Configuration des agents ({len(agents)}) :\n")
    for agent, result in zip(agents, results):
        print("-" * 75)
        print(f"Agent : {agent.name} — {agent.description}")
        if result.model:
            status = "FALLBACK / SURCLASSEMENT" if result.is_fallback else "EXACT"
            print(f"  Statut      : [{status}] {result.reason}")
            print(f"  Modèle retenu : {result.model.id}")
        else:
            print(f"  Aucun modèle compatible : {result.reason}")
    budget = simulate_fleet_budget(results, agents)
    print("-" * 75)
    print(f"💰 Coût mensuel total estimé : ${budget.total_monthly_cost:.4f}")
    print(f"📊 Volume total estimé : {budget.total_tokens:,} tokens/mois")


def run(args: argparse.Namespace, base_dir: Path = BASE_DIR) -> int:
    """Exécute le flux CLI et renvoie un code de sortie POSIX."""
    models_path = base_dir / "data" / "models.json"
    agents_path = base_dir / "config" / "agents_requirements.json"
    if args.sync or not models_path.exists():
        print("🔄 Synchronisation du catalogue depuis OpenRouter...")
        try:
            count, backup = sync_models_from_openrouter(models_path)
        except Exception as error:  # Les erreurs réseau et de stockage sont externes.
            LOGGER.error("Échec de synchronisation : %s", error)
            print(f"❌ Échec de la synchronisation : {error}", file=sys.stderr)
            return 1
        print(f"✅ {count} modèles synchronisés avec succès dans {models_path}")
        if backup:
            print(f"💾 Sauvegarde précédente archivée : {backup}")
    try:
        models, agents = load_data(models_path, agents_path)
    except ValueError as error:
        LOGGER.error("Erreur de chargement : %s", error)
        print(f"❌ {error}", file=sys.stderr)
        return 2
    results = [resolve_model_for_agent(agent, models, allow_fallback=not args.no_fallback) for agent in agents]
    render_results(results, agents)
    if args.export:
        target = Path(args.export)
        target = target if target.is_absolute() else base_dir / target
        exported = export_opencode_config(results, agents, target)
        print(f"🚀 Configuration OpenCode exportée avec succès : {exported}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée CLI testable ; renvoie 0 en cas de succès."""
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
