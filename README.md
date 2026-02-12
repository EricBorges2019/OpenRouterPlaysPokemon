# AI Plays Pokemon - Starter Version

A minimal implementation of AI (via OpenRouter) playing Pokemon Red using the PyBoy emulator. This starter version includes:

- Simple agent that uses AI models (via OpenRouter) to play Pokemon Red
- Memory reading functionality to extract game state information
- Basic emulator control through AI model tool calling

## Setup

1. Clone this repository
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Set up your OpenRouter API key as an environment variable:
   ```
   export OPENROUTER_API_KEY=your_api_key_here
   ```
   
   Get your API key from: https://openrouter.ai/keys
   
   Alternatively, copy [`.env.example`](.env.example) to `.env` and add your API key there

4. Place your Pokemon Red ROM file in the root directory (you need to provide your own ROM)

## Why OpenRouter?

This project uses OpenRouter instead of direct API providers for several advantages:

- **Multi-provider Access**: Switch between Claude, GPT-4, Gemini, and other models easily
- **Cost Optimization**: Compare pricing and use the most cost-effective model
- **Fallback Support**: Automatically retry with different models if one fails
- **Unified Interface**: One API key and interface for all providers
- **Rate Limit Management**: Built-in handling across providers

You can change models by updating the `MODEL_NAME` in [`config.py`](config.py) to any supported model:
- Anthropic: `anthropic/claude-3-7-sonnet-20250219`
- OpenAI: `openai/gpt-4-turbo`
- Google: `google/gemini-pro-1.5`
- And many more at https://openrouter.ai/models

## Usage

Run the main script:

```
python main.py
```

Optional arguments:
- `--rom`: Path to the Pokemon ROM file (default: `pokemon.gb` in the root directory)
- `--steps`: Number of agent steps to run (default: 10)
- `--display`: Run with display (not headless)
- `--sound`: Enable sound (only applicable with display)

Example:
```
python main.py --rom pokemon.gb --steps 20 --display --sound
```

## Implementation Details

### Components

- `agent/simple_agent.py`: Main agent class that uses AI models (via OpenRouter) to play Pokemon
- `agent/emulator.py`: Wrapper around PyBoy with helper functions
- `agent/memory_reader.py`: Extracts game state information from emulator memory

### How It Works

1. The agent captures a screenshot from the emulator
2. It reads the game state information from memory
3. It sends the screenshot and game state to the AI model (via OpenRouter)
4. The AI model responds with explanations and emulator commands
5. The agent executes the commands and repeats the process