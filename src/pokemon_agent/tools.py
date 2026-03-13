import json
import logging
from typing import Any, Dict, List, Optional

from .emulator import Emulator
from .utils import get_screenshot_base64
from .config import USE_NAVIGATOR

logger = logging.getLogger(__name__)

class ToolHandler:
    def __init__(self, emulator: Emulator):
        self.emulator = emulator

    @property
    def definitions(self) -> List[Dict[str, Any]]:
        """Return the list of available tools."""
        tools = [
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
            tools.append({
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
        return tools

    def _fix_json_arguments(self, args_str: str) -> Dict[str, Any]:
        """Attempt to fix malformed JSON arguments."""
        try:
            return json.loads(args_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error at pos {e.pos}: {e.msg}")
            logger.warning(f"Attempting to extract valid JSON from malformed arguments...")
            
            # Find all potential JSON objects by looking for }{ patterns
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
                tool_input = potential_objects[-1]
                logger.warning(f"Successfully extracted JSON: {tool_input}")
                return tool_input
            
            logger.error("Could not recover valid JSON from malformed arguments")
            raise

    def process_tool_call(self, tool_call) -> Dict[str, Any]:
        """Process a single tool call."""
        tool_name = tool_call.function.name
        logger.info(f"Processing tool call: {tool_name}")
        
        # Parse arguments
        if hasattr(tool_call.function, 'arguments'):
             # Handle weird object types if necessary, but assume string or dict
             if isinstance(tool_call.function.arguments, str):
                 tool_input = self._fix_json_arguments(tool_call.function.arguments)
             else:
                 tool_input = tool_call.function.arguments
        else:
            tool_input = {}

        result_content = []

        if tool_name == "press_buttons":
            buttons = tool_input.get("buttons", [])
            wait = tool_input.get("wait", True)
            logger.info(f"[Buttons] Pressing: {buttons} (wait={wait})")
            
            self.emulator.press_buttons(buttons, wait)
            result_content.append({"type": "text", "text": f"Pressed buttons: {', '.join(buttons)}"})

        elif tool_name == "navigate_to":
            row = tool_input.get("row")
            col = tool_input.get("col")
            logger.info(f"[Navigation] Navigating to: ({row}, {col})")
            
            status, path = self.emulator.find_path(row, col)
            if path:
                for direction in path:
                    self.emulator.press_buttons([direction], True)
                result_msg = f"Navigation successful: followed path with {len(path)} steps"
            else:
                result_msg = f"Navigation failed: {status}"
            
            result_content.append({"type": "text", "text": f"Navigation result: {result_msg}"})
            
        else:
            logger.error(f"Unknown tool called: {tool_name}")
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [{"type": "text", "text": f"Error: Unknown tool '{tool_name}'"}]
            }

        # Common post-action logic: screenshot and memory dump
        screenshot = self.emulator.get_screenshot()
        screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
        memory_info = self.emulator.get_state_from_memory()
        
        logger.info(f"[Memory State after action]\n{memory_info}")
        collision_map = self.emulator.get_collision_map()
        if collision_map:
            logger.info(f"[Collision Map after action]\n{collision_map}")

        result_content.extend([
            {"type": "text", "text": "\nHere is a screenshot of the screen after your action:"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot_b64,
                },
            },
            {"type": "text", "text": f"\nGame state information from memory after your action:\n{memory_info}"},
        ])

        return {
            "type": "tool_result",
            "tool_use_id": tool_call.id,
            "content": result_content,
        }
