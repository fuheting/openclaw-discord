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
            client = genai.Client(api_key=gemini_key)
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


class ConfiguredAgent(discord.Client):
    def __init__(self, config: dict):
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
        self.token = os.getenv(config["token_env_var"])

        if self.provider == "anthropic":
            http_client = httpx.AsyncClient(proxy=proxy)
            self.anthropic = AsyncAnthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                http_client=http_client,
            )
        elif self.provider == "gemini":
            self.gemini = genai.Client(
                api_key=os.environ.get("GEMINI_API_KEY"),
            )

    async def on_ready(self):
        print(f"{self.name} bot logged in as {self.user}")

    async def on_message(self, message: discord.Message):
        if self.user.id == message.author.id:
            return

        mention_str = f"<@{self.discord_id}>"
        if mention_str not in message.content:
            return

        content = message.content.replace(mention_str, "").strip()

        thinking_msg = await message.reply(f"*{self.name} is thinking...*")

        try:
            response = await self._call_llm(content)
            await thinking_msg.edit(content=f"**{self.name}:** {response}")
        except Exception as e:
            await thinking_msg.edit(content=f"**{self.name}** encountered an error: {e}")

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
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
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

    tasks = []
    for config in configs:
        agent = ConfiguredAgent(config)
        tasks.append(agent.start(agent.token))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
