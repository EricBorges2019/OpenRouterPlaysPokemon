import base64
import copy
import io
import logging
import os

from config import (
    MAX_TOKENS, MODEL_NAME, TEMPERATURE, USE_NAVIGATOR,
    PROMPT_CACHING_ENABLED, PROMPT_CACHE_TTL
)

from agent.emulator import Emulator
from openai import OpenAI



# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_screenshot_base64(screenshot, upscale=1):
    """Convert PIL image to base64 string."""
    # Resize if needed
    if upscale > 1:
        new_size = (screenshot.width * upscale, screenshot.height * upscale)
        screenshot = screenshot.resize(new_size)

    # Convert to base64
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    return base64.standard_b64encode(buffered.getvalue()).decode()


def apply_cache_control(messages, enabled=True, ttl="5m"):
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


SYSTEM_PROMPT = """You are playing Pokemon Red. You can see the game screen and control the game by executing emulator commands.

Your goal is to play through Pokemon Red and eventually defeat the Elite Four. Make decisions based on what you see on the screen.

Before each action, explain your reasoning briefly, then use the emulator tool to execute your chosen commands.

The conversation history may occasionally be summarized to save context space. If you see a message labeled "CONVERSATION HISTORY SUMMARY", this contains the key information about your progress so far. Use this information to maintain continuity in your gameplay."""

SUMMARY_PROMPT = """I need you to create a detailed summary of our conversation history up to this point. This summary will replace the full conversation history to manage the context window.

Please include:
1. Key game events and milestones you've reached
2. Important decisions you've made
3. Current objectives or goals you're working toward
4. Your current location and Pokémon team status
5. Any strategies or plans you've mentioned

The summary should be comprehensive enough that you can continue gameplay without losing important context about what has happened so far."""


AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "press_buttons",
            "description": "Press a sequence of buttons on the Game Boy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "buttons": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["a", "b", "start", "select", "up", "down", "left", "right"]
                        },
                        "description": "List of buttons to press in sequence. Valid buttons: 'a', 'b', 'start', 'select', 'up', 'down', 'left', 'right'"
                    },
                    "wait": {
                        "type": "boolean",
                        "description": "Whether to wait for a brief period after pressing each button. Defaults to true."
                    }
                },
                "required": ["buttons"],
            },
        }
    }
]

if USE_NAVIGATOR:
    AVAILABLE_TOOLS.append({
        "type": "function",
        "function": {
            "name": "navigate_to",
            "description": "Automatically navigate to a position on the map grid. The screen is divided into a 9x10 grid, with the top-left corner as (0, 0). This tool is only available in the overworld.",
            "parameters": {
                "type": "object",
                "properties": {
                    "row": {
                        "type": "integer",
                        "description": "The row coordinate to navigate to (0-8)."
                    },
                    "col": {
                        "type": "integer",
                        "description": "The column coordinate to navigate to (0-9)."
                    }
                },
                "required": ["row", "col"],
            },
        }
    })


