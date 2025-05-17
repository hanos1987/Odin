import discord
from discord.ext import commands
import json
import logging
import os
from dotenv import load_dotenv
import aiohttp

# Load environment variables from /root/Discord_Bots/.env
load_dotenv('/root/Discord_Bots/.env')
XAI_API_KEY = os.getenv('XAI_API_KEY')

# Set up logging
logger = logging.getLogger(__name__)

class AiAddFunction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Validate API key presence
        if not XAI_API_KEY:
            logger.error("XAI_API_KEY not found in .env file.")
        self._register_commands()

    def _register_commands(self):
        """Register this cog's commands in commands.json."""
        commands_to_register = {
            "ai_addfunction": "Generates a program from a text prompt using AI (admin)."
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
            logger.error(f"Failed to register commands for AiAddFunction cog: {e}")

    async def _call_ai_model(self, prompt):
        """Call the xAI API to generate code based on the prompt."""
        if not XAI_API_KEY:
            logger.error("No XAI_API_KEY provided.")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                # Updated endpoint (confirm with xAI API docs: https://x.ai/api)
                url = "https://api.x.ai/v1/completions"  # Likely endpoint
                headers = {
                    "Authorization": f"Bearer {XAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "prompt": f"Generate a program: {prompt}",
                    "max_tokens": 1000,
                    "model": "grok-3"  # Adjust based on xAI's available models
                }

                logger.info(f"Sending request to xAI API with prompt: {prompt}")
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"xAI API error: {response.status} - {error_text}")
                        return None
                    
                    data = await response.json()
                    logger.info(f"xAI API response: {data}")
                    # Extract the generated code (adjust based on actual API response structure)
                    generated_code = data.get("choices", [{}])[0].get("text", "").strip()
                    return generated_code if generated_code else None
        except Exception as e:
            logger.error(f"xAI API request failed: {str(e)}")
            return None

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ai_addfunction(self, ctx, *, prompt: str):
        """Generates a program from a text prompt using AI (admin)."""
        if not prompt:
            await ctx.send("Please provide a prompt to generate a program.")
            return

        # Call the xAI API to generate the code
        generated_code = await self._call_ai_model(prompt)
        if not generated_code:
            await ctx.send("Failed to generate the program. Check the API key and server logs for details.")
            return

        # Ensure the output fits within Discord's 2000-character limit
        if len(generated_code) > 1900:
            parts = [generated_code[i:i+1900] for i in range(0, len(generated_code), 1900)]
            for i, part in enumerate(parts, 1):
                await ctx.send(f"**Generated Program (Part {i}/{len(parts)})**:\n```\n{part}\n```")
        else:
            await ctx.send(f"**Generated Program**:\n```\n{generated_code}\n```")

async def setup(bot):
    await bot.add_cog(AiAddFunction(bot))
