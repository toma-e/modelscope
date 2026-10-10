"""Tests unitaires pour le module de synchronisation et de backup fetcher.py."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from src.fetcher import (
    create_backup,
    estimate_complexity_score,
    fetch_openrouter_models,
    parse_openrouter_model,
    prune_timestamped_backups,
    write_json_atomic,
)


class TestFetcher(unittest.TestCase):
    def test_estimate_complexity_score(self) -> None:
        self.assertEqual(estimate_complexity_score("anthropic/claude-3-5-sonnet", 3.0), 5)
        self.assertEqual(estimate_complexity_score("deepseek/deepseek-r1", 0.55), 5)
        self.assertEqual(estimate_complexity_score("meta-llama/llama-3.3-70b-instruct", 0.12), 4)
        self.assertEqual(estimate_complexity_score("mistralai/mistral-large-2407", 2.0), 4)
        self.assertEqual(estimate_complexity_score("google/gemini-2.5-flash", 0.0), 3)
        self.assertEqual(estimate_complexity_score("google/gemini-2.5-flash-lite", 0.0), 2)
        self.assertEqual(estimate_complexity_score("meta-llama/llama-3.2-1b-instruct", 0.0), 1)
        self.assertEqual(estimate_complexity_score("google/gemma-4-31b-it", 0.0), 3)
        self.assertEqual(estimate_complexity_score("qwen/qwen3.6-35b-a3b", 0.0), 4)
        self.assertEqual(estimate_complexity_score("microsoft/wizardlm-2-8x22b", 0.0), 4)
        self.assertEqual(estimate_complexity_score("openai/o4-mini", 0.0), 5)
        self.assertEqual(estimate_complexity_score("openai/o4-mini-high", 0.0), 5)

    @patch("src.fetcher.urllib.request.urlopen", side_effect=URLError("timeout"))
    def test_fetch_openrouter_models_propagates_network_error(self, mocked_urlopen: object) -> None:
        """Une erreur réseau n'est pas transformée en catalogue vide."""
        with self.assertRaises(URLError):
            fetch_openrouter_models(timeout=1)

    def test_parse_openrouter_model_valid(self) -> None:
        raw = {
            "id": "anthropic/claude-3-5-sonnet",
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            "context_length": 200000,
            "supported_parameters": ["tools", "temperature"],
        }
        model = parse_openrouter_model(raw)
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.id, "anthropic/claude-3-5-sonnet")
        self.assertEqual(model.provider, "anthropic")
        self.assertEqual(model.cost_input_per_m, 3.0)
        self.assertEqual(model.cost_output_per_m, 15.0)
        self.assertTrue(model.supports_tools)
        self.assertEqual(model.tier, "pay_as_you_go")
        self.assertEqual(model.complexity_score, 5)

    def test_parse_openrouter_model_free(self) -> None:
        raw = {
            "id": "google/gemma-3-12b-it:free",
            "pricing": {"prompt": "0.0", "completion": "0.0"},
            "context_length": 131072,
            "supported_parameters": ["tools"],
        }
        model = parse_openrouter_model(raw)
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.tier, "free_tier")
        self.assertEqual(model.cost_input_per_m, 0.0)

    def test_parse_openrouter_model_negative_price_filtered(self) -> None:
        raw = {
            "id": "dummy/router",
            "pricing": {"prompt": "-1.0", "completion": "-1.0"},
            "context_length": 4096,
        }
        self.assertIsNone(parse_openrouter_model(raw))

    def test_create_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            target = tmp_path / "models.json"
            target.write_text(json.dumps({"test": "data"}), encoding="utf-8")

            bkp_timestamp, bkp_bak = create_backup(target)

            self.assertIsNotNone(bkp_timestamp)
            self.assertIsNotNone(bkp_bak)
            assert bkp_timestamp is not None
            assert bkp_bak is not None
            self.assertTrue(bkp_timestamp.exists())
            self.assertTrue(bkp_bak.exists())
            self.assertEqual(bkp_timestamp.read_text(encoding="utf-8"), json.dumps({"test": "data"}))
            self.assertEqual(bkp_bak.read_text(encoding="utf-8"), json.dumps({"test": "data"}))

    def test_write_json_atomic_replaces_target_without_leaving_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "models.json"
            target.write_text("{}", encoding="utf-8")
            write_json_atomic(target, {"ok": True, "count": 2})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"ok": True, "count": 2})
            self.assertEqual(list(Path(tmp_dir).glob("*.tmp")), [])

    def test_write_json_atomic_preserves_previous_file_when_dump_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "models.json"
            target.write_text(json.dumps({"keep": True}), encoding="utf-8")
            with patch("src.fetcher.json.dump", side_effect=OSError("disque plein")):
                with self.assertRaises(OSError):
                    write_json_atomic(target, {"keep": False})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"keep": True})

    def test_prune_timestamped_backups_keeps_newest_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            backup_dir = Path(tmp_dir) / "backups"
            backup_dir.mkdir()
            for day in range(5):
                (backup_dir / f"models_2026010{day}_000000.json").write_text("{}", encoding="utf-8")
            prune_timestamped_backups(backup_dir, "models", ".json", keep=3)
            remaining = sorted(path.name for path in backup_dir.iterdir())
            self.assertEqual(
                remaining,
                [
                    "models_20260102_000000.json",
                    "models_20260103_000000.json",
                    "models_20260104_000000.json",
                ],
            )


if __name__ == "__main__":
    unittest.main()
