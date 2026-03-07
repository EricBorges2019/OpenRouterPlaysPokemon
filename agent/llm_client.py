import logging
import os
from openai import OpenAI
from config import MODEL_NAME, MAX_TOKENS, TEMPERATURE, PROMPT_CACHING_ENABLED, PROMPT_CACHE_TTL

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is not set. "
                "Please set it with your OpenRouter API key."
            )
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

    def apply_cache_control(self, messages, enabled=True, ttl="5m"):
        """Apply OpenRouter prompt caching breakpoints to the outgoing messages."""
        if not enabled or not messages:
            return messages

        if ttl not in ("5m", "1h"):
            ttl = "5m"

        cache_control = {"type": "ephemeral", "ttl": ttl}

        # 1) System prompt breakpoint (stable prefix)
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content")
                if isinstance(content, str):
                    msg["content"] = [
                        {"type": "text", "text": content},
                        {"type": "text", "text": "", "cache_control": cache_control},
                    ]
                elif isinstance(content, list):
                    # Ensure there's at least one text part to attach cache_control to
                    has_text = any(isinstance(p, dict) and p.get("type") == "text" for p in content)
                    if has_text:
                        content.append({"type": "text", "text": "", "cache_control": cache_control})
                break

        # 2) Summary breakpoint (stable prefix after summarization)
        for msg in messages:
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                parts = msg["content"]
                # Identify the summary text block
                summary_idx = None
                for i, part in enumerate(parts):
                    if isinstance(part, dict) and part.get("type") == "text":
                        if "CONVERSATION HISTORY SUMMARY" in (part.get("text") or ""):
                            summary_idx = i
                            break

                if summary_idx is None:
                    continue

                # Place breakpoint on the next text block after the summary
                for j in range(summary_idx + 1, len(parts)):
                    part = parts[j]
                    if isinstance(part, dict) and part.get("type") == "text":
                        part["cache_control"] = cache_control
                        return messages

                # If no subsequent text block exists, add a tiny one as breakpoint
                parts.insert(summary_idx + 1, {"type": "text", "text": "", "cache_control": cache_control})
                return messages

        return messages

    def create_completion(self, messages, tools=None):
        # Note: messages should be a copy if the caller wants to preserve the original structure
        # (apply_cache_control modifies in-place)
        messages_with_cache = self.apply_cache_control(
            messages,
            enabled=PROMPT_CACHING_ENABLED,
            ttl=PROMPT_CACHE_TTL
        )
        return self.client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            messages=messages_with_cache,
            tools=tools,
            temperature=TEMPERATURE,
        )
