"""Module de sélection et de filtrage des modèles LLM pour les agents.

Ce module fournit les structures de données typées et la logique pure
pour attribuer et classer les modèles selon les exigences d'un agent,
avec gestion de la fenêtre de contexte, des filtres de fournisseurs,
des modèles imposés et du surclassement (fallback).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Union


@dataclass(frozen=True)
class Model:
    """Représentation d'un modèle LLM disponible dans le catalogue."""

    id: str
    provider: str
    tier: str
    cost_input_per_m: float
    cost_output_per_m: float
    context_window: int
    supports_tools: bool
    complexity_score: int

    @property
    def is_free(self) -> bool:
        """Indique si le modèle appartient au niveau gratuit."""
        return self.tier == "free_tier" or (
            self.cost_input_per_m == 0.0 and self.cost_output_per_m == 0.0
        )

    @property
    def total_cost_per_m(self) -> float:
        """Somme des coûts d'entrée et de sortie par million de tokens."""
        return self.cost_input_per_m + self.cost_output_per_m

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Model:
        """Instancie un Model depuis un dictionnaire."""
        return cls(
            id=str(data["id"]),
            provider=str(data["provider"]),
            tier=str(data["tier"]),
            cost_input_per_m=float(data["cost_input_per_m"]),
            cost_output_per_m=float(data["cost_output_per_m"]),
            context_window=int(data["context_window"]),
            supports_tools=bool(data["supports_tools"]),
            complexity_score=int(data["complexity_score"]),
        )


@dataclass(frozen=True)
class AgentRequirement:
    """Spécification des besoins techniques et de coût d'un agent."""

    name: str
    description: str
    min_complexity: int
    max_complexity: int
    requires_tools: bool
    prefer_free: bool
    min_context_window: Optional[int] = None
    allowed_providers: Optional[List[str]] = None
    excluded_providers: Optional[List[str]] = None
    force_model: Optional[str] = None
    estimated_tokens_input: int = 0
    estimated_tokens_output: int = 0
    max_monthly_budget: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRequirement:
        """Instancie un AgentRequirement depuis un dictionnaire."""
        allowed = data.get("allowed_providers")
        if allowed is not None:
            allowed = [str(p) for p in allowed]

        excluded = data.get("excluded_providers")
        if excluded is not None:
            excluded = [str(p) for p in excluded]

        min_ctx = data.get("min_context_window")
        if min_ctx is not None:
            min_ctx = int(min_ctx)

        force = data.get("force_model")
        if force is not None:
            force = str(force)

        in_tokens = int(data.get("estimated_tokens_input", 0))
        out_tokens = int(data.get("estimated_tokens_output", 0))

        max_budget = data.get("max_monthly_budget")
        if max_budget is not None:
            max_budget = float(max_budget)

        return cls(
            name=str(data["name"]),
            description=str(data.get("description", "")),
            min_complexity=int(data["min_complexity"]),
            max_complexity=int(data["max_complexity"]),
            requires_tools=bool(data["requires_tools"]),
            prefer_free=bool(data.get("prefer_free", False)),
            min_context_window=min_ctx,
            allowed_providers=allowed,
            excluded_providers=excluded,
            force_model=force,
            estimated_tokens_input=in_tokens,
            estimated_tokens_output=out_tokens,
            max_monthly_budget=max_budget,
        )


@dataclass(frozen=True)
class SelectionResult:
    """Résultat détaillé de l'attribution d'un modèle à un agent."""

    agent_name: str
    model: Optional[Model]
    is_fallback: bool
    candidates: List[Model]
    reason: str


def check_common_constraints(model: Model, agent_req: AgentRequirement) -> bool:
    """Vérifie les contraintes transversales : outils, contexte, fournisseurs autorisés/exclus et budget."""
    # 1. Support des outils
    if agent_req.requires_tools and not model.supports_tools:
        return False

    # 2. Fenêtre de contexte minimale
    if agent_req.min_context_window is not None:
        if model.context_window < agent_req.min_context_window:
            return False

    # 3. Fournisseurs autorisés
    if agent_req.allowed_providers:
        allowed = {p.lower() for p in agent_req.allowed_providers}
        if model.provider.lower() not in allowed:
            return False

    # 4. Fournisseurs exclus
    if agent_req.excluded_providers:
        excluded = {p.lower() for p in agent_req.excluded_providers}
        if model.provider.lower() in excluded:
            return False

    # 5. Plafond budgétaire mensuel
    if agent_req.max_monthly_budget is not None and (
        agent_req.estimated_tokens_input > 0 or agent_req.estimated_tokens_output > 0
    ):
        monthly_cost = (
            (agent_req.estimated_tokens_input / 1_000_000) * model.cost_input_per_m
            + (agent_req.estimated_tokens_output / 1_000_000) * model.cost_output_per_m
        )
        if monthly_cost > agent_req.max_monthly_budget:
            return False

    return True


def is_model_compatible(model: Model, agent_req: AgentRequirement) -> bool:
    """Vérifie si un modèle respecte strictement les contraintes d'un agent."""
    if not check_common_constraints(model, agent_req):
        return False

    return agent_req.min_complexity <= model.complexity_score <= agent_req.max_complexity


