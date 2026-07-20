"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
from datetime import datetime

from . import storage, personalities, models, prompts
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    """Seed default personalities on first start."""
    personalities.seed_defaults_if_empty()


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    content: str


class RenameConversationRequest(BaseModel):
    """Request to rename a conversation."""

    title: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""

    id: str
    created_at: str
    title: str
    message_count: int
    mode: str = "classic"


class Conversation(BaseModel):
    """Full conversation with all messages."""

    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]
    mode: str = "classic"
    lineup: List[Dict[str, Any]] = []
    chairman: Optional[Dict[str, Any]] = None


class PersonalityBase(BaseModel):
    """Fields for creating a personality."""

    name: str
    model: str
    system_prompt: str
    description: str = ""


class PersonalityUpdate(BaseModel):
    """Fields for updating a personality (all optional)."""

    name: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    description: Optional[str] = None


class LineupRequest(BaseModel):
    """Request to set a conversation's mode and personality lineup.

    The `lineup` is a list of participant dicts for Stage 1 & 2, each
    containing at least `id`, `name`, `model`, and `system_prompt` keys.
    The `chairman` is a separate participant dict for Stage 3 — it does NOT
    need to be in the lineup. Both are snapshot-stored on the conversation
    so reusing it later always reflects the state at creation time, even
    if the underlying personality is later edited or deleted.
    """

    mode: str  # "classic" or "personalities"
    lineup: List[Dict[str, Any]] = []
    chairman: Optional[Dict[str, Any]] = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/config")
async def get_config():
    """Get the council configuration (models used for deliberation)."""
    return {
        "council_models": COUNCIL_MODELS,
        "chairman_model": CHAIRMAN_MODEL,
    }


# ---------------------------------------------------------------------------
# Personalities CRUD
# ---------------------------------------------------------------------------

@app.get("/api/personalities")
async def list_personalities_route():
    """List all personalities, newest first."""
    return personalities.list_personalities()


