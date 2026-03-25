import os
import json
import asyncio
from typing import Optional

import httpx
import discord
from anthropic import Anthropic, AsyncAnthropic
import google.genai as genai

from dotenv import load_dotenv


load_dotenv()

if proxy := os.getenv("ALL_PROXY"):
    os.environ["ALL_PROXY"] = proxy


def get_available_models() -> tuple[set[str], set[str]]:
    anthropic_models = set()
    gemini_models = set()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            client = Anthropic(api_key=anthropic_key)
            page = client.models.list(limit=100)
            anthropic_models = {m.id for m in page.data}
        except Exception as e:
            print(f"Failed to fetch Anthropic models: {e}")

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            http_options = {}
            if proxy:
                import httpx
                http_options = {
                    "httpx_client": httpx.Client(proxy=proxy),
                    "httpx_async_client": httpx.AsyncClient(proxy=proxy)
                }
            client = genai.Client(
                api_key=gemini_key,
                http_options=http_options if http_options else None
            )
            models = client.models.list()
            gemini_models = {m.name.replace("models/", "") for m in models}
        except Exception as e:
            print(f"Failed to fetch Gemini models: {e}")

    return anthropic_models, gemini_models


def validate_and_update_configs(configs: list[dict]) -> list[dict]:
    anthropic_models, gemini_models = get_available_models()

    print("\n=== Available Models ===")
    print(f"Anthropic ({len(anthropic_models)}): {', '.join(sorted(anthropic_models)[:8])}...")
    print(f"Gemini ({len(gemini_models)}): {', '.join(sorted(gemini_models)[:8])}...")
    print()

    updated = False

    defaults = {
        "anthropic": "claude-sonnet-4-20250514",
        "gemini": "gemini-2.5-flash",
    }

    for config in configs:
        provider = config.get("provider")
        model = config.get("model")
        agent_name = config.get("name", "Unknown")

        available = anthropic_models if provider == "anthropic" else gemini_models if provider == "gemini" else set()

        if model not in available:
            print(f"Warning: Agent '{agent_name}' has model '{model}' which is not available.")

            if available:
                config["model"] = defaults.get(provider, list(sorted(available))[0])
                print(f"Updated {agent_name} model to: {config['model']}")
                updated = True
            else:
                print(f"No available models for {provider} provider.")

    if updated:
        with open("agents_config.json", "w") as f:
            json.dump(configs, f, indent=2)
        print("\nUpdated agents_config.json")

    return configs


import re

