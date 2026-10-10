"""Module de synchronisation et de génération du catalogue de modèles via l'API OpenRouter.

Ce module permet de :
1. Récupérer dynamiquement la liste publique des modèles OpenRouter.
2. Déduire les capacités, tarifications et scores de complexité.
3. Sauvegarder le catalogue dans data/models.json tout en créant une sauvegarde (backup)
   horodatée de la version précédente.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

from src.selector import Model

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
MAX_TIMESTAMPED_BACKUPS = 20


def estimate_complexity_score(model_id: str, prompt_cost_per_m: float) -> int:
    """Estime un score de complexité (1 à 5) basé sur l'identifiant et le tarif du modèle.

    Heuristique :
    - 5 (Expert / Raisonnement complexe) : Modèles phares (Opus, Sonnet, o1, o3, R1, 405B, GPT-4, etc.)
    - 4 (Avancé / Codeur lourd) : Modèles intermédiaires-hauts (70B, 72B, Codestral, Mistral-Large, etc.)
    - 3 (Moyen / Généraliste rapide) : Modèles légers rapides (Flash, Haiku, 8B, 14B, 32B, etc.)
    - 2 (Compact / Tâches simples) : Petits modèles (Flash-lite, 7B, 3B, Mini, Lite)
    - 1 (Ultra-léger / Embarqué) : Micro modèles (1B, 0.5B, Nano)
    """
    m_id = model_id.lower()

    # Score 5 : modèles de pointe / raisonnement approfondi
    if any(k in m_id for k in ["opus", "sonnet", "o1", "o3", "o4", "r1", "deepseek-r1", "405b", "gpt-5"]):
        return 5
    if "gpt-4" in m_id and "mini" not in m_id:
        return 5

    # Score 4 : modèles 70B+ et gros modèles open-source.
    # Les tailles sont reconnues comme des jetons complets : "1b" ne doit pas
    # capturer "31b" ou "8x22b".
    if any(k in m_id for k in ["mistral-large", "deepseek-v3", "codestral", "command-r+"]):
        return 4
    parameter_tokens = re.findall(r"(?<![a-z0-9])(?:\d+x)?(\d+(?:\.\d+)?)b(?![a-z0-9])", m_id)
    parameter_sizes = [float(token) for token in parameter_tokens]
    if re.search(r"(?<![a-z0-9])\d+x\d+(?:\.\d+)?b(?![a-z0-9])", m_id):
        return 4
    if parameter_sizes and max(parameter_sizes) >= 35:
        return 4

    # Score 1 : ultra légers
    if any(size in parameter_sizes for size in [0.5, 1.0]) or re.search(r"(?<![a-z0-9])(?:nano|micro|tiny)(?![a-z0-9])", m_id):
        return 1

    # Score 2 : petits modèles (attention à ne pas matcher 'mini' dans 'gemini')
    has_mini = bool(re.search(r"[-_/]mini([-_/:]|$)", m_id))
    if "flash-lite" in m_id or "lite" in m_id or has_mini or any(size in parameter_sizes for size in [3.0, 7.0]):
        return 2

    # Score 3 : modèles rapides intermédiaires
    if any(k in m_id for k in ["flash", "haiku", "mistral-small"]) or any(size in parameter_sizes for size in [8.0, 14.0, 31.0, 32.0]):
        return 3

    # Fallback heuristique basé sur le coût par million de tokens d'entrée
    if prompt_cost_per_m >= 2.0:
        return 5
    elif prompt_cost_per_m >= 0.5:
        return 4
    elif prompt_cost_per_m >= 0.05:
        return 3
    elif prompt_cost_per_m > 0:
        return 2
    else:
        return 3


def parse_openrouter_model(raw: dict[str, Any]) -> Optional[Model]:
    """Convertit un objet modèle brut d'OpenRouter vers la dataclass Model.

    Retourne None si le modèle est invalide (ex: prix négatifs de routage interne).
    """
    model_id = raw.get("id")
    if not model_id or not isinstance(model_id, str):
        return None

    # Extraction du fournisseur (préfixe avant le '/')
    provider = model_id.split("/")[0] if "/" in model_id else "openrouter"

    pricing = raw.get("pricing", {})
    try:
        raw_prompt = float(pricing.get("prompt", 0))
        raw_completion = float(pricing.get("completion", 0))
    except (TypeError, ValueError):
        raw_prompt, raw_completion = 0.0, 0.0

    # Filtrer les tarifs négatifs (tests / placeholders OpenRouter)
    if raw_prompt < 0 or raw_completion < 0:
        return None

    cost_in = round(raw_prompt * 1_000_000, 4)
    cost_out = round(raw_completion * 1_000_000, 4)

    is_free = ":free" in model_id or (cost_in == 0.0 and cost_out == 0.0)
    tier = "free_tier" if is_free else "pay_as_you_go"

    context_window = int(raw.get("context_length") or 4096)

    supported_params = raw.get("supported_parameters", [])
    supports_tools = "tools" in supported_params or "tool_choice" in supported_params

    complexity_score = estimate_complexity_score(model_id, cost_in)

    return Model(
        id=model_id,
        provider=provider,
        tier=tier,
        cost_input_per_m=cost_in,
        cost_output_per_m=cost_out,
        context_window=context_window,
        supports_tools=supports_tools,
        complexity_score=complexity_score,
    )


def write_json_atomic(path: Path, data: object) -> None:
    """Écrit un document JSON via un fichier temporaire puis un remplacement atomique."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def prune_timestamped_backups(
    backup_dir: Path,
    stem: str,
    suffix: str,
    keep: int = MAX_TIMESTAMPED_BACKUPS,
) -> None:
    """Conserve uniquement les sauvegardes horodatées les plus récentes."""
    if keep < 1 or not backup_dir.is_dir():
        return
    archived = sorted(
        path for path in backup_dir.glob(f"{stem}_*{suffix}") if path.is_file()
    )
    excess = len(archived) - keep
    if excess <= 0:
        return
    for obsolete in archived[:excess]:
        obsolete.unlink(missing_ok=True)


