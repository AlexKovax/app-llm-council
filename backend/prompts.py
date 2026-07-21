"""Centralized prompt templates used by the council.

Keeping these in one place makes them easy to inspect via the settings API
and to tweak without touching the orchestration code. Each builder function
returns the final prompt string given its required inputs.
"""

from typing import List, Dict, Any


def stage2_ranking_prompt(user_query: str, stage1_results: List[Dict[str, Any]]) -> str:
    """Build the Stage 2 ranking prompt.

    The user query is injected verbatim, and Stage 1 responses are
    anonymized as "Response A", "Response B", etc. in their original
    order.
    """
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    return f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""


def stage3_chairman_prompt(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
) -> str:
    """Build the Stage 3 chairman synthesis prompt."""
    stage1_text = "\n\n".join([
        f"Participant: {result.get('display_name', result['model'])}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Participant: {result.get('display_name', result['model'])}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    return f"""You are the Chairman of an LLM Council. Multiple AI participants have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""


def title_generation_prompt(user_query: str) -> str:
    """Build the title generation prompt (used for conversation naming)."""
    return f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""


def svg_avatar_prompt(name: str, description: str) -> str:
    """Build the prompt used to generate a monochrome SVG avatar for a personality.

    The output is a single self-contained <svg> element with a fixed 64x64
    viewBox, transparent background, and a single ink color (currentColor so
    the UI can theme it). The avatar is a stylized face that evokes the
    personality's essence. No scripts, no external resources, no markdown
    fences, no prose around the SVG.
    """
    desc_part = f"\nDescription: {description}" if description else ""
    return f"""You are an iconic portrait illustrator. Generate a single SVG image of a stylized human face that represents the following personality.

Personality: {name}{desc_part}

STRICT REQUIREMENTS:
- Output ONLY the raw SVG markup. No markdown, no code fences, no explanation, no prose before or after.
- The SVG must start with `<svg` and end with `</svg>`.
- Use viewBox="0 0 64 64" and width="64" height="64".
- Background MUST be transparent (no <rect> filling the whole canvas, no background color).
- Use a SINGLE ink color: fill="currentColor" (or stroke="currentColor"). Do not use any other color.
- Draw a human face (head, eyes, nose, mouth, optional hair/beard/headwear/glasses) styled to evoke the personality's identity and era.
- Style: minimalist flat portrait icon, bold readable silhouette, 2-4 simple shapes. Think iconic pictogram portrait, not detailed painting.
- The face should be recognizable and distinctive (e.g. beret + beard for Che, turtleneck + glasses for Jobs, toga + laurel for Plato).
- Forbidden tags: <script>, <foreignObject>, <use>, <image>, <style> with external URLs, base64 data URIs, any kind of animation.
- Keep the markup under 1.5 KB. No comments, no XML declaration, no xmlns:xlink.

Return only the SVG:"""


# Static descriptions of each prompt, used by the settings API to render them
# in the UI without needing to invoke the builders with real inputs. Each
# entry contains a stable `id`, a human-readable `label`, the raw `template`
# (with placeholders shown as {placeholder}), and a short `description`.
PROMPTS_METADATA = [
    {
        "id": "stage1_query",
        "label": "Stage 1 — User query",
        "description": (
            "Sent to each council participant in Stage 1. There is no master "
            "prompt: the user's question is forwarded verbatim as the message "
            "content. When a personality is attached, its system_prompt is "
            "prepended as a system message (independent of this template)."
        ),
        "template": "{user_query}",
    },
    {
        "id": "stage2_ranking",
        "label": "Stage 2 — Peer ranking prompt",
        "description": (
            "Sent to each participant in Stage 2. Contains the original "
            "question and the anonymized Stage 1 responses (Response A, B, "
            "C…). Asks the model to evaluate each response then provide a "
            "final ranking in a strict parseable format."
        ),
        "template": (
            "You are evaluating different responses to the following question:\n\n"
            "Question: {user_query}\n\n"
            "Here are the responses from different models (anonymized):\n\n"
            "{responses_text}\n\n"
            "Your task:\n"
            "1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.\n"
            "2. Then, at the very end of your response, provide a final ranking.\n\n"
            "IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:\n"
            "- Start with the line \"FINAL RANKING:\" (all caps, with colon)\n"
            "- Then list the responses from best to worst as a numbered list\n"
            "- Each line should be: number, period, space, then ONLY the response label (e.g., \"1. Response A\")\n"
            "- Do not add any other text or explanations in the ranking section\n\n"
            "Example of the correct format for your ENTIRE response:\n\n"
            "Response A provides good detail on X but misses Y...\n"
            "Response B is accurate but lacks depth on Z...\n"
            "Response C offers the most comprehensive answer...\n\n"
            "FINAL RANKING:\n"
            "1. Response C\n"
            "2. Response A\n"
            "3. Response B\n\n"
            "Now provide your evaluation and ranking:"
        ),
    },
    {
        "id": "stage3_chairman",
        "label": "Stage 3 — Chairman synthesis prompt",
        "description": (
            "Sent to the chairman model in Stage 3. Contains the original "
            "question, the Stage 1 individual responses, and the Stage 2 "
            "peer rankings. Asks the chairman to synthesize everything "
            "into a single final answer."
        ),
        "template": (
            "You are the Chairman of an LLM Council. Multiple AI participants have provided responses to a user's question, and then ranked each other's responses.\n\n"
            "Original Question: {user_query}\n\n"
            "STAGE 1 - Individual Responses:\n"
            "{stage1_text}\n\n"
            "STAGE 2 - Peer Rankings:\n"
            "{stage2_text}\n\n"
            "Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:\n"
            "- The individual responses and their insights\n"
            "- The peer rankings and what they reveal about response quality\n"
            "- Any patterns of agreement or disagreement\n\n"
            "Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"
        ),
    },
    {
        "id": "title_generation",
        "label": "Conversation title generation prompt",
        "description": (
            "Sent to a small fast model (gemini-2.5-flash) on the first "
            "message of a conversation to auto-generate a short title."
        ),
        "template": (
            "Generate a very short title (3-5 words maximum) that summarizes the following question.\n"
            "The title should be concise and descriptive. Do not use quotes or punctuation in the title.\n\n"
            "Question: {user_query}\n\n"
            "Title:"
        ),
    },
    {
        "id": "svg_avatar",
        "label": "Personality SVG avatar prompt",
        "description": (
            "Sent to deepseek-v4-flash on demand when the user regenerates a "
            "personality's avatar via the ↻ Avatar button. Asks for a single "
            "self-contained monochrome SVG face (64x64, transparent "
            "background, currentColor ink) that evokes the personality's "
            "identity. Stored in the `avatar_svg` field and snapshotted into "
            "conversations. Avatar generation is opt-in: creating a "
            "personality does NOT trigger an LLM call."
        ),
        "template": (
            "You are an iconic portrait illustrator. Generate a single SVG image of a stylized human face that represents the following personality.\n\n"
            "Personality: {name}\n"
            "Description: {description}\n\n"
            "STRICT REQUIREMENTS:\n"
            "- Output ONLY the raw SVG markup...\n"
            "- viewBox=\"0 0 64 64\", transparent background, fill=\"currentColor\"...\n"
            "- Draw a human face (head, eyes, nose, mouth, optional hair/beard/headwear/glasses)...\n"
            "- Forbidden: <script>, <foreignObject>, base64, animations...\n"
        ),
    },
]


def list_prompts() -> List[Dict[str, Any]]:
    """Return the metadata for all council prompts (for the settings UI)."""
    return list(PROMPTS_METADATA)
