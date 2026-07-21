"""3-stage LLM Council orchestration.

The council runs in a single unified code path parameterized by *participants*
and a *chairman*. A participant is a dict with at least `name` and `model`
keys, and optionally a `system_prompt`. The classic mode (no personalities) is
expressed as participants with no system prompt, built from the global config.
"""

from typing import List, Dict, Any, Tuple, Optional
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL
from . import prompts


Participant = Dict[str, Any]


def _participant_model(p: Participant) -> str:
    """Return the OpenRouter model id of a participant."""
    return p["model"]


def _participant_system_prompt(p: Participant) -> Optional[str]:
    """Return the optional system prompt of a participant."""
    return p.get("system_prompt")


def _participant_display_name(p: Participant) -> str:
    """Display name: prefer personality name, else short model name."""
    name = p.get("name")
    if name:
        return name
    model = p["model"]
    return model.split("/")[1] if "/" in model else model


def _participant_avatar(p: Participant) -> str:
    """SVG avatar markup for a participant (empty string if none)."""
    return p.get("avatar_svg") or ""


def classic_participants() -> List[Participant]:
    """Build participants from the classic global config (no system prompts)."""
    return [{"name": None, "model": m, "system_prompt": None} for m in COUNCIL_MODELS]


def classic_chairman() -> Participant:
    """Build the chairman from the classic global config."""
    return {"name": None, "model": CHAIRMAN_MODEL, "system_prompt": None}


