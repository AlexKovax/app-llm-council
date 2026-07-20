"""Persistent LLM personalities for the Council.

A personality is a named LLM persona combining a model, a system prompt, and
optional metadata. Personalities are persisted in `data/personalities.json` as
a single list. On first start, a set of default personalities is seeded.
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from .config import DATA_DIR


# Personalities live in a separate file at the data root, not inside the
# conversations directory (which is scanned for conversation files).
PERSONALITIES_FILE = os.path.join(os.path.dirname(DATA_DIR.rstrip("/")), "personalities.json")


def _ensure_data_dir() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def _load_all() -> List[Dict[str, Any]]:
    if not os.path.exists(PERSONALITIES_FILE):
        return []
    try:
        with open(PERSONALITIES_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_all(personalities: List[Dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(PERSONALITIES_FILE, "w") as f:
        json.dump(personalities, f, indent=2)


def _new_personality(
    name: str,
    model: str,
    system_prompt: str,
    description: str = "",
    is_seed: bool = False,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "model": model,
        "system_prompt": system_prompt,
        "description": description,
        "is_seed": is_seed,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def list_personalities() -> List[Dict[str, Any]]:
    """List all personalities, newest first."""
    personalities = _load_all()
    personalities.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return personalities


def get_personality(personality_id: str) -> Optional[Dict[str, Any]]:
    """Get a single personality by id, or None if not found."""
    for p in _load_all():
        if p["id"] == personality_id:
            return p
    return None


def create_personality(
    name: str,
    model: str,
    system_prompt: str,
    description: str = "",
) -> Dict[str, Any]:
    """Create and persist a new personality."""
    if not name or not name.strip():
        raise ValueError("Name is required")
    if not model or not model.strip():
        raise ValueError("Model is required")
    if not system_prompt or not system_prompt.strip():
        raise ValueError("System prompt is required")

    personality = _new_personality(
        name=name.strip(),
        model=model.strip(),
        system_prompt=system_prompt.strip(),
        description=(description or "").strip(),
    )
    personalities = _load_all()
    personalities.append(personality)
    _save_all(personalities)
    return personality


def update_personality(
    personality_id: str,
    name: Optional[str] = None,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update fields of a personality. Returns updated personality or None."""
    personalities = _load_all()
    for p in personalities:
        if p["id"] == personality_id:
            if name is not None:
                if not name.strip():
                    raise ValueError("Name cannot be empty")
                p["name"] = name.strip()
            if model is not None:
                if not model.strip():
                    raise ValueError("Model cannot be empty")
                p["model"] = model.strip()
            if system_prompt is not None:
                if not system_prompt.strip():
                    raise ValueError("System prompt cannot be empty")
                p["system_prompt"] = system_prompt.strip()
            if description is not None:
                p["description"] = description.strip()
            p["updated_at"] = datetime.utcnow().isoformat()
            _save_all(personalities)
            return p
    return None


def delete_personality(personality_id: str) -> bool:
    """Delete a personality by id."""
    personalities = _load_all()
    before = len(personalities)
    personalities = [p for p in personalities if p["id"] != personality_id]
    if len(personalities) == before:
        return False
    _save_all(personalities)
    return True


def seed_defaults_if_empty() -> None:
    """Seed default personalities on first start if none exist."""
    if _load_all():
        return

    # 3 archetype personalities (pure persona roles)
    archetypes = [
        (
            "The Skeptic",
            "openai/gpt-5.4",
            "You are The Skeptic. You distrust grand claims, demand evidence, "
            "and relentlessly probe for logical flaws, hidden assumptions, and "
            "edge cases. You prefer doubt over comfort and never accept an "
            "argument just because it sounds good. When you agree, you do so "
            "reluctantly and only after exhausting counter-arguments.",
            "Methodical doubter who hunts for holes in every argument.",
        ),
        (
            "The Strategist",
            "anthropic/claude-opus-4.8",
            "You are The Strategist. You think in terms of trade-offs, second-"
            "order effects, and long-term consequences. You frame every "
            "problem as a sequence of decisions under uncertainty, weigh "
            "costs and benefits explicitly, and prioritize actionable paths "
            "over theoretical purity. You are pragmatic and outcome-oriented.",
            "Pragmatic planner focused on trade-offs and long-term outcomes.",
        ),
        (
            "The Creative",
            "google/gemini-3.1-pro-preview",
            "You are The Creative. You favor originality, lateral thinking, "
            "and unexpected connections. You avoid obvious answers, propose "
            "multiple divergent options, and look for analogies from distant "
            "domains. You are comfortable with ambiguity and speculative "
            "ideas, but always tie them back to usefulness.",
            "Lateral thinker who proposes unexpected, divergent options.",
        ),
    ]

    # 3 real historical personalities
    historical = [
        (
            "Che Guevara",
            "deepseek/deepseek-v4-pro",
            "You are Ernesto \"Che\" Guevara, the Argentine-Marxist "
            "revolutionary. You view problems through the lens of class "
            "struggle, anti-imperialism, and solidarity with the oppressed. "
            "You are uncompromising on matters of principle, skeptical of "
            "capitalist and institutional solutions, and you prioritize "
            "collective action over individual comfort. You speak plainly "
            "and with conviction, often with a militant tone.",
            "Marxist revolutionary who frames issues through anti-imperialism.",
        ),
        (
            "Steve Jobs",
            "openai/gpt-5.4",
            "You are Steve Jobs, co-founder of Apple. You obsess over "
            "elegant simplicity, the intersection of technology and liberal "
            "arts, and products that delight users. You reject mediocrity, "
            "say no to a thousand things to say yes to the right one, and "
            "judge ideas harshly on whether they are \"insanely great\". You "
            "are demanding, opinionated, and focused on the user experience.",
            "Apple co-founder obsessed with elegance and user experience.",
        ),
        (
            "Plato",
            "anthropic/claude-opus-4.8",
            "You are Plato, the Athenian philosopher and student of "
            "Socrates. You pursue truth through dialectic, question "
            "definitions, and reason from the ideal Forms. You distrust "
            "mere appearances and rhetoric, you value virtue and justice, "
            "and you frequently use analogies, myths, and the Socratic "
            "method. You are patient, rigorous, and uninterested in "
            "practical shortcuts that compromise truth.",
            "Athenian philosopher who reasons via dialectic and ideal Forms.",
        ),
    ]

    personalities = []
    for name, model, prompt, desc in archetypes + historical:
        personalities.append(
            _new_personality(
                name=name,
                model=model,
                system_prompt=prompt,
                description=desc,
                is_seed=True,
            )
        )
    _save_all(personalities)
