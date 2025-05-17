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
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    required_keys = ['prefix', 'token']
    for key in required_keys:
        if key not in config:
            raise KeyError(f"Missing required config key: {key}")
except FileNotFoundError:
    logger.error("config.json not found. Please create it with 'prefix' and 'token'.")
    exit(1)
except json.JSONDecodeError:
    logger.error("config.json is not a valid JSON file.")
    exit(1)

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for commands
bot = commands.Bot(command_prefix=config['prefix'], intents=intents)

# Load cogs from functions.json
async def load_cogs_from_json():
    try:
        with open('functions.json', 'r') as f:
            data = json.load(f)
        cogs_list = data.get('cogs', [])
    except FileNotFoundError:
        logger.error("functions.json not found. Creating a default one.")
        cogs_list = []
        with open('functions.json', 'w') as f:
            json.dump({"cogs": cogs_list}, f, indent=4)
    except json.JSONDecodeError:
        logger.error("functions.json is not a valid JSON file.")
        return

    # Ensure cogs directory exists
    if not os.path.exists('./cogs'):
        logger.warning("Cogs directory not found. Creating it.")
        os.makedirs('./cogs')

    # Track currently loaded cogs
    currently_loaded = set(bot.extensions.keys())
    desired_cogs = set(f'cogs.{cog}' for cog in cogs_list)

    # Unload cogs that are no longer in functions.json
    for cog in currently_loaded:
        if cog not in desired_cogs and cog.startswith('cogs.'):
            try:
                await bot.unload_extension(cog)
                logger.info(f'Unloaded cog: {cog}')
            except Exception as e:
                logger.error(f'Failed to unload cog {cog}: {e}')

    # Load or reload cogs from functions.json
    for cog_name in cogs_list:
        cog = f'cogs.{cog_name}'
        try:
            # If cog is already loaded, reload it
            if cog in bot.extensions:
                await bot.reload_extension(cog)
                logger.info(f'Reloaded cog: {cog}')
            else:
                await bot.load_extension(cog)
                logger.info(f'Loaded cog: {cog}')
        except Exception as e:
            logger.error(f'Failed to load/reload cog {cog}: {e}')

# On ready event
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    await load_cogs_from_json()

# Error handling for commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` for a list of commands.")
    else:
        logger.error(f'Error in command {ctx.command}: {error}')
        await ctx.send("An error occurred while processing the command.")

# Command to update cogs while the bot is running
@bot.command()
@commands.has_permissions(administrator=True)  # Restrict to admins
async def function_update(ctx):
    """Reloads cogs based on functions.json."""
    await ctx.send("Updating cogs from functions.json...")
    await load_cogs_from_json()
    await ctx.send("Cog update complete!")

# Run the bot
async def main():
    try:
        await bot.start(config['token'])
    except Exception as e:
        logger.error(f'Failed to start bot: {e}')
        await asyncio.sleep(5)  # Wait before retrying
        await main()  # Attempt to reconnect

if __name__ == '__main__':
    asyncio.run(main())