class SimpleAgent:
    def __init__(self, rom_path, headless=True, sound=False, max_history=60, load_state=None):
        """Initialize the simple agent.

        Args:
            rom_path: Path to the ROM file
            headless: Whether to run without display
            sound: Whether to enable sound
            max_history: Maximum number of messages in history before summarization
        """
        # Fail-fast validation of API key
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is not set. "
                "Please set it with your OpenRouter API key."
            )
        
        self.emulator = Emulator(rom_path, headless, sound)
        self.emulator.initialize()  # Initialize the emulator
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.running = True
        self.message_history = [{"role": "user", "content": "You may now begin playing."}]
        self.max_history = max_history
        if load_state:
            logger.info(f"Loading saved state from {load_state}")
            self.emulator.load_state(load_state)

    def process_tool_call(self, tool_call):
        """Process a single tool call."""
        import json
        tool_name = tool_call.function.name
        
        # DEBUG: Log the raw arguments before attempting to parse
        logger.info(f"[DEBUG] Tool: {tool_name}")
        logger.info(f"[DEBUG] Raw arguments type: {type(tool_call.function.arguments)}")
        logger.info(f"[DEBUG] Raw arguments repr: {repr(tool_call.function.arguments)}")
        logger.info(f"[DEBUG] Raw arguments value: {tool_call.function.arguments}")
        
        logger.debug(f"Tool call: {tool_name}, args: {tool_call.function.arguments}")
        
        try:
            tool_input = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in {tool_name} at pos {e.pos}: {e.msg}")
            logger.error(f"Failed to parse arguments: {repr(tool_call.function.arguments)}")
            logger.error(f"Character at error position {e.pos}: {repr(tool_call.function.arguments[e.pos:e.pos+5])}")
            
            # WORKAROUND: Try to extract the last valid JSON object if multiple are concatenated
            args_str = tool_call.function.arguments
            logger.warning(f"Attempting to extract valid JSON from malformed arguments...")
            
            # Find all potential JSON objects by looking for }{ patterns (where objects are concatenated)
            # Try to parse from the rightmost valid JSON object
            potential_objects = []
            depth = 0
            start = -1
            for i, char in enumerate(args_str):
                if char == '{':
                    if depth == 0:
                        start = i
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0 and start != -1:
                        try:
                            obj = json.loads(args_str[start:i+1])
                            potential_objects.append(obj)
                        except json.JSONDecodeError:
                            pass
            
            if potential_objects:
                # Use the last valid object found (likely the most complete one)
                tool_input = potential_objects[-1]
                logger.warning(f"Successfully extracted JSON: {tool_input}")
            else:
                logger.error("Could not recover valid JSON from malformed arguments")
                raise
        
        logger.info(f"Processing tool call: {tool_name}")

        if tool_name == "press_buttons":
            buttons = tool_input["buttons"]
            wait = tool_input.get("wait", True)
            logger.info(f"[Buttons] Pressing: {buttons} (wait={wait})")
            
            result = self.emulator.press_buttons(buttons, wait)
            
            # Get a fresh screenshot after executing the buttons
            screenshot = self.emulator.get_screenshot()
            screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
            
            # Get game state from memory after the action
            memory_info = self.emulator.get_state_from_memory()
            
            # Log the memory state after the tool call
            logger.info(f"[Memory State after action]")
            logger.info(memory_info)
            
            collision_map = self.emulator.get_collision_map()
            if collision_map:
                logger.info(f"[Collision Map after action]\n{collision_map}")
            
            # Return tool result as a dictionary
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"Pressed buttons: {', '.join(buttons)}"},
                    {"type": "text", "text": "\nHere is a screenshot of the screen after your button presses:"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {"type": "text", "text": f"\nGame state information from memory after your action:\n{memory_info}"},
                ],
            }
        elif tool_name == "navigate_to":
            row = tool_input["row"]
            col = tool_input["col"]
            logger.info(f"[Navigation] Navigating to: ({row}, {col})")
            
            status, path = self.emulator.find_path(row, col)
            if path:
                for direction in path:
                    self.emulator.press_buttons([direction], True)
                result = f"Navigation successful: followed path with {len(path)} steps"
            else:
                result = f"Navigation failed: {status}"
            
            # Get a fresh screenshot after executing the navigation
            screenshot = self.emulator.get_screenshot()
            screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
            
            # Get game state from memory after the action
            memory_info = self.emulator.get_state_from_memory()
            
            # Log the memory state after the tool call
            logger.info(f"[Memory State after action]")
            logger.info(memory_info)
            
            collision_map = self.emulator.get_collision_map()
            if collision_map:
                logger.info(f"[Collision Map after action]\n{collision_map}")
            
            # Return tool result as a dictionary
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"Navigation result: {result}"},
                    {"type": "text", "text": "\nHere is a screenshot of the screen after navigation:"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {"type": "text", "text": f"\nGame state information from memory after your action:\n{memory_info}"},
                ],
            }
        else:
            logger.error(f"Unknown tool called: {tool_name}")
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"Error: Unknown tool '{tool_name}'"}
                ],
            }

    def run(self, num_steps=1):
        """Main agent loop.

        Args:
            num_steps: Number of steps to run for
        """
        logger.info(f"Starting agent loop for {num_steps} steps")

        steps_completed = 0
        while self.running and steps_completed < num_steps:
            try:
                messages = copy.deepcopy(self.message_history)

                # Prepend system message for OpenRouter
                messages_with_system = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
                
                # Apply prompt caching if enabled
                messages_with_system = apply_cache_control(
                    messages_with_system,
                    enabled=PROMPT_CACHING_ENABLED,
                    ttl=PROMPT_CACHE_TTL
                )

                # Get model response
                try:
                    response = self.client.chat.completions.create(
                        model=MODEL_NAME,
                        max_tokens=MAX_TOKENS,
                        messages=messages_with_system,
                        tools=AVAILABLE_TOOLS,
                        temperature=TEMPERATURE,
                    )
                except Exception as e:
                    raise

                # Log usage with cache details
                usage = response.usage
                log_msg = f"Response usage: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}"
                if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                    details = usage.prompt_tokens_details
                    if hasattr(details, 'cached_tokens') and details.cached_tokens:
                        log_msg += f", cached={details.cached_tokens}"
                if hasattr(usage, 'cache_write_tokens') and usage.cache_write_tokens:
                    log_msg += f", cache_write={usage.cache_write_tokens}"
                logger.info(log_msg)

                # Extract tool calls and content from response
                assistant_message = response.choices[0].message
                tool_calls = assistant_message.tool_calls if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls else []
                
                # WORKAROUND: Filter out tool calls with None arguments (openrouter package bug)
                if tool_calls:
                    valid_tool_calls = []
                    for tc in tool_calls:
                        if hasattr(tc.function, 'arguments') and tc.function.arguments is not None:
                            valid_tool_calls.append(tc)
                        else:
                            logger.warning(f"Skipping tool call {tc.function.name} with None arguments")
                    tool_calls = valid_tool_calls
                
                # Display the model's reasoning
                if assistant_message.content:
                    logger.info(f"[Text] {assistant_message.content}")
                
                if tool_calls:
                    for tool_call in tool_calls:
                        logger.info(f"[Tool] Using tool: {tool_call.function.name}")

                # Process tool calls
                if tool_calls:
                    # Add assistant message to history (OpenRouter format)
                    self.message_history.append({
                        "role": "assistant",
                        "content": assistant_message.content if assistant_message.content else "",
                        "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tool_calls]
                    })
                    
                    # Process tool calls and create tool results
                    tool_messages = []
                    for tool_call in tool_calls:
                        tool_result = self.process_tool_call(tool_call)
                        # Serialize tool result content properly
                        content_parts = tool_result["content"]
                        text_parts = []
                        image_count = 0
                        for part in content_parts:
                            if part.get("type") == "text":
                                text_parts.append(part["text"])
                            elif part.get("type") == "image":
                                image_count += 1
                                # Get image data size for placeholder
                                img_data = part.get("source", {}).get("data", "")
                                text_parts.append(f"[Screenshot captured: {len(img_data)} bytes base64]")
                        
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "\n".join(text_parts)
                        })
                    
                    # Add tool results to message history
                    for tool_msg in tool_messages:
                        self.message_history.append(tool_msg)

                    # Check if we need to summarize the history
                    if len(self.message_history) >= self.max_history:
                        self.summarize_history()

                steps_completed += 1
                logger.info(f"Completed step {steps_completed}/{num_steps}")

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping")
                self.running = False
            except Exception as e:
                logger.error(f"Error in agent loop: {e}")
                raise e

        if not self.running:
            self.emulator.stop()

        return steps_completed

    def summarize_history(self):
        """Generate a summary of the conversation history and replace the history with just the summary."""
        logger.info(f"[Agent] Generating conversation summary...")
        
        # Get a new screenshot for the summary
        screenshot = self.emulator.get_screenshot()
        screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
        
        # Create messages for the summarization request - pass the entire conversation history
        messages = copy.deepcopy(self.message_history) 

        messages.append({
            "role": "user",
            "content": SUMMARY_PROMPT,
        })
        
        # Prepend system message for OpenRouter
        messages_with_system = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        
        # Apply prompt caching if enabled
        messages_with_system = apply_cache_control(
            messages_with_system,
            enabled=PROMPT_CACHING_ENABLED,
            ttl=PROMPT_CACHE_TTL
        )
        
        # Get summary from the model
        response = self.client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            messages=messages_with_system,
            temperature=TEMPERATURE
        )
        
        # Log usage with cache details
        usage = response.usage
        log_msg = f"Summarization usage: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}"
        if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
            details = usage.prompt_tokens_details
            if hasattr(details, 'cached_tokens') and details.cached_tokens:
                log_msg += f", cached={details.cached_tokens}"
        if hasattr(usage, 'cache_write_tokens') and usage.cache_write_tokens:
            log_msg += f", cache_write={usage.cache_write_tokens}"
        logger.info(log_msg)
        
        # Extract the summary text
        summary_text = response.choices[0].message.content
        
        logger.info(f"[Agent] Game Progress Summary:")
        logger.info(f"{summary_text}")
        
        # Replace message history with just the summary
        self.message_history = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"CONVERSATION HISTORY SUMMARY (representing {self.max_history} previous messages): {summary_text}"
                    },
                    {
                        "type": "text",
                        "text": "\n\nCurrent game screenshot for reference:"
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "You were just asked to summarize your playthrough so far, which is the summary you see above. You may now continue playing by selecting your next action."
                    },
                ]
            }
        ]
        
        logger.info(f"[Agent] Message history condensed into summary.")
        
    def stop(self):
        """Stop the agent."""
        self.running = False
        self.emulator.stop()


if __name__ == "__main__":
    # Get the ROM path relative to this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    rom_path = os.path.join(os.path.dirname(current_dir), "pokemon.gb")

    # Create and run agent
    agent = SimpleAgent(rom_path)

    try:
        steps_completed = agent.run(num_steps=10)
        logger.info(f"Agent completed {steps_completed} steps")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping")
    finally:
        agent.stop()