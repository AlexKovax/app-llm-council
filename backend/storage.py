"""JSON-based storage for conversations."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Defaults to "classic" mode (no personality lineup). The mode and lineup
    can be set later via `set_conversation_lineup`.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "mode": "classic",
        "lineup": [],
        "chairman": None,
        "messages": [],
    }

    # Save to file
    path = get_conversation_path(conversation_id)
    with open(path, "w") as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, "r") as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation["id"])
    with open(path, "w") as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            path = os.path.join(DATA_DIR, filename)
            with open(path, "r") as f:
                data = json.load(f)
                # Return metadata only
                conversations.append(
                    {
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"]),
                        "mode": data.get("mode", "classic"),
                    }
                )

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({"role": "user", "content": content})

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
        metadata: Optional metadata (label_to_model, aggregate_rankings) to
            persist so the conversation displays correctly after reload
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    message = {
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
    }
    if metadata is not None:
        message["metadata"] = metadata

    conversation["messages"].append(message)

    save_conversation(conversation)


def set_conversation_lineup(
    conversation_id: str,
    mode: str,
    lineup: List[Dict[str, Any]],
    chairman: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Set the mode and personality lineup of a conversation.

    The lineup is a list of participant dicts for Stage 1 & 2 (each with
    at least `name`, `model`, and `system_prompt` keys). The chairman is
    a separate participant dict for Stage 3 — it does NOT need to belong
    to the lineup. Both are snapshot-stored on the conversation so that
    reusing the conversation later always reflects the state at creation
    time, even if the underlying personality is later edited or deleted.

    Args:
        conversation_id: Conversation identifier
        mode: "classic" or "personalities"
        lineup: List of participant dicts (snapshot) for Stage 1 & 2
        chairman: Chairman participant dict (snapshot) for Stage 3, or None

    Returns:
        Updated conversation, or None if not found
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        return None

    conversation["mode"] = mode
    conversation["lineup"] = lineup
    conversation["chairman"] = chairman
    save_conversation(conversation)
    return conversation


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        True if deleted, False if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return False

    os.remove(path)
    return True
