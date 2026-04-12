"""
api_config.py - Configuration for Anthropic API (uses environment variables)
Never hardcode API keys here - always use environment variables!
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get your API key from: https://console.anthropic.com/account/keys
# Set ANTHROPIC_API_KEY in your .env file
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError(
        "ANTHROPIC_API_KEY not found in environment variables. "
        "Please set it in your .env file or as an environment variable."
    )

# Model to use for responses
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# Max tokens for generated responses
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "300"))
