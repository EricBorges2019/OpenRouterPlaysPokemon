import io
import base64
import logging
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_screenshot_base64(screenshot: Image.Image, upscale: int = 1) -> str:
    """Convert PIL image to base64 string."""
    # Resize if needed
    if upscale > 1:
        new_size = (screenshot.width * upscale, screenshot.height * upscale)
        screenshot = screenshot.resize(new_size)

    # Convert to base64
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    return base64.standard_b64encode(buffered.getvalue()).decode()


def apply_cache_control(messages: list, enabled: bool = True, ttl: str = "5m") -> list:
    """Apply OpenRouter prompt caching breakpoints to the outgoing messages.

    OpenRouter prompt caching expects `cache_control` to be attached to a *text*
    part inside a multipart `content` list.

    Strategy:
    - Cache the stable system prompt by converting the system message into a
      multipart content list and adding a tiny text part with `cache_control`.
    - If a condensed conversation summary exists (our first user multipart
      message), cache the large summary text by placing a cache_control
      breakpoint on the *next* text part (so only the summary text is in the
      cached prefix, not the screenshot).
    """
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
