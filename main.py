import os
import json
import asyncio

import httpx
import discord
from anthropic import AsyncAnthropic
import google.genai as genai

from dotenv import load_dotenv


load_dotenv()

if proxy := os.getenv("ALL_PROXY"):
    os.environ["ALL_PROXY"] = proxy


class ConfiguredAgent(discord.Client):
    def __init__(self, config: dict):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents)
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
            genai.Client(
                api_key=os.environ.get("GEMINI_API_KEY"),
                http_options={"proxy": proxy},
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
            http_options={"proxy": os.environ.get("ALL_PROXY")},
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

    proxy = os.getenv("ALL_PROXY")

    tasks = []
    for config in configs:
        agent = ConfiguredAgent(config)
        tasks.append(agent.start(agent.token))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
