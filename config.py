# Configuration for the application
MODEL_NAME = "google/gemini-2.0-flash-exp:free"
TEMPERATURE = 1.0
MAX_TOKENS = 10000

USE_NAVIGATOR = False

# Prompt caching configuration (OpenRouter)
# Default disabled to keep behaviour unchanged unless explicitly enabled.
PROMPT_CACHING_ENABLED = True
PROMPT_CACHE_TTL = "5m"  # Can be "5m" or "1h"