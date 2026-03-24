# Multi-Agent Discord Bot System Tutorial

This system runs 3 AI agents concurrently on Discord: a Project Manager (Anthropic), an AI Engineer (Anthropic), and a Researcher (Gemini).

## Prerequisites

- Python 3.10+
- Discord bot tokens for 3 bots
- Anthropic API key
- Gemini API key
- SOCKS5 proxy (for bypassing region blocks)

## Setup

### 1. Install Dependencies

```bash
pip install discord.py anthropic google-genai python-dotenv httpx
```

### 2. Configure Environment Variables

Edit `.env` with your actual credentials:

```env
DISCORD_TOKEN_PM=your_pm_bot_token
DISCORD_TOKEN_ENG=your_engineer_bot_token
DISCORD_TOKEN_RES=your_researcher_bot_token

ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key

ALL_PROXY=socks5h://127.0.0.1:7890
```

### 3. Update Agent Discord IDs

Edit `agents_config.json` to replace the `discord_id` values with your actual bot user IDs. You can get a bot's ID by enabling Developer Mode in Discord and right-clicking the bot username.

### 4. Configure Agent Behaviors

Edit the `system_prompt` field in `agents_config.json` for each agent to customize their behavior and instructions.

## Running the System

### Start All Agents

```bash
python main.py
```

All 3 bots will start concurrently and connect to Discord. You should see output like:

```
Project Manager bot logged in as <Bot>
AI Engineer bot logged in as <Bot>
Researcher bot logged in as <Bot>
```

### Stop the System

Press `Ctrl+C` to gracefully shutdown all bots.

## Using the Bots

### Mention Syntax

Tag a bot using its Discord mention format: `<@BOT_ID>`

Example: `<@1485638996695711865>`

### Interacting with the Project Manager

The PM coordinates tasks. Message it directly or in a channel:

```
<@1485638996695711865> We need to research authentication methods for our web app
```

The PM will analyze the request and delegate to the Engineer or Researcher as appropriate.

### Direct Agent Communication

You can also message the Engineer or Researcher directly:

```
<@1485928264525414461> Write a Python function to validate email addresses
```

```
<@1485925944018341979> What are the latest developments in LLM architecture?
```

### Delegation from PM

When the PM delegates to another agent, it will @mention them in its response. You can then continue the conversation directly with that agent.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Discord Server                        │
│                                                         │
│   User ──@mention──► PM Bot ──@mention──► Engineer Bot  │
│                      │                   │              │
│                      └───@mention──► Researcher Bot     │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Concurrent asyncio    │
              │  .gather() execution   │
              └───────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐    ┌───────────┐    ┌───────────┐
    │Anthropic│    │ Anthropic │    │  Gemini   │
    │  (PM)   │    │(Engineer) │    │(Research) │
    └─────────┘    └───────────┘    └───────────┘
```

## Troubleshooting

### Bots Not Responding

1. Verify all tokens in `.env` are correct
2. Ensure bots have "Message Content Intent" enabled in Discord Developer Portal
3. Check bots have permissions to read/send messages in your channel

### API Errors

1. Verify API keys are valid and have sufficient quota
2. Check your proxy is running and accessible
3. Review the error message in the bot's reply

### Region Block Errors

Ensure `ALL_PROXY` in `.env` points to a working SOCKS5 proxy that can reach the API endpoints.

## Customization

### Adding New Agents

1. Add a new entry to `agents_config.json` with:
   - Unique `discord_id`
   - New `DISCORD_TOKEN_*` in `.env`
   - Appropriate `provider` (anthropic or gemini)

2. Add the new token to `.env`

3. Include the new token env var in `main.py` when starting

### Changing Models

Update the `model` field in `agents_config.json`:
- Anthropic: `claude-opus-4-20250514`, `claude-sonnet-4-20250514`, `claude-haiku-4-20250507`
- Gemini: `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-pro`
