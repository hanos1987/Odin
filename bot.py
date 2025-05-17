import discord
from discord.ext import commands
import json
import logging
import os
import asyncio
import subprocess

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
intents.message_content = True
intents.dm_messages = True
bot = commands.Bot(command_prefix=config['prefix'], intents=intents)

# Ensure server_configs directory exists
if not os.path.exists('./server_configs'):
    logger.warning("server_configs directory not found. Creating it.")
    os.makedirs('./server_configs')

# Load server-specific cogs
async def load_server_cogs(guild_id):
    # Always ensure the base 'general' cog is loaded
    if 'cogs.general' not in bot.extensions:
        try:
            await bot.load_extension('cogs.general')
            logger.info("Loaded base cog: cogs.general")
        except Exception as e:
            logger.error(f"Failed to load base cog cogs.general: {e}")

    # Load server-specific cogs
    config_path = f'./server_configs/{guild_id}.json'
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        server_cogs = data.get('cogs', [])
    except FileNotFoundError:
        # If no config exists, create a default one with no extra cogs
        server_cogs = []
        with open(config_path, 'w') as f:
            json.dump({"cogs": server_cogs}, f, indent=4)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {config_path}. Skipping server-specific cogs.")
        return

    # Load cogs specified in the server's config
    for cog_name in server_cogs:
        cog = f'cogs.{cog_name}'
        if cog != 'cogs.general' and cog not in bot.extensions:  # Avoid reloading the base cog
            try:
                await bot.load_extension(cog)
                logger.info(f"Loaded server-specific cog for guild {guild_id}: {cog}")
            except Exception as e:
                logger.error(f"Failed to load server-specific cog {cog} for guild {guild_id}: {e}")

# On ready event: Load general cog only initially
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    # Load only the base cog at startup
    if 'cogs.general' not in bot.extensions:
        try:
            await bot.load_extension('cogs.general')
            logger.info("Loaded base cog: cogs.general")
        except Exception as e:
            logger.error(f"Failed to load base cog cogs.general: {e}")

# Before invoking a command, load the server's cogs
@bot.before_invoke
async def before_invoke(ctx):
    if ctx.guild:  # Only load server cogs if the command is in a guild
        await load_server_cogs(ctx.guild.id)

# Error handling for commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` for a list of commands.")
    else:
        logger.error(f'Error in command {ctx.command}: {error}')
        await ctx.send("An error occurred while processing the command.")

# Command to enable a cog for the server
@bot.command()
@commands.has_permissions(administrator=True)
async def enable_function(ctx, cog_name: str):
    """Enables a cog for this server."""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    if not cog_name.isalnum():
        await ctx.send("Cog name must be alphanumeric (letters and numbers only).")
        return
    if not os.path.exists(f'./cogs/{cog_name}.py'):
        await ctx.send(f"No cog named '{cog_name}' exists in the cogs directory.")
        return

    config_path = f'./server_configs/{ctx.guild.id}.json'
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        server_cogs = data.get('cogs', [])
    except FileNotFoundError:
        server_cogs = []
        data = {"cogs": server_cogs}

    if cog_name == "general":
        await ctx.send("The 'general' cog is always enabled for all servers.")
        return
    if cog_name in server_cogs:
        await ctx.send(f"Cog '{cog_name}' is already enabled for this server.")
        return

    server_cogs.append(cog_name)
    data['cogs'] = server_cogs
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)

    # Load the cog immediately
    try:
        await bot.load_extension(f'cogs.{cog_name}')
        logger.info(f"Enabled and loaded cog for guild {ctx.guild.id}: cogs.{cog_name}")
        await ctx.send(f"Enabled and loaded cog '{cog_name}' for this server.")
    except Exception as e:
        logger.error(f"Failed to load cog {cog_name} for guild {ctx.guild.id}: {e}")
        await ctx.send(f"Failed to load cog '{cog_name}'. Check the code for errors.")

# Command to disable a cog for the server
@bot.command()
@commands.has_permissions(administrator=True)
async def disable_function(ctx, cog_name: str):
    """Disables a cog for this server."""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    if cog_name == "general":
        await ctx.send("The 'general' cog cannot be disabled.")
        return

    config_path = f'./server_configs/{ctx.guild.id}.json'
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        server_cogs = data.get('cogs', [])
    except FileNotFoundError:
        await ctx.send(f"Cog '{cog_name}' is not enabled for this server.")
        return

    if cog_name not in server_cogs:
        await ctx.send(f"Cog '{cog_name}' is not enabled for this server.")
        return

    server_cogs.remove(cog_name)
    data['cogs'] = server_cogs
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)

    # Unload the cog if no other servers are using it
    cog = f'cogs.{cog_name}'
    still_in_use = False
    for guild in bot.guilds:
        guild_config_path = f'./server_configs/{guild.id}.json'
        try:
            with open(guild_config_path, 'r') as f:
                guild_data = json.load(f)
            if cog_name in guild_data.get('cogs', []):
                still_in_use = True
                break
        except FileNotFoundError:
            continue

    if not still_in_use and cog in bot.extensions:
        try:
            await bot.unload_extension(cog)
            logger.info(f"Unloaded cog {cog} as it is no longer in use by any server.")
        except Exception as e:
            logger.error(f"Failed to unload cog {cog}: {e}")

    await ctx.send(f"Disabled cog '{cog_name}' for this server.")

