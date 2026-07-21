"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers available as Stage 1
# participants in classic mode. The user picks a subset of these (default: all)
# plus a chairman for Stage 3.
COUNCIL_MODELS = [
    "openai/gpt-5.6-sol",
    "moonshotai/kimi-k3",
    "anthropic/claude-opus-4.8",
    "x-ai/grok-4.5",
    "google/gemini-3.1-pro-preview",
    "qwen/qwen3.7-max",
]

# Chairman model - synthesizes final response. Used as the default chairman
# selection in classic mode when the user has not explicitly picked one.
CHAIRMAN_MODEL = "openai/gpt-5.6-sol"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
