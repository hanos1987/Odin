import discord
from discord.ext import commands
import json
import logging
import os
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for commands
bot = commands.Bot(command_prefix=config['prefix'], intents=intents)

# Load cogs dynamically
async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog = f'cogs.{filename[:-3]}'
            try:
                await bot.load_extension(cog)
                logger.info(f'Loaded cog: {cog}')
            except Exception as e:
                logger.error(f'Failed to load cog {cog}: {e}')

# On ready event
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    await load_cogs()

# Error handling for commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` for a list of commands.")
    else:
        logger.error(f'Error in command {ctx.command}: {error}')
        await ctx.send("An error occurred while processing the command.")

# Run the bot
async def main():
    try:
        await bot.start(config['token'])
    except Exception as e:
        logger.error(f'Failed to start bot: {e}')

if __name__ == '__main__':
    asyncio.run(main())