# Command to add a new cog via DM
@bot.command()
@commands.has_permissions(administrator=True)
async def add_function(ctx, cog_name: str):
    """Initiates adding a new cog by DMing the invoker for the code, overwriting if it exists."""
    if not cog_name.isalnum():
        await ctx.send("Cog name must be alphanumeric (letters and numbers only).")
        return

    # Check if the cog is currently loaded
    cog_path = f'cogs.{cog_name}'
    was_loaded = cog_path in bot.extensions

    # If the cog is loaded, unload it before overwriting
    if was_loaded:
        try:
            await bot.unload_extension(cog_path)
            logger.info(f"Unloaded cog {cog_path} before overwriting.")
        except Exception as e:
            logger.error(f"Failed to unload cog {cog_path} before overwriting: {e}")
            await ctx.send(f"Failed to unload existing cog '{cog_name}' for overwriting: {str(e)}")
            return

    try:
        await ctx.author.send(f"Please reply with the `.py` code for the cog named '{cog_name}'. Wrap the code in triple backticks (```) like this:\n```\n# Your code here\n```")
        await ctx.send("I’ve sent you a DM. Please reply there with the cog code.")
    except discord.Forbidden:
        await ctx.send("I couldn’t DM you. Please enable DMs from server members.")
        return

    def check(msg):
        return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

    try:
        msg = await bot.wait_for('message', check=check, timeout=300)
        content = msg.content.strip()
        
        if content.startswith('```') and content.endswith('```'):
            code = content[3:-3].strip()
            if not code:
                await ctx.author.send("The code you provided is empty. Please try again.")
                return

            # Save the code, overwriting if the file exists
            with open(f'./cogs/{cog_name}.py', 'w') as f:
                f.write(code)
            logger.info(f'Saved (or overwrote) cog file: cogs/{cog_name}.py')
            await ctx.author.send(f"Cog '{cog_name}' has been added/overwritten. Use `!enable_function {cog_name}` in a server to enable it.")
        else:
            await ctx.author.send("Please wrap your code in triple backticks (```). Try again.")
    except asyncio.TimeoutError:
        await ctx.author.send("Timed out waiting for your reply. Please use `!add_function` again.")

# Command to pull updates from Git
@bot.command()
@commands.has_permissions(administrator=True)
async def update(ctx):
    """Pulls the latest changes from the Git repository (origin/main), overwriting local changes."""
    await ctx.send("Fetching and overwriting with latest changes from Git repository...")
    try:
        # Step 1: Fetch the latest changes
        fetch_result = subprocess.run(
            ['git', 'fetch', 'origin', 'main'],
            cwd='/root/Discord-Bots/Odin',
            capture_output=True,
            text=True
        )
        if fetch_result.returncode != 0:
            logger.error(f"Git fetch failed: {fetch_result.stderr}")
            await ctx.send(f"Git fetch failed:\n```\n{fetch_result.stderr}\n```")
            return

        # Step 2: Reset to the fetched main branch, overwriting local changes
        reset_result = subprocess.run(
            ['git', 'reset', '--hard', 'origin/main'],
            cwd='/root/Discord-Bots/Odin',
            capture_output=True,
            text=True
        )
        if reset_result.returncode == 0:
            logger.info("Git overwrite successful.")
            await ctx.send(f"Git overwrite successful:\n```\n{reset_result.stdout}\n```")
        else:
            logger.error(f"Git reset failed: {reset_result.stderr}")
            await ctx.send(f"Git reset failed:\n```\n{reset_result.stderr}\n```")
            return
    except Exception as e:
        logger.error(f"Error during git overwrite: {e}")
        await ctx.send(f"Error during git overwrite: {str(e)}")
        return

# Run the bot
async def main():
    try:
        await bot.start(config['token'])
    except Exception as e:
        logger.error(f'Failed to start bot: {e}')
        await bot.close()
        await asyncio.sleep(5)
        if bot.http:
            await bot.http.close()
        await main()

if __name__ == '__main__':
    asyncio.run(main())
