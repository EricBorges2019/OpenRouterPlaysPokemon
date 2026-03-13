import os
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "openrouter/free")
TEMPERATURE = float(os.getenv("TEMPERATURE", 1.0))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 4000))

USE_NAVIGATOR = os.getenv("USE_NAVIGATOR", "False").lower() in ("true", "1", "yes")

# Prompt caching configuration (OpenRouter)
PROMPT_CACHING_ENABLED = os.getenv("PROMPT_CACHING_ENABLED", "False").lower() in ("true", "1", "yes")
PROMPT_CACHE_TTL = os.getenv("PROMPT_CACHE_TTL", "5m")  # Can be "5m" or "1h"
