import discord
from discord.ext import commands
import json
import logging
import os
from dotenv import load_dotenv
import aiohttp

# Load environment variables from ../.env (relative to working directory /root/Discord-Bots/Odin)
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
logger = logging.getLogger(__name__)
logger.info(f"Attempting to load .env file from: {env_path}")
if not os.path.exists(env_path):
    logger.error(f".env file not found at: {env_path}")
load_dotenv(env_path)
XAI_API_KEY = os.getenv('XAI_API_KEY')

class FunctionGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        if not XAI_API_KEY:
            logger.error("XAI_API_KEY not found in .env file.")
        self._register_commands()

    def _register_commands(self):
        """Register this cog's commands in commands.json."""
        commands_to_register = {
            "function_generator": "Generates a program from a text prompt using AI (admin)."
        }
        try:
            try:
                with open('commands.json', 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {"commands": {}}

            data["commands"].update(commands_to_register)
            with open('commands.json', 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to register commands for FunctionGenerator cog: {e}")

    async def _call_ai_model(self, prompt):
        """Call the xAI API to generate code based on the prompt."""
        if not XAI_API_KEY:
            logger.error("No XAI_API_KEY provided.")
            return None

        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            url = "https://api.x.ai/v1/completions"
            headers = {
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "prompt": f"Generate a program: {prompt}",
                "max_tokens": 1000,
                "model": "grok-3"
            }

            logger.info(f"Sending request to xAI API with prompt: {prompt}")
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"xAI API error: {response.status} - {error_text}")
                    return None
                
                data = await response.json()
                logger.info(f"xAI API response: {data}")
                generated_code = data.get("choices", [{}])[0].get("text", "").strip()
                return generated_code if generated_code else None
        except Exception as e:
            logger.error(f"xAI API request failed: {str(e)}")
            return None

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def function_generator(self, ctx, *, prompt: str):
        """Generates a program from a text prompt using AI (admin)."""
        if not prompt:
            await ctx.send("Please provide a prompt to generate a program.")
            return

        generated_code = await self._call_ai_model(prompt)
        if not generated_code:
            await ctx.send("Failed to generate the program. Check the API key and server logs for details.")
            return

        if len(generated_code) > 1900:
            parts = [generated_code[i:i+1900] for i in range(0, len(generated_code), 1900)]
            for i, part in enumerate(parts, 1):
                await ctx.send(f"**Generated Program (Part {i}/{len(parts)})**:\n```\n{part}\n```")
        else:
            await ctx.send(f"**Generated Program**:\n```\n{generated_code}\n```")

    async def cog_unload(self):
        if self.session:
            await self.session.close()

async def setup(bot):
    await bot.add_cog(FunctionGenerator(bot))
