# OpenClaw Discord Multi-Agent System

A concurrent multi-agent Discord bot system using discord.py, Anthropic, and Gemini.

## Features

- **3 AI Agents** running concurrently: Project Manager, AI Engineer, Researcher
- **Anthropic Integration** for PM and Engineer bots
- **Gemini Integration** for Researcher bot
- **Proxy Support** for bypassing region blocks
- **@mention Activation** to prevent spam and infinite loops

## Quick Start

```bash
pip install discord.py anthropic google-genai python-dotenv httpx

# Configure .env with your tokens
cp .env.example .env

# Run
python main.py
```

## Project Structure

```
├── .env                 # API tokens (not committed)
├── .gitignore
├── agents_config.json   # Agent configurations
├── main.py              # Bot entry point
├── TUTORIAL.md          # Detailed usage guide
└── README.md
```

## License

MIT
