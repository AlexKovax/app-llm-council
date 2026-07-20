"""Cached OpenRouter model list for the personality picker.

The cache lives at `data/models.json` and is refreshed on demand via the
`refresh_models()` function, which calls OpenRouter's public `/models`
endpoint and filters to the providers we care about (OpenAI, Anthropic,
Gemini/Google, DeepSeek, GLM/Z-AI, Kimi/MoonshotAI). A hardcoded fallback
list is used on first start if the cache is empty and the API is
unreachable.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import httpx

from .config import DATA_DIR


MODELS_FILE = os.path.join(os.path.dirname(DATA_DIR.rstrip("/")), "models.json")
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Maximum number of models kept per provider, sorted by creation date
# (most recent first). Keeps the picker usable without dropping any provider.
MAX_MODELS_PER_PROVIDER = 5

# Provider prefixes we keep, mapped to a human-readable group label.
# Ordered the way the user requested them in the UI.
PROVIDER_GROUPS = [
    ("OpenAI", ["openai/"]),
    ("Anthropic", ["anthropic/"]),
    ("Google (Gemini)", ["google/"]),
    ("DeepSeek", ["deepseek/"]),
    ("GLM (Z-AI)", ["z-ai/", "thudm/"]),
    ("Kimi (Moonshot)", ["moonshotai/", "moonshot/"]),
]


# Fallback list used on first start if OpenRouter is unreachable. Kept short
# on purpose — the admin should hit "Refresh models" to get the live list.
FALLBACK_MODELS: List[Dict[str, Any]] = [
    {"id": "openai/gpt-5.4", "name": "GPT-5.4", "provider": "OpenAI"},
    {"id": "openai/gpt-5.5", "name": "GPT-5.5", "provider": "OpenAI"},
    {"id": "anthropic/claude-opus-4.8", "name": "Claude Opus 4.8", "provider": "Anthropic"},
    {"id": "anthropic/claude-sonnet-4.9", "name": "Claude Sonnet 4.9", "provider": "Anthropic"},
    {"id": "google/gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro", "provider": "Google (Gemini)"},
    {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "provider": "DeepSeek"},
    {"id": "z-ai/glm-4.6", "name": "GLM-4.6", "provider": "GLM (Z-AI)"},
    {"id": "moonshotai/kimi-k2", "name": "Kimi K2", "provider": "Kimi (Moonshot)"},
]


def _ensure_parent_dir() -> None:
    Path(os.path.dirname(MODELS_FILE)).mkdir(parents=True, exist_ok=True)


def _load_cache() -> Optional[Dict[str, Any]]:
    if not os.path.exists(MODELS_FILE):
        return None
    try:
        with open(MODELS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and "models" in data:
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_cache(models: List[Dict[str, Any]]) -> None:
    _ensure_parent_dir()
    payload = {
        "models": models,
        "updated_at": datetime.utcnow().isoformat(),
    }
    with open(MODELS_FILE, "w") as f:
        json.dump(payload, f, indent=2)


def _classify_provider(model_id: str) -> Optional[str]:
    """Return the human-readable provider group for a model id, or None."""
    for group_label, prefixes in PROVIDER_GROUPS:
        for prefix in prefixes:
            if model_id.startswith(prefix):
                return group_label
    return None


def list_models() -> Dict[str, Any]:
    """Return the cached model list and its last-updated timestamp.

    If no cache exists yet, seeds it with the hardcoded fallback list.
    """
    cache = _load_cache()
    if cache is None:
        _save_cache(FALLBACK_MODELS)
        cache = _load_cache()

    return {
        "models": cache.get("models", FALLBACK_MODELS),
        "updated_at": cache.get("updated_at"),
    }


async def refresh_models() -> Dict[str, Any]:
    """Fetch the live model list from OpenRouter and refresh the cache.

    Only models from the configured provider groups are kept. For each
    provider, only the `MAX_MODELS_PER_PROVIDER` most recent models
    (by OpenRouter's `created` timestamp) are retained, so the picker
    stays usable. The returned dict mirrors `list_models()` plus a
    `count` field.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(OPENROUTER_MODELS_URL)
            response.raise_for_status()
            payload = response.json()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch models from OpenRouter: {e}")

    raw_models = payload.get("data", []) if isinstance(payload, dict) else []

    # Group by provider, keeping id/name/created for each candidate
    by_provider: Dict[str, List[Dict[str, Any]]] = {}
    seen_ids = set()
    for m in raw_models:
        if not isinstance(m, dict):
            continue
        model_id = m.get("id")
        if not model_id or model_id in seen_ids:
            continue
        provider = _classify_provider(model_id)
        if provider is None:
            continue
        seen_ids.add(model_id)
        name = m.get("name") or model_id.split("/", 1)[1]
        # `created` is a Unix timestamp (int) or None if missing
        created = m.get("created")
        try:
            created = int(created) if created is not None else 0
        except (TypeError, ValueError):
            created = 0
        by_provider.setdefault(provider, []).append({
            "id": model_id,
            "name": name,
            "provider": provider,
            "created": created,
        })

    provider_order = {label: i for i, (label, _) in enumerate(PROVIDER_GROUPS)}

    # For each provider, sort by created desc and keep the top N
    kept: List[Dict[str, Any]] = []
    for provider, group_models in by_provider.items():
        group_models.sort(key=lambda x: x["created"], reverse=True)
        kept.extend(group_models[:MAX_MODELS_PER_PROVIDER])

    # Final sort: by provider order, then by created desc
    kept.sort(key=lambda x: (provider_order.get(x["provider"], 99), -x["created"]))

    # Strip the `created` field from the cached payload (not needed client-side)
    for m in kept:
        m.pop("created", None)

    if not kept:
        # If filtering dropped everything (shouldn't happen), keep fallback
        kept = list(FALLBACK_MODELS)

    _save_cache(kept)
    return {
        "models": kept,
        "updated_at": datetime.utcnow().isoformat(),
        "count": len(kept),
    }
