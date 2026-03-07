import copy
import logging
import os

from config import MAX_TOKENS, MODEL_NAME, TEMPERATURE

from agent.emulator import Emulator
from agent.llm_client import LLMClient
from agent.prompts import SYSTEM_PROMPT, SUMMARY_PROMPT
from agent.tools import AVAILABLE_TOOLS
from agent.utils import get_screenshot_base64


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SimpleAgent:
    def __init__(self, rom_path, headless=True, sound=False, max_history=60, load_state=None):
        """Initialize the simple agent.

        Args:
            rom_path: Path to the ROM file
            headless: Whether to run without display
            sound: Whether to enable sound
            max_history: Maximum number of messages in history before summarization
        """
        self.emulator = Emulator(rom_path, headless, sound)
        self.emulator.initialize()  # Initialize the emulator
        self.client = LLMClient()
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
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"Error parsing arguments: {e.msg}. Please fix your JSON formatting."}
                ],
            }

        logger.info(f"Processing tool call: {tool_name}")

        if tool_name == "press_buttons":
            buttons = tool_input.get("buttons", [])
            if not buttons:
                logger.warning(f"[Buttons] Empty buttons argument received, skipping")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": [
                        {"type": "text", "text": "Error: No buttons specified. Please provide a list of buttons to press."}
                    ],
                }
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
            
            # Return tool result as a dictionary (OpenAI image format)
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"Pressed buttons: {', '.join(buttons)}"},
                    {"type": "text", "text": "\nHere is a screenshot of the screen after your button presses:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}"
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
            
            # Return tool result as a dictionary (OpenAI image format)
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"Navigation result: {result}"},
                    {"type": "text", "text": "\nHere is a screenshot of the screen after navigation:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}"
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
                
                # LLMClient handles caching
                try:
                    response = self.client.create_completion(
                        messages=messages_with_system,
                        tools=AVAILABLE_TOOLS,
                    )
                except Exception as e:
                    raise

                # Log usage with cache details
                usage = response.usage
                if usage:
                    log_msg = f"Response usage: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}"
                    if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                        details = usage.prompt_tokens_details
                        if hasattr(details, 'cached_tokens') and details.cached_tokens:
                            log_msg += f", cached={details.cached_tokens}"
                    if hasattr(usage, 'cache_write_tokens') and usage.cache_write_tokens:
                        log_msg += f", cache_write={usage.cache_write_tokens}"
                    logger.info(log_msg)
                else:
                    logger.info("Response usage: None")

                # Extract tool calls and content from response
                if not response or not hasattr(response, 'choices') or not response.choices:
                    logger.error(f"Invalid response from LLM API: {response}")
                    # Use a fallback empty response to keep loop going, or continue to retry
                    continue
                    
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
                    screenshot_b64 = None
                    memory_info = None
                    
                    for tool_call in tool_calls:
                        tool_result = self.process_tool_call(tool_call)
                        # Extract text and screenshot from tool result
                        content_parts = tool_result["content"]
                        text_parts = []
                        for part in content_parts:
                            if part.get("type") == "text":
                                text_parts.append(part["text"])
                            elif part.get("type") == "image_url":
                                # Extract screenshot for later user message
                                img_url = part.get("image_url", {}).get("url", "")
                                if img_url.startswith("data:image/png;base64,"):
                                    screenshot_b64 = img_url.replace("data:image/png;base64,", "")
                        
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "\n".join(text_parts),
                        })
                    
                    # Add tool results to message history
                    for tool_msg in tool_messages:
                        self.message_history.append(tool_msg)
                    
                    # Send screenshot as user message so model can see it
                    if screenshot_b64:
                        self.message_history.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Here is the current game state:"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                            ]
                        })

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
        
        # Get summary from the model
        response = self.client.create_completion(
            messages=messages_with_system,
        )
        
        # Log usage with cache details
        usage = response.usage
        if usage:
            log_msg = f"Summarization usage: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}"
            if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                details = usage.prompt_tokens_details
                if hasattr(details, 'cached_tokens') and details.cached_tokens:
                    log_msg += f", cached={details.cached_tokens}"
            if hasattr(usage, 'cache_write_tokens') and usage.cache_write_tokens:
                log_msg += f", cache_write={usage.cache_write_tokens}"
            logger.info(log_msg)
        else:
            logger.info("Summarization usage: None")
        
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
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}"
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