async def stage1_collect_responses(
    user_query: str,
    participants: Optional[List[Participant]] = None,
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council participants.

    Args:
        user_query: The user's question
        participants: List of participant dicts. Defaults to classic config.

    Returns:
        List of dicts with 'model', 'display_name', and either 'response'
        (on success) or 'error' (on failure). Failed participants are kept
        in the list so the UI can show which model failed and why, instead
        of silently dropping them.
    """
    if participants is None:
        participants = classic_participants()

    messages = [{"role": "user", "content": user_query}]

    models = [_participant_model(p) for p in participants]
    system_prompts = [_participant_system_prompt(p) for p in participants]

    # Query all models in parallel
    responses = await query_models_parallel(models, messages, system_prompts=system_prompts)

    # Format results, preserving participant order. Include failed entries
    # (with response=None + error) so the UI can surface them.
    stage1_results = []
    for participant, model in zip(participants, models):
        response = responses.get(model)
        entry = {
            "model": model,
            "display_name": _participant_display_name(participant),
            "avatar_svg": _participant_avatar(participant),
            "system_prompt": _participant_system_prompt(participant),
            "response": None,
        }
        if response is not None:
            entry["response"] = response.get('content')
            if response.get('error'):
                entry["error"] = response['error']
        else:
            # Legacy case (query_model returned None) — shouldn't happen
            # with the current client, but kept for safety.
            entry["error"] = "No response returned by the API client."
        stage1_results.append(entry)

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    participants: Optional[List[Participant]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each participant ranks the anonymized responses, in character.

    The system prompt of each participant (if any) is applied during ranking
    so that a personality stays in character even while evaluating.

    Failed Stage 1 responses are excluded from the ranking prompt (a model
    cannot rank a missing response), but a participant whose own Stage 1
    failed can still evaluate the others in Stage 2.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1 (may include error entries)
        participants: List of participant dicts. Defaults to classic config.

    Returns:
        Tuple of (rankings list, label_to_model mapping). The rankings list
        includes error entries for participants whose Stage 2 query failed,
        so the UI can surface them instead of silently dropping them.
    """
    if participants is None:
        participants = classic_participants()

    # Only successful Stage 1 responses can be ranked. The anonymized labels
    # (A, B, C, ...) are assigned in order to the successful responses only.
    successful_stage1 = [r for r in stage1_results if r.get('response')]
    labels = [chr(65 + i) for i in range(len(successful_stage1))]

    # Mapping from label -> display name (used for de-anonymization client-side).
    # We map to the display_name (personality name if set, else model name)
    # so the UI can render meaningful identities.
    label_to_model = {
        f"Response {label}": result['display_name']
        for label, result in zip(labels, successful_stage1)
    }

    # Build the ranking prompt from successful responses only
    ranking_prompt = prompts.stage2_ranking_prompt(user_query, successful_stage1)

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all participants in parallel, each with its own system prompt
    models = [_participant_model(p) for p in participants]
    system_prompts = [_participant_system_prompt(p) for p in participants]

    responses = await query_models_parallel(models, messages, system_prompts=system_prompts)

    # Format results, preserving participant order. Include failed entries
    # so the UI can surface them.
    stage2_results = []
    for participant, model in zip(participants, models):
        response = responses.get(model)
        entry = {
            "model": model,
            "display_name": _participant_display_name(participant),
            "avatar_svg": _participant_avatar(participant),
            "ranking": None,
            "parsed_ranking": [],
        }
        if response is not None:
            content = response.get('content') or ''
            entry["ranking"] = content
            entry["parsed_ranking"] = parse_ranking_from_text(content)
            if response.get('error'):
                entry["error"] = response['error']
        else:
            entry["error"] = "No response returned by the API client."
        stage2_results.append(entry)

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman: Optional[Participant] = None,
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Failed Stage 1 / Stage 2 entries are excluded from the chairman prompt
    (only successful responses and rankings are sent to the chairman).

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1 (may include errors)
        stage2_results: Rankings from Stage 2 (may include errors)
        chairman: Chairman participant dict. Defaults to classic config.

    Returns:
        Dict with 'model', 'display_name', and either 'response' (on success)
        or 'error' (on failure).
    """
    if chairman is None:
        chairman = classic_chairman()

    # Only send successful Stage 1 / Stage 2 entries to the chairman
    successful_stage1 = [r for r in stage1_results if r.get('response')]
    successful_stage2 = [r for r in stage2_results if r.get('ranking')]

    # Build comprehensive context for chairman
    chairman_prompt = prompts.stage3_chairman_prompt(
        user_query, successful_stage1, successful_stage2
    )

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model, with its optional system prompt
    response = await query_model(
        _participant_model(chairman),
        messages,
        system_prompt=_participant_system_prompt(chairman),
    )

    result = {
        "model": _participant_model(chairman),
        "display_name": _participant_display_name(chairman),
        "avatar_svg": _participant_avatar(chairman),
        "response": None,
    }

    if response is None:
        result["error"] = "No response returned by the API client."
        return result

    if response.get('error'):
        result["error"] = response['error']
        return result

    result["response"] = response.get('content', '')
    return result


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to display names

    Returns:
        List of dicts with display name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each participant (keyed by display name)
    participant_positions = defaultdict(list)

    for ranking in stage2_results:
        # Skip participants whose Stage 2 query failed (no ranking text)
        if ranking.get('error') or not ranking.get('ranking'):
            continue

        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                display_name = label_to_model[label]
                participant_positions[display_name].append(position)

    # Calculate average position for each participant
    aggregate = []
    for display_name, positions in participant_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": display_name,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions),
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = prompts.title_generation_prompt(user_query)
    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    user_query: str,
    participants: Optional[List[Participant]] = None,
    chairman: Optional[Participant] = None,
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question
        participants: Council participants. Defaults to classic config.
        chairman: Chairman participant. Defaults to classic config.

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    if participants is None:
        participants = classic_participants()
    if chairman is None:
        chairman = classic_chairman()

    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query, participants)

    # If every Stage 1 participant failed, there is nothing to rank or
    # synthesize. Surface the chairman error so the UI can show it.
    if not any(r.get('response') for r in stage1_results):
        return (
            stage1_results,
            [],
            {
                "model": _participant_model(chairman),
                "display_name": _participant_display_name(chairman),
                "avatar_svg": _participant_avatar(chairman),
                "response": None,
                "error": "All council participants failed to respond. Please try again.",
            },
            {},
        )

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, participants
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        chairman,
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
    }

    return stage1_results, stage2_results, stage3_result, metadata
