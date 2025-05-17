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
        logger.info("Initializing FunctionGenerator cog")
        self._register_commands()

    def _register_commands(self):
        """Register this cog's commands in functions.json."""
        logger.info("Starting command registration for FunctionGenerator")
        commands_to_register = {
            "function_generator": "Generates a program from a text prompt using AI (admin). Usage: function_generator <function_name>"
        }
        try:
            try:
                with open('functions.json', 'r') as f:
                    data = json.load(f)
                logger.info("Successfully read functions.json")
            except FileNotFoundError:
                data = {"cogs": {}, "bot_commands": {}}
                logger.warning("functions.json not found, creating new structure")

            if "cogs" not in data:
                data["cogs"] = {}
            data["cogs"]["function_generator"] = {"commands": commands_to_register}
            with open('functions.json', 'w') as f:
                json.dump(data, f, indent=4)
            logger.info("Successfully registered commands for FunctionGenerator")
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
    async def function_generator(self, ctx, function_name: str):
        """Generates a program from a text prompt using AI (admin). Usage: function_generator <function_name>"""
        if not function_name:
            await ctx.send("Please provide a function name (e.g., `function_generator sort_list`).")
            return

        # Step 1: DM the user for the initial prompt
        try:
            await ctx.author.send(f"Let's create a program for the function `{function_name}`. Please provide a prompt describing what the program should do (e.g., 'a Python script to sort a list').")
            await ctx.send("I’ve sent you a DM to start creating the program.")
        except discord.Forbidden:
            await ctx.send("I couldn’t DM you. Please enable DMs from server members.")
            return

        def check(msg):
            return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

        try:
            # Wait for the initial prompt
            prompt_msg = await self.bot.wait_for('message', check=check, timeout=300)
            prompt = prompt_msg.content.strip()
            if not prompt:
                await ctx.author.send("The prompt you provided is empty. Please try again.")
                return

            # Step 2: Ask about specific functionality
            await ctx.author.send(f"Got your prompt: `{prompt}`. Now, please describe the specific functionality you want for `{function_name}` (e.g., 'It should handle duplicate values and sort in ascending order').")
            functionality_msg = await self.bot.wait_for('message', check=check, timeout=300)
            functionality = functionality_msg.content.strip()
            if not functionality:
                await ctx.author.send("The functionality description is empty. Please try again.")
                return

            # Step 3: Confirm the functionality
            await ctx.author.send(f"Here’s the functionality you described for `{function_name}`: `{functionality}`. Is this correct? Reply with 'yes' to confirm or 'no' to provide a new description.")
            confirmation_msg = await self.bot.wait_for('message', check=check, timeout=300)
            confirmation = confirmation_msg.content.strip().lower()

            if confirmation != 'yes':
                await ctx.author.send("Please provide the correct functionality description.")
                functionality_msg = await self.bot.wait_for('message', check=check, timeout=300)
                functionality = functionality_msg.content.strip()
                if not functionality:
                    await ctx.author.send("The functionality description is empty. Aborting.")
                    return

            # Step 4: Generate the program using the AI
            full_prompt = f"{prompt}. Specific functionality: {functionality}"
            generated_code = await self._call_ai_model(full_prompt)
            if not generated_code:
                await ctx.send("Failed to generate the program. Check the API key and server logs for details.")
                return

            # Step 5: Send the generated code back to the channel
            if len(generated_code) > 1900:
                parts = [generated_code[i:i+1900] for i in range(0, len(generated_code), 1900)]
                for i, part in enumerate(parts, 1):
                    await ctx.send(f"**Generated Program for `{function_name}` (Part {i}/{len(parts)})**:\n```\n{part}\n```")
            else:
                await ctx.send(f"**Generated Program for `{function_name}`**:\n```\n{generated_code}\n```")

        except asyncio.TimeoutError:
            await ctx.author.send("Timed out waiting for your reply. Please use `#function_generator` again.")

    async def cog_unload(self):
        if self.session:
            await self.session.close()

async def setup(bot):
    await bot.add_cog(FunctionGenerator(bot))