def create_backup(
    target_file: Path,
    keep: int = MAX_TIMESTAMPED_BACKUPS,
) -> Tuple[Optional[Path], Optional[Path]]:
    """Crée une sauvegarde horodatée et un fichier .bak si le fichier cible existe.

    Returns:
        Tuple (chemin_backup_horodate, chemin_backup_bak) ou (None, None).
    """
    if not target_file.exists():
        return None, None

    backup_dir = target_file.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamped_backup = backup_dir / f"{target_file.stem}_{timestamp}{target_file.suffix}"
    latest_bak = target_file.with_suffix(target_file.suffix + ".bak")

    shutil.copy2(target_file, timestamped_backup)
    shutil.copy2(target_file, latest_bak)
    prune_timestamped_backups(backup_dir, target_file.stem, target_file.suffix, keep)

    return timestamped_backup, latest_bak


def fetch_openrouter_models(timeout: int = 10) -> List[dict[str, Any]]:
    """Interroge l'API publique OpenRouter pour récupérer la liste des modèles."""
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        headers={"User-Agent": "ModelScope/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload: object = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Réponse OpenRouter invalide : liste 'data' absente.")
    models: list[dict[str, Any]] = []
    for raw_model in payload["data"]:
        if not isinstance(raw_model, dict):
            raise ValueError("Réponse OpenRouter invalide : un modèle doit être un objet.")
        models.append(raw_model)
    return models


def sync_models_from_openrouter(
    output_path: Path,
    create_backup_file: bool = True,
    exclude_batch: bool = True,
) -> Tuple[int, Optional[Path]]:
    """Télécharge les modèles d'OpenRouter, met à jour le fichier JSON et gère le backup.

    Args:
        output_path: Chemin du fichier JSON de destination (ex: data/models.json).
        create_backup_file: Indique s'il faut sauvegarder l'ancienne version.
        exclude_batch: Exclut les variantes ':batch' d'OpenRouter pour alléger le registre.

    Returns:
        Tuple contenant (nombre_de_modèles_enregistrés, chemin_de_la_sauvegarde).
    """
    raw_models = fetch_openrouter_models()

    parsed_models: List[Model] = []
    for raw in raw_models:
        model = parse_openrouter_model(raw)
        if not model:
            continue
        if exclude_batch and ":batch" in model.id:
            continue
        parsed_models.append(model)

    # Création du backup si le fichier existe déjà
    backup_path: Optional[Path] = None
    if create_backup_file and output_path.exists():
        backup_path, _ = create_backup(output_path)

    # Préparation des données JSON
    output_data = {
        "version": "1.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": OPENROUTER_API_URL,
        "total_models": len(parsed_models),
        "models": [
            {
                "id": m.id,
                "provider": m.provider,
                "tier": m.tier,
                "cost_input_per_m": m.cost_input_per_m,
                "cost_output_per_m": m.cost_output_per_m,
                "context_window": m.context_window,
                "supports_tools": m.supports_tools,
                "complexity_score": m.complexity_score,
            }
            for m in parsed_models
        ],
    }

    write_json_atomic(output_path, output_data)

    return len(parsed_models), backup_path


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    target = base_dir / "data" / "models.json"
    print(f"🔄 Synchronisation des modèles depuis OpenRouter vers {target}...")
    try:
        count, bkp = sync_models_from_openrouter(target)
        print(f"✅ {count} modèles synchronisés avec succès dans {target}")
        if bkp:
            print(f"💾 Sauvegarde précédente conservée : {bkp}")
    except Exception as err:
        print(f"❌ Erreur lors de la synchronisation : {err}")
