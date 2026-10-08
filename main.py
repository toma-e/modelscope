"""Point d'entrée principal pour ModelScope.

Permet de charger les modèles, d'exécuter l'attribution automatique pour les agents,
et propose l'option --sync pour mettre à jour le catalogue depuis l'API OpenRouter avec backup.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

from src.fetcher import sync_models_from_openrouter
from src.selector import (
    AgentRequirement,
    Model,
    resolve_model_for_agent,
)


def load_data(
    models_path: Path, agents_path: Path
) -> Tuple[List[Model], List[AgentRequirement]]:
    """Charge et parse les fichiers JSON de configuration."""
    with open(models_path, "r", encoding="utf-8") as f:
        models_raw = json.load(f).get("models", [])
        models = [Model.from_dict(m) for m in models_raw]

    with open(agents_path, "r", encoding="utf-8") as f:
        agents_raw = json.load(f).get("agents", [])
        agents = [AgentRequirement.from_dict(a) for a in agents_raw]

    return models, agents


def main() -> None:
    """Exécute l'attribution automatique pour chaque agent et gère les options CLI."""
    parser = argparse.ArgumentParser(
        description="ModelScope - Attribution automatique de modèles LLM pour agents OpenCode."
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Synchronise le catalogue de modèles depuis l'API publique OpenRouter avec création d'un backup.",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Désactive le surclassement économique automatique si aucun modèle exact n'est trouvé.",
    )

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    models_path = base_dir / "data" / "models.json"
    agents_path = base_dir / "config" / "agents_requirements.json"

    print("=" * 75)
    print("🎯 ModelScope - Attribution automatique de modèles LLM")
    print("=" * 75)

    # Synchronisation si demandée ou si le catalogue n'existe pas encore
    if args.sync or not models_path.exists():
        print("🔄 Synchronisation du catalogue depuis OpenRouter...")
        try:
            count, bkp = sync_models_from_openrouter(models_path)
            print(f"✅ {count} modèles synchronisés avec succès dans {models_path}")
            if bkp:
                print(f"💾 Sauvegarde précédente archivée : {bkp}")
        except Exception as err:
            print(f"❌ Échec de la synchronisation : {err}")
            if not models_path.exists():
                sys.exit(1)

    models, agents = load_data(models_path, agents_path)

    # Statistiques du catalogue
    free_count = sum(1 for m in models if m.is_free)
    tools_count = sum(1 for m in models if m.supports_tools)
    providers = sorted({m.provider for m in models})

    print(f"\n📦 Catalogue de modèles ({len(models)} au total) :")
    print(f"   - Modèles gratuits (free_tier) : {free_count}")
    print(f"   - Supportant les outils (tools) : {tools_count}")
    print(f"   - Fournisseurs ({len(providers)}) : {', '.join(providers[:6])}...")

    print(f"\n🤖 Configuration des agents ({len(agents)}) :\n")

    allow_fallback = not args.no_fallback

    for agent in agents:
        print("-" * 75)
        print(f"Agent : \033[1m{agent.name}\033[0m — {agent.description}")
        print(
            f"  Exigences   : Complexité [{agent.min_complexity} - {agent.max_complexity}] | "
            f"Tools: {agent.requires_tools} | Prefer free: {agent.prefer_free}"
        )

        result = resolve_model_for_agent(agent, models, allow_fallback=allow_fallback)

        if result.model:
            status_tag = (
                "\033[33m[FALLBACK / SURCLASSEMENT]\033[0m"
                if result.is_fallback
                else "\033[32m[EXACT]\033[0m"
            )
            print(f"  Statut      : {status_tag} {result.reason}")
            print(f"  ✅ \033[1mModèle retenu : {result.model.id}\033[0m")
            print(
                f"     Fournisseur: {result.model.provider} | Tier: {result.model.tier} | "
                f"Complexité: {result.model.complexity_score} | Coût total/1M: ${result.model.total_cost_per_m:.2f}"
            )
            if len(result.candidates) > 1:
                top_alts = [m.id for m in result.candidates[1:6]]
                more_count = len(result.candidates) - 6
                suffix = f" (+ {more_count} autres)" if more_count > 0 else ""
                print(f"     Alternatives éligibles : {', '.join(top_alts)}{suffix}")
        else:
            print(f"  ❌ \033[31mAucun modèle compatible :\033[0m {result.reason}")

    print("-" * 75)
    print("\n✨ Attribution terminée.")


if __name__ == "__main__":
    main()
