"""Module d'export de la configuration pour les agents OpenCode.

Ce module transforme les résultats de sélection de modèles en un format
de configuration standardisé et exploitable par l'environnement OpenCode,
avec inclusion de la simulation budgétaire prévisionnelle.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.budget import simulate_fleet_budget
from src.selector import AgentRequirement, SelectionResult


@dataclass(frozen=True)
class OpenCodeModelConfig:
    """Configuration du modèle attribué à un agent OpenCode."""

    id: str
    provider: str
    tier: str
    context_window: int
    supports_tools: bool
    cost_input_per_m: float
    cost_output_per_m: float
    total_cost_per_m: float


@dataclass(frozen=True)
class OpenCodeAgentConfig:
    """Configuration complète d'un agent OpenCode."""

    name: str
    description: str
    enabled: bool
    requires_tools: bool
    min_context_window: Optional[int]
    allowed_providers: Optional[List[str]]
    max_monthly_budget: Optional[float]
    estimated_monthly_cost: float
    model: Optional[OpenCodeModelConfig]
    selection_status: str
    selection_reason: str


def build_opencode_config(
    results: Sequence[SelectionResult],
    agents: Sequence[AgentRequirement],
) -> Dict[str, Any]:
    """Construit le dictionnaire de configuration pour OpenCode.

    Args:
        results: Résultats de la sélection pour chaque agent.
        agents: Exigences initiales des agents.

    Returns:
        Dictionnaire au format OpenCode contenant les agents configurés,
        les métadonnées et la simulation budgétaire consolidée.
    """
    agents_by_name = {a.name: a for a in agents}
    fleet_budget = simulate_fleet_budget(results, agents)
    budget_by_agent = {r.agent_name: r for r in fleet_budget.agent_reports}

    configured_agents: Dict[str, Dict[str, Any]] = {}
    assigned_count = 0
    unassigned_count = 0

    for res in results:
        agent_req = agents_by_name.get(res.agent_name)
        description = agent_req.description if agent_req else ""
        requires_tools = agent_req.requires_tools if agent_req else False
        min_context = agent_req.min_context_window if agent_req else None
        allowed_providers = agent_req.allowed_providers if agent_req else None
        max_budget = agent_req.max_monthly_budget if agent_req else None

        agent_budget = budget_by_agent.get(res.agent_name)
        monthly_cost = agent_budget.monthly_total_cost if agent_budget else 0.0

        if res.model:
            assigned_count += 1
            status_str = "fallback" if res.is_fallback else "exact"
            model_conf = OpenCodeModelConfig(
                id=res.model.id,
                provider=res.model.provider,
                tier=res.model.tier,
                context_window=res.model.context_window,
                supports_tools=res.model.supports_tools,
                cost_input_per_m=res.model.cost_input_per_m,
                cost_output_per_m=res.model.cost_output_per_m,
                total_cost_per_m=res.model.total_cost_per_m,
            )
            agent_conf = OpenCodeAgentConfig(
                name=res.agent_name,
                description=description,
                enabled=True,
                requires_tools=requires_tools,
                min_context_window=min_context,
                allowed_providers=allowed_providers,
                max_monthly_budget=max_budget,
                estimated_monthly_cost=monthly_cost,
                model=model_conf,
                selection_status=status_str,
                selection_reason=res.reason,
            )
        else:
            unassigned_count += 1
            agent_conf = OpenCodeAgentConfig(
                name=res.agent_name,
                description=description,
                enabled=False,
                requires_tools=requires_tools,
                min_context_window=min_context,
                allowed_providers=allowed_providers,
                max_monthly_budget=max_budget,
                estimated_monthly_cost=0.0,
                model=None,
                selection_status="unassigned",
                selection_reason=res.reason,
            )

        configured_agents[res.agent_name] = asdict(agent_conf)

    budget_summary = {
        "total_estimated_monthly_cost": fleet_budget.total_monthly_cost,
        "total_estimated_tokens": fleet_budget.total_tokens,
        "estimated_free_tier_savings": fleet_budget.free_tier_savings,
        "has_warnings": fleet_budget.has_budget_warnings,
        "reports": [
            {
                "agent": r.agent_name,
                "monthly_cost": r.monthly_total_cost,
                "input_cost": r.monthly_input_cost,
                "output_cost": r.monthly_output_cost,
                "max_budget": r.max_budget,
                "budget_exceeded": r.budget_exceeded,
                "quota_warning": r.quota_warning,
            }
            for r in fleet_budget.agent_reports
        ],
    }

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "generator": "ModelScope",
            "total_agents": len(results),
            "assigned_agents": assigned_count,
            "unassigned_agents": unassigned_count,
        },
        "budget_simulation": budget_summary,
        "agents": configured_agents,
    }


def export_opencode_config(
    results: Sequence[SelectionResult],
    agents: Sequence[AgentRequirement],
    output_path: Path,
) -> Path:
    """Génère et sauvegarde le fichier de configuration JSON pour OpenCode.

    Args:
        results: Résultats de la sélection des modèles.
        agents: Exigences initiales des agents.
        output_path: Fichier de destination (ex: config/opencode.json).

    Returns:
        Chemin absolu du fichier écrit.
    """
    config_data = build_opencode_config(results, agents)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

    return output_path.resolve()
