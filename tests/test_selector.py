"""Tests unitaires pour le module selector."""

import unittest

from src.selector import (
    AgentRequirement,
    Model,
    is_model_compatible,
    is_model_fallback_compatible,
    rank_models_for_agent,
    resolve_model_for_agent,
    select_model_for_agent,
)


class TestSelector(unittest.TestCase):
    def setUp(self) -> None:
        self.llama_1b = Model(
            id="meta-llama/llama-3.2-1b-instruct",
            provider="meta",
            tier="free_tier",
            cost_input_per_m=0.0,
            cost_output_per_m=0.0,
            context_window=8192,
            supports_tools=False,
            complexity_score=1,
        )
        self.gemini_lite = Model(
            id="google/gemini-2.5-flash-lite",
            provider="google",
            tier="free_tier",
            cost_input_per_m=0.0,
            cost_output_per_m=0.0,
            context_window=1000000,
            supports_tools=True,
            complexity_score=2,
        )
        self.gpt_4o_mini = Model(
            id="openai/gpt-4o-mini",
            provider="openai",
            tier="pay_as_you_go",
            cost_input_per_m=0.15,
            cost_output_per_m=0.60,
            context_window=128000,
            supports_tools=True,
            complexity_score=2,
        )
        self.gemini_flash = Model(
            id="google/gemini-2.5-flash",
            provider="google",
            tier="free_tier",
            cost_input_per_m=0.0,
            cost_output_per_m=0.0,
            context_window=1000000,
            supports_tools=True,
            complexity_score=3,
        )
        self.llama_70b = Model(
            id="meta-llama/llama-3.3-70b-instruct",
            provider="meta",
            tier="pay_as_you_go",
            cost_input_per_m=0.12,
            cost_output_per_m=0.30,
            context_window=128000,
            supports_tools=True,
            complexity_score=4,
        )
        self.claude_sonnet = Model(
            id="anthropic/claude-3-5-sonnet",
            provider="anthropic",
            tier="pay_as_you_go",
            cost_input_per_m=3.0,
            cost_output_per_m=15.0,
            context_window=200000,
            supports_tools=True,
            complexity_score=5,
        )
        self.models = [
            self.llama_1b,
            self.gemini_lite,
            self.gpt_4o_mini,
            self.gemini_flash,
            self.llama_70b,
            self.claude_sonnet,
        ]

    def test_compatibility_tool_support(self) -> None:
        req = AgentRequirement(
            name="coder",
            description="",
            min_complexity=1,
            max_complexity=2,
            requires_tools=True,
            prefer_free=False,
        )
        self.assertFalse(is_model_compatible(self.llama_1b, req))
        self.assertTrue(is_model_compatible(self.gemini_lite, req))

    def test_doc_agent_selection(self) -> None:
        """doc_agent (complexité 1-2, prefer_free) doit choisir gemini-2.5-flash-lite."""
        req = AgentRequirement(
            name="doc_agent",
            description="",
            min_complexity=1,
            max_complexity=2,
            requires_tools=False,
            prefer_free=True,
        )
        selected = select_model_for_agent(req, self.models)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "google/gemini-2.5-flash-lite")

    def test_coder_agent_selection(self) -> None:
        """coder_agent (complexité 3-4, requires_tools, prefer_free) doit choisir gemini-flash."""
        req = AgentRequirement(
            name="coder_agent",
            description="",
            min_complexity=3,
            max_complexity=4,
            requires_tools=True,
            prefer_free=True,
        )
        selected = select_model_for_agent(req, self.models)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "google/gemini-2.5-flash")

    def test_fallback_when_no_exact_match(self) -> None:
        """Si aucun modèle ne satisfait la plage stricte, le fallback surclasse vers le modèle économique."""
        req = AgentRequirement(
            name="strict_agent",
            description="",
            min_complexity=1,
            max_complexity=1,
            requires_tools=True,
            prefer_free=True,
        )
        # Sans fallback -> None
        result_no_fallback = resolve_model_for_agent(req, self.models, allow_fallback=False)
        self.assertIsNone(result_no_fallback.model)
        self.assertFalse(result_no_fallback.is_fallback)

        # Avec fallback -> surclassement vers gemini_lite (score 2, free, tools=True)
        result_fallback = resolve_model_for_agent(req, self.models, allow_fallback=True)
        self.assertIsNotNone(result_fallback.model)
        self.assertTrue(result_fallback.is_fallback)
        self.assertEqual(result_fallback.model.id, "google/gemini-2.5-flash-lite")

    def test_architect_agent_selection(self) -> None:
        """architect_agent (complexité 5) doit choisir claude-3-5-sonnet."""
        req = AgentRequirement(
            name="architect_agent",
            description="",
            min_complexity=5,
            max_complexity=5,
            requires_tools=True,
            prefer_free=False,
        )
        selected = select_model_for_agent(req, self.models)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "anthropic/claude-3-5-sonnet")

    def test_min_context_window_filter(self) -> None:
        """Exclut les modèles ayant une fenêtre de contexte inférieure au seuil."""
        # Pour une complexité 2, gemini_lite a 1M et gpt_4o_mini a 128k
        req = AgentRequirement(
            name="big_doc_agent",
            description="",
            min_complexity=2,
            max_complexity=2,
            requires_tools=False,
            prefer_free=False,
            min_context_window=500000,
        )
        selected = select_model_for_agent(req, self.models)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "google/gemini-2.5-flash-lite")

    def test_allowed_providers_filter(self) -> None:
        """Ne retient que les modèles appartenant aux fournisseurs autorisés."""
        req = AgentRequirement(
            name="openai_only_agent",
            description="",
            min_complexity=2,
            max_complexity=2,
            requires_tools=True,
            prefer_free=False,
            allowed_providers=["openai"],
        )
        selected = select_model_for_agent(req, self.models)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "openai/gpt-4o-mini")

    def test_excluded_providers_filter(self) -> None:
        """Exclut explicitement certains fournisseurs."""
        req = AgentRequirement(
            name="no_google_agent",
            description="",
            min_complexity=2,
            max_complexity=2,
            requires_tools=True,
            prefer_free=False,
            excluded_providers=["google"],
        )
        selected = select_model_for_agent(req, self.models)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "openai/gpt-4o-mini")

    def test_force_model_override(self) -> None:
        """Un modèle imposé manuellement doit être sélectionné en priorité absolue."""
        req = AgentRequirement(
            name="forced_agent",
            description="",
            min_complexity=1,
            max_complexity=1,
            requires_tools=False,
            prefer_free=False,
            force_model="anthropic/claude-3-5-sonnet",
        )
        result = resolve_model_for_agent(req, self.models)
        self.assertIsNotNone(result.model)
        self.assertEqual(result.model.id, "anthropic/claude-3-5-sonnet")
        self.assertIn("imposé manuellement", result.reason)

    def test_force_model_not_found(self) -> None:
        """Un modèle imposé inexistant retourne None avec un motif clair."""
        req = AgentRequirement(
            name="forced_unknown_agent",
            description="",
            min_complexity=1,
            max_complexity=1,
            requires_tools=False,
            prefer_free=False,
            force_model="provider/unknown-model",
        )
        result = resolve_model_for_agent(req, self.models)
        self.assertIsNone(result.model)
    def test_max_monthly_budget_filter(self) -> None:
        """Exclut les modèles dont le coût estimé dépasse le budget maximal autorisé."""
        # Pour complexité 2 :
        # gpt_4o_mini coûte in: $0.15/1M, out: $0.60/1M.
        # Avec 2M in et 1M out -> coût = $0.30 + $0.60 = $0.90.
        # Si budget max est $0.50 et prefer_free est False :
        # gpt_4o_mini ($0.90) est rejeté, mais gemini_lite ($0.00) est compatible !
        req = AgentRequirement(
            name="capped_budget_agent",
            description="",
            min_complexity=2,
            max_complexity=2,
            requires_tools=True,
            prefer_free=False,
            estimated_tokens_input=2_000_000,
            estimated_tokens_output=1_000_000,
            max_monthly_budget=0.50,
        )
        selected = select_model_for_agent(req, self.models)
        self.assertIsNotNone(selected)
        # Seul gemini_lite respecte le budget max
        self.assertEqual(selected.id, "google/gemini-2.5-flash-lite")


if __name__ == "__main__":
    unittest.main()

