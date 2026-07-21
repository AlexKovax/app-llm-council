"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


def _extract_error_message(exc: Exception) -> str:
    """Best-effort extraction of a human-readable error message from an httpx exception.

    OpenRouter returns JSON bodies like {"error": {"message": "...", "code": 404}}
    on failures. We try to surface that message; otherwise we fall back to the
    raw response text or the exception string.
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            body = exc.response.json()
            err = body.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if isinstance(err, str) and err:
                return err
            if isinstance(body, dict) and body.get("message"):
                return str(body["message"])
        except Exception:
            pass
        text = (exc.response.text or "").strip()
        if text:
            return text[:500]
        return f"HTTP {exc.response.status_code}"
    return str(exc)


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    system_prompt: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g. "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        system_prompt: Optional system prompt prepended to the messages

    Returns:
        Response dict with 'content' and optional 'reasoning_details'. On
        failure, returns a dict with 'content' set to None and an 'error'
        field describing what went wrong (so callers can surface it to the
        UI instead of failing silently). Returns None only if the request
        could not even be attempted (e.g. empty messages).
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    final_messages = list(messages)
    if system_prompt:
        final_messages = [
            {"role": "system", "content": system_prompt},
            *final_messages,
        ]

    payload = {
        "model": model,
        "messages": final_messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        # Surface the error so the council can include it in the stage
        # results and the UI can show which model failed and why.
        return {
            'content': None,
            'error': _extract_error_message(e),
        }


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    system_prompts: Optional[List[Optional[str]]] = None,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel, optionally with per-model system prompts.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        system_prompts: Optional list of system prompts, one per model.
            If provided, must have the same length as `models`. Pass None
            or empty string for a model that should receive no system prompt.

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    if system_prompts is None:
        system_prompts = [None] * len(models)
    if len(system_prompts) != len(models):
        raise ValueError(
            "system_prompts must have the same length as models"
        )

    # Create tasks for all models
    tasks = [
        query_model(model, messages, system_prompt=prompt)
        for model, prompt in zip(models, system_prompts)
    ]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
