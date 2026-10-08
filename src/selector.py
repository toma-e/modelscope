"""Module de sélection et de filtrage des modèles LLM pour les agents.

Ce module fournit les structures de données typées et la logique pure
pour attribuer et classer les modèles selon les exigences d'un agent,
avec gestion optionnelle du surclassement (fallback).
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRequirement:
        """Instancie un AgentRequirement depuis un dictionnaire."""
        return cls(
            name=str(data["name"]),
            description=str(data.get("description", "")),
            min_complexity=int(data["min_complexity"]),
            max_complexity=int(data["max_complexity"]),
            requires_tools=bool(data["requires_tools"]),
            prefer_free=bool(data.get("prefer_free", False)),
        )


@dataclass(frozen=True)
class SelectionResult:
    """Résultat détaillé de l'attribution d'un modèle à un agent."""

    agent_name: str
    model: Optional[Model]
    is_fallback: bool
    candidates: List[Model]
    reason: str


def is_model_compatible(model: Model, agent_req: AgentRequirement) -> bool:
    """Vérifie si un modèle respecte strictement les contraintes d'un agent.

    Critères vérifiés :
    - Si l'agent requiert des outils, le modèle doit supporter les outils.
    - Le score de complexité du modèle doit être compris entre min_complexity
      et max_complexity de l'agent (inclus).
    """
    if agent_req.requires_tools and not model.supports_tools:
        return False

    if not (agent_req.min_complexity <= model.complexity_score <= agent_req.max_complexity):
        return False

    return True


def is_model_fallback_compatible(model: Model, agent_req: AgentRequirement) -> bool:
    """Vérifie si un modèle est éligible pour un surclassement (fallback).

    Un modèle est éligible en surclassement si :
    - Il supporte les outils si requis.
    - Son score de complexité est supérieur à max_complexity (surqualifié mais capable).
    """
    if agent_req.requires_tools and not model.supports_tools:
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

    Args:
        agent_req: Exigences de l'agent (instance ou dictionnaire).
        models: Liste des modèles disponibles (instances ou dictionnaires).
        allow_fallback: Si True et qu'aucun modèle n'est dans la plage exacte,
            inclut les modèles surqualifiés.

    Returns:
        Liste triée des modèles compatibles, du plus adapté au moins adapté.
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
        # Surclassement minimal en priorité (ex: complexité 3 préférée à 5 pour un besoin max 2)
        complexity_gap = model.complexity_score - req.max_complexity
        return (free_penalty, cost, complexity_gap)

    return sorted(fallbacks, key=sorting_key_fallback)


def resolve_model_for_agent(
    agent_req: Union[AgentRequirement, dict[str, Any]],
    models: Sequence[Union[Model, dict[str, Any]]],
    allow_fallback: bool = True,
) -> SelectionResult:
    """Effectue une analyse complète et attribue le modèle optimal avec détails.

    Args:
        agent_req: Besoins de l'agent.
        models: Liste des modèles disponibles.
        allow_fallback: Autorise ou non le surclassement économique si nécessaire.

    Returns:
        SelectionResult détaillant le modèle choisi, le statut (exact ou fallback),
        la liste des candidats et le motif.
    """
    req = agent_req if isinstance(agent_req, AgentRequirement) else AgentRequirement.from_dict(agent_req)
    parsed_models = [m if isinstance(m, Model) else Model.from_dict(m) for m in models]

    # 1. Tentative de correspondance exacte
    exact_candidates = rank_models_for_agent(req, parsed_models, allow_fallback=False)
    if exact_candidates:
        return SelectionResult(
            agent_name=req.name,
            model=exact_candidates[0],
            is_fallback=False,
            candidates=exact_candidates,
            reason="Correspondance exacte avec les exigences de complexité et d'outils.",
        )

    # 2. Tentative avec surclassement (fallback) si autorisé
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
    """Sélectionne le meilleur modèle pour un agent donné.

    Args:
        agent_req: Besoins de l'agent.
        models: Liste des modèles disponibles.
        allow_fallback: Autorise le surclassement si aucun modèle n'est dans la plage exacte.

    Returns:
        Le modèle le plus adapté, ou None si aucun modèle n'est compatible.
    """
    result = resolve_model_for_agent(agent_req, models, allow_fallback=allow_fallback)
    return result.model