@app.post("/api/personalities")
async def create_personality_route(payload: PersonalityBase):
    """Create a new personality and auto-generate its SVG avatar."""
    try:
        return await personalities.create_personality(
            name=payload.name,
            model=payload.model,
            system_prompt=payload.system_prompt,
            description=payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/api/personalities/{personality_id}")
async def update_personality_route(personality_id: str, payload: PersonalityUpdate):
    """Update a personality. Only non-None fields are updated."""
    try:
        updated = personalities.update_personality(
            personality_id,
            name=payload.name,
            model=payload.model,
            system_prompt=payload.system_prompt,
            description=payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail="Personality not found")
    return updated


@app.post("/api/personalities/{personality_id}/avatar")
async def regenerate_personality_avatar_route(personality_id: str):
    """Regenerate the SVG avatar for an existing personality via an LLM call."""
    updated = await personalities.regenerate_avatar(personality_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Personality not found")
    return updated


@app.delete("/api/personalities/{personality_id}")
async def delete_personality_route(personality_id: str):
    """Delete a personality."""
    deleted = personalities.delete_personality(personality_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Personality not found")
    return {"status": "deleted", "id": personality_id}


# ---------------------------------------------------------------------------
# Models (OpenRouter cache)
# ---------------------------------------------------------------------------

@app.get("/api/models")
async def list_models_route():
    """List the cached OpenRouter models (filtered to the configured providers)."""
    return models.list_models()


@app.post("/api/models/refresh")
async def refresh_models_route():
    """Refresh the OpenRouter model cache by hitting the live API."""
    try:
        return await models.refresh_models()
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings/prompts")
async def list_prompts_route():
    """Return the master prompt templates used by the council (read-only)."""
    return {"prompts": prompts.list_prompts()}


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.patch("/api/conversations/{conversation_id}/lineup", response_model=Conversation)
async def set_conversation_lineup(conversation_id: str, payload: LineupRequest):
    """Set the mode and personality lineup of a conversation.

    Allowed modes are "classic" and "personalities". For "personalities"
    mode, `lineup` must contain at least 2 participants and `chairman`
    must be a separate participant dict (it does NOT need to belong to
    the lineup).
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Only allow lineup changes on fresh conversations (no messages yet)
    if len(conversation.get("messages", [])) > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot change lineup of a conversation that already has messages",
        )

    if payload.mode not in ("classic", "personalities"):
        raise HTTPException(status_code=400, detail="Invalid mode")

    if payload.mode == "personalities":
        if len(payload.lineup) < 2:
            raise HTTPException(
                status_code=400,
                detail="Personalities mode requires at least 2 participants",
            )
        if not payload.chairman or not payload.chairman.get("id"):
            raise HTTPException(
                status_code=400,
                detail="A chairman personality is required in personalities mode",
            )

    updated = storage.set_conversation_lineup(
        conversation_id,
        mode=payload.mode,
        lineup=payload.lineup,
        chairman=payload.chairman,
    )
    return updated


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Resolve participants/chairman based on conversation mode
    participants, chairman = _resolve_participants(conversation)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content, participants=participants, chairman=chairman
    )

    # Add assistant message with all stages and persist metadata
    storage.add_assistant_message(
        conversation_id, stage1_results, stage2_results, stage3_result, metadata=metadata
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata,
    }


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    deleted = storage.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "id": conversation_id}


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(conversation_id: str, request: RenameConversationRequest):
    """Rename a conversation."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    storage.update_conversation_title(conversation_id, request.title)
    return {"status": "renamed", "id": conversation_id, "title": request.title}


@app.get("/api/conversations/{conversation_id}/export")
async def export_conversation(conversation_id: str):
    """Export a conversation as Markdown."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    md_lines = []
    title = conversation.get("title", "Conversation")
    md_lines.append(f"# {title}")
    md_lines.append(f"*Created: {conversation['created_at']}*")
    md_lines.append("")

    for i, msg in enumerate(conversation["messages"]):
        if msg["role"] == "user":
            q_num = (i // 2) + 1
            md_lines.append("---")
            md_lines.append("")
            md_lines.append(f"## Question {q_num}")
            md_lines.append("")
            md_lines.append(f"**User**: {msg['content']}")
            md_lines.append("")
        elif msg["role"] == "assistant":
            stage1 = msg.get("stage1", [])
            stage2 = msg.get("stage2", [])
            stage3 = msg.get("stage3", {})

            if stage1:
                md_lines.append("### Stage 1: Individual Responses")
                md_lines.append("")
                for resp in stage1:
                    display = resp.get("display_name") or resp.get("model", "Unknown")
                    model = resp.get("model", "")
                    response = resp.get("response", "")
                    reasoning = resp.get("reasoning_details")
                    md_lines.append(f"#### {display} ({model})")
                    md_lines.append("")
                    if reasoning:
                        md_lines.append(
                            f"<details><summary>Reasoning</summary>\n\n{reasoning}\n\n</details>"
                        )
                        md_lines.append("")
                    md_lines.append(response)
                    md_lines.append("")

            if stage2:
                md_lines.append("### Stage 2: Peer Rankings")
                md_lines.append("")
                for rank in stage2:
                    display = rank.get("display_name") or rank.get("model", "Unknown")
                    model = rank.get("model", "")
                    ranking = rank.get("ranking", "")
                    parsed = rank.get("parsed_ranking", [])
                    md_lines.append(f"#### {display} ({model})'s Evaluation")
                    md_lines.append("")
                    md_lines.append(ranking)
                    if parsed:
                        md_lines.append("")
                        md_lines.append(f"**Extracted Ranking**: {', '.join(parsed)}")
                    md_lines.append("")

            if stage3:
                md_lines.append("### Stage 3: Final Synthesis")
                md_lines.append("")
                chairman_display = stage3.get("display_name") or stage3.get("model", "Chairman")
                chairman_model = stage3.get("model", "")
                chairman_response = stage3.get("response", "")
                md_lines.append(f"*Chairman: {chairman_display} ({chairman_model})*")
                md_lines.append("")
                md_lines.append(chairman_response)
                md_lines.append("")

    markdown = "\n".join(md_lines)
    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="llm-council-{conversation_id[:8]}.md"'
        },
    )


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Resolve participants/chairman based on conversation mode
    participants, chairman = _resolve_participants(conversation)

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(
                    generate_conversation_title(request.content)
                )

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                request.content, participants=participants
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                request.content, stage1_results, participants=participants
            )
            aggregate_rankings = calculate_aggregate_rankings(
                stage2_results, label_to_model
            )
            metadata = {
                "label_to_model": label_to_model,
                "aggregate_rankings": aggregate_rankings,
            }
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': metadata})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                request.content, stage1_results, stage2_results, chairman=chairman
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message (with persisted metadata)
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result,
                metadata=metadata,
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _resolve_participants(conversation: Dict[str, Any]):
    """Resolve the participants and chairman for a conversation.

    For "classic" mode (or any conversation without a lineup), returns
    (None, None) so the council module uses the classic global config.
    For "personalities" mode, returns the snapshot lineup and the
    chairman participant (stored separately, does NOT need to belong
    to the lineup).
    """
    mode = conversation.get("mode", "classic")
    lineup = conversation.get("lineup", []) or []
    chairman = conversation.get("chairman")

    if mode != "personalities" or not lineup:
        return None, None

    # Chairman is stored as its own snapshot; fall back to first lineup
    # participant only if missing (legacy conversations).
    if chairman is None:
        chairman = lineup[0]

    return lineup, chairman


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
