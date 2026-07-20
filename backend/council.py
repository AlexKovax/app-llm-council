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
        List of dicts with 'model', 'display_name', and 'response' keys
    """
    if participants is None:
        participants = classic_participants()

    messages = [{"role": "user", "content": user_query}]

    models = [_participant_model(p) for p in participants]
    system_prompts = [_participant_system_prompt(p) for p in participants]

    # Query all models in parallel
    responses = await query_models_parallel(models, messages, system_prompts=system_prompts)

    # Format results, preserving participant order
    stage1_results = []
    for participant, model in zip(participants, models):
        response = responses.get(model)
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "display_name": _participant_display_name(participant),
                "system_prompt": _participant_system_prompt(participant),
                "response": response.get('content', ''),
            })

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

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        participants: List of participant dicts. Defaults to classic config.

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    if participants is None:
        participants = classic_participants()

    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Mapping from label -> display name (used for de-anonymization client-side).
    # We map to the display_name (personality name if set, else model name)
    # so the UI can render meaningful identities.
    label_to_model = {
        f"Response {label}": result['display_name']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    ranking_prompt = prompts.stage2_ranking_prompt(user_query, stage1_results)

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all participants in parallel, each with its own system prompt
    models = [_participant_model(p) for p in participants]
    system_prompts = [_participant_system_prompt(p) for p in participants]

    responses = await query_models_parallel(models, messages, system_prompts=system_prompts)

    # Format results, preserving participant order
    stage2_results = []
    for participant, model in zip(participants, models):
        response = responses.get(model)
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "display_name": _participant_display_name(participant),
                "ranking": full_text,
                "parsed_ranking": parsed,
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman: Optional[Participant] = None,
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        chairman: Chairman participant dict. Defaults to classic config.

    Returns:
        Dict with 'model', 'display_name', and 'response' keys
    """
    if chairman is None:
        chairman = classic_chairman()

    # Build comprehensive context for chairman
    chairman_prompt = prompts.stage3_chairman_prompt(user_query, stage1_results, stage2_results)

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model, with its optional system prompt
    response = await query_model(
        _participant_model(chairman),
        messages,
        system_prompt=_participant_system_prompt(chairman),
    )

    if response is None:
        # Fallback if chairman fails
        return {
            "model": _participant_model(chairman),
            "display_name": _participant_display_name(chairman),
            "response": "Error: Unable to generate final synthesis.",
        }

    return {
        "model": _participant_model(chairman),
        "display_name": _participant_display_name(chairman),
        "response": response.get('content', ''),
    }


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

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": _participant_model(chairman),
            "display_name": _participant_display_name(chairman),
            "response": "All models failed to respond. Please try again."
        }, {}

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