class ConfiguredAgent(discord.Client):
    def __init__(self, config: dict, trusted_bot_ids: list[str]):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents, proxy=proxy)
        self.config = config
        self.name = config["name"]
        self.discord_id = config["discord_id"]
        self.provider = config["provider"]
        self.model = config["model"]
        self.system_prompt = config["system_prompt"]
        self.max_depth = config.get("max_depth", 5)
        self.trusted_bot_ids = trusted_bot_ids
        self.token = os.getenv(config["token_env_var"])

        if self.provider == "anthropic":
            http_client = httpx.AsyncClient(proxy=proxy)
            self.anthropic = AsyncAnthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                http_client=http_client,
            )
        elif self.provider == "gemini":
            http_options = {}
            if proxy:
                import httpx
                http_options = {
                    "httpx_client": httpx.Client(proxy=proxy),
                    "httpx_async_client": httpx.AsyncClient(proxy=proxy)
                }
            self.gemini = genai.Client(
                api_key=os.environ.get("GEMINI_API_KEY"),
                http_options=http_options if http_options else None
            )

    async def on_ready(self):
        print(f"{self.name} bot logged in as {self.user}")

    async def on_message(self, message: discord.Message):
        # 1. Prevent self-replies
        if self.user.id == message.author.id:
            return

        # 2. Trusted Bot Whitelist
        if message.author.bot and str(message.author.id) not in self.trusted_bot_ids:
            return

        # 3. Robust Mention Parsing
        if self.user not in message.mentions:
            return

        # 4. Infinite Loop Prevention (Depth Counter)
        current_depth = 1
        depth_match = re.search(r'\[Depth:\s*(\d+)\]', message.content)
        if depth_match:
            current_depth = int(depth_match.group(1))
            if current_depth >= self.max_depth:
                await message.reply(f"🛑 **System Pause:** Max autonomous conversation depth ({self.max_depth}) reached. "
                                    f"Project may be incomplete. @Human, please review our progress and mention me to continue.", mention_author=False)
                print(f"[{self.name}] Max conversation depth ({self.max_depth}) reached. Stopping loop.")
                return

        # 5. Clean current message
        clean_content = message.content
        clean_content = clean_content.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "")
        clean_content = re.sub(r'\[Depth:\s*\d+\]', '', clean_content).strip()

        # 6. Context History Fetching
        history_msgs = [msg async for msg in message.channel.history(limit=10, before=message)]
        history_msgs.reverse()  # Chronological order
        
        transcript = ""
        for h_msg in history_msgs:
            author_name = h_msg.author.name
            clean_h_content = re.sub(r'\[Depth:\s*\d+\]', '', h_msg.content).strip()
            transcript += f"[{author_name}]: {clean_h_content}\n"

        # Combine transcript and current message
        final_prompt = clean_content
        if transcript:
            final_prompt = f"--- Recent Channel History ---\n{transcript}\n--- End History ---\n\nNew Message from {message.author.name}:\n{clean_content}"

        thinking_msg = await message.reply(f"*{self.name} is thinking...*", mention_author=False)

        try:
            response = await self._call_llm(final_prompt)
            
            # 7. Human Intervention Check
            if "[REQUIRES HUMAN]" in response:
                clean_response = response.replace("[REQUIRES HUMAN]", "").strip()
                final_response = f"🛑 **{self.name} Needs Clarification:**\n{clean_response}"
            else:
                final_response = f"**{self.name}:** {response}\n\n*[Depth: {current_depth + 1}]*"
                
            await thinking_msg.delete()
            
            # Split the response if it exceeds Discord's 2000 character limit
            if len(final_response) > 2000:
                chunks = [final_response[i:i+1990] for i in range(0, len(final_response), 1990)]
                for idx, chunk in enumerate(chunks):
                    if idx == 0:
                        await message.reply(content=chunk, mention_author=False)
                    else:
                        await message.channel.send(content=chunk)
            else:
                await message.reply(content=final_response, mention_author=False)

        except Exception as e:
            try:
                await thinking_msg.edit(content=f"**{self.name}** encountered an error: {e}")
            except discord.NotFound:
                await message.reply(content=f"**{self.name}** encountered an error: {e}", mention_author=False)

    async def _call_llm(self, content: str) -> str:
        if self.provider == "anthropic":
            return await self._call_anthropic(content)
        elif self.provider == "gemini":
            return await self._call_gemini(content)

    async def _call_anthropic(self, content: str) -> str:
        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text

    async def _call_gemini(self, content: str) -> str:
        http_options = {}
        if proxy:
            import httpx
            http_options = {
                "httpx_client": httpx.Client(proxy=proxy),
                "httpx_async_client": httpx.AsyncClient(proxy=proxy)
            }
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
            http_options=http_options if http_options else None
        )
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=content,
            config={
                "system_instruction": self.system_prompt,
            },
        )
        return response.text


async def main():
    with open("agents_config.json") as f:
        configs = json.load(f)

    configs = validate_and_update_configs(configs)

    proxy = os.getenv("ALL_PROXY")
    
    trusted_bot_ids = [c["discord_id"] for c in configs]

    tasks = []
    for config in configs:
        agent = ConfiguredAgent(config, trusted_bot_ids)
        tasks.append(agent.start(agent.token))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