def is_model_fallback_compatible(model: Model, agent_req: AgentRequirement) -> bool:
    """Vérifie si un modèle est éligible pour un surclassement (fallback).

    Un modèle est éligible en surclassement si :
    - Il respecte toutes les contraintes transversales (outils, contexte, providers).
    - Son score de complexité est supérieur à max_complexity (surqualifié mais capable).
    """
    if not check_common_constraints(model, agent_req):
        return False

    return model.complexity_score > agent_req.max_complexity


def rank_models_for_agent(
    agent_req: Union[AgentRequirement, dict[str, Any]],
    models: Sequence[Union[Model, dict[str, Any]]],
    allow_fallback: bool = False,
) -> List[Model]:
    """Classe les modèles éligibles pour un agent selon ses préférences.

    Règles de priorité :
    1. Modèles strictement compatibles en premier.
    2. Si aucun modèle compatible et allow_fallback=True : modèles surqualifiés les plus économiques.
    3. Si `prefer_free` est True, priorité absolue aux modèles `free_tier`.
    4. Coût total (entrée + sortie) le plus faible.
    5. Complexité la plus adaptée (plus proche du besoin).
    """
    req = agent_req if isinstance(agent_req, AgentRequirement) else AgentRequirement.from_dict(agent_req)
    parsed_models = [m if isinstance(m, Model) else Model.from_dict(m) for m in models]

    compatible = [m for m in parsed_models if is_model_compatible(m, req)]

    def sorting_key_exact(model: Model) -> tuple[int, float, int]:
        free_penalty = 0 if (req.prefer_free and model.tier == "free_tier") else (1 if req.prefer_free else 0)
        cost = model.total_cost_per_m
        complexity_inverted = -model.complexity_score
        return (free_penalty, cost, complexity_inverted)

    if compatible:
        return sorted(compatible, key=sorting_key_exact)

    if not allow_fallback:
        return []

    # Recherche de fallback (surclassement)
    fallbacks = [m for m in parsed_models if is_model_fallback_compatible(m, req)]

    def sorting_key_fallback(model: Model) -> tuple[int, float, int]:
        free_penalty = 0 if (req.prefer_free and model.tier == "free_tier") else (1 if req.prefer_free else 0)
        cost = model.total_cost_per_m
        complexity_gap = model.complexity_score - req.max_complexity
        return (free_penalty, cost, complexity_gap)

    return sorted(fallbacks, key=sorting_key_fallback)


def resolve_model_for_agent(
    agent_req: Union[AgentRequirement, dict[str, Any]],
    models: Sequence[Union[Model, dict[str, Any]]],
    allow_fallback: bool = True,
) -> SelectionResult:
    """Effectue une analyse complète et attribue le modèle optimal avec détails.

    Gère le forçage manuel (force_model), la correspondance exacte et le surclassement.
    """
    req = agent_req if isinstance(agent_req, AgentRequirement) else AgentRequirement.from_dict(agent_req)
    parsed_models = [m if isinstance(m, Model) else Model.from_dict(m) for m in models]

    # 0. Gestion du modèle imposé manuellement (force_model)
    if req.force_model:
        matching = [m for m in parsed_models if m.id == req.force_model]
        if matching:
            return SelectionResult(
                agent_name=req.name,
                model=matching[0],
                is_fallback=False,
                candidates=matching,
                reason=f"Modèle imposé manuellement ({req.force_model}).",
            )
        return SelectionResult(
            agent_name=req.name,
            model=None,
            is_fallback=False,
            candidates=[],
            reason=f"Modèle imposé '{req.force_model}' introuvable dans le catalogue.",
        )

    # 1. Correspondance exacte
    exact_candidates = rank_models_for_agent(req, parsed_models, allow_fallback=False)
    if exact_candidates:
        return SelectionResult(
            agent_name=req.name,
            model=exact_candidates[0],
            is_fallback=False,
            candidates=exact_candidates,
            reason="Correspondance exacte avec les exigences.",
        )

    # 2. Surclassement automatique (fallback) si autorisé
    if allow_fallback:
        fallback_candidates = rank_models_for_agent(req, parsed_models, allow_fallback=True)
        if fallback_candidates:
            chosen = fallback_candidates[0]
            reason = (
                f"Surclassement automatique (fallback) : aucun modèle dans la plage "
                f"[{req.min_complexity}-{req.max_complexity}], modèle de complexité "
                f"{chosen.complexity_score} sélectionné pour sa rentabilité."
            )
            return SelectionResult(
                agent_name=req.name,
                model=chosen,
                is_fallback=True,
                candidates=fallback_candidates,
                reason=reason,
            )

    return SelectionResult(
        agent_name=req.name,
        model=None,
        is_fallback=False,
        candidates=[],
        reason="Aucun modèle compatible trouvé respectant les contraintes.",
    )


def select_model_for_agent(
    agent_req: Union[AgentRequirement, dict[str, Any]],
    models: Sequence[Union[Model, dict[str, Any]]],
    allow_fallback: bool = True,
) -> Optional[Model]:
    """Sélectionne le meilleur modèle pour un agent donné."""
    result = resolve_model_for_agent(agent_req, models, allow_fallback=allow_fallback)
    return result.model
