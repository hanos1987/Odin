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
bot = commands.Bot(command_prefix=config['prefix'], intents=intents, help_command=None)

# Your Discord user ID (replace with your actual user ID)
ALLOWED_USER_ID = 123456789012345678  # Replace with your Discord user ID

# Register bot-level commands in functions.json
def register_bot_commands():
    commands_to_register = {
        "update": "Restarts the bot (admin).",
        "add_function": "Adds a new cog via DM (admin).",
        "enable_function": "Enables a cog for the server (admin).",
        "disable_function": "Disables a cog for the server (admin).",
        "logs": "Displays the odin.service logs up to the maximum allowable length (admin).",
        "install_deps": "Installs dependencies from requirements.txt within the venv and restarts (admin).",
        "rename": "Renames a command in functions.json (admin).",
        "change_prefix": "Changes the bot's command prefix (admin).",
        "generate_cog": "Placeholder for generating predefined cog files on the server (admin).",
        "execute": "Executes a shell command on the server (admin, restricted)."
    }
    try:
        try:
            with open('functions.json', 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"cogs": {}, "bot_commands": {}}

        data["bot_commands"] = commands_to_register
        with open('functions.json', 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}")

# Ensure server_configs directory exists
if not os.path.exists('./server_configs'):
    logger.warning("server_configs directory not found. Creating it.")
    os.makedirs('./server_configs')

# Load server-specific cogs
async def load_server_cogs(guild_id):
    try:
        with open('functions.json', 'r') as f:
            functions_data = json.load(f)
        available_cogs = functions_data.get("cogs", {}).keys()
    except FileNotFoundError:
        logger.error("functions.json not found. No cogs will be loaded.")
        return
    except json.JSONDecodeError:
        logger.error("functions.json is invalid JSON. No cogs will be loaded.")
        return

    if 'cogs.general' not in bot.extensions:
        try:
            await bot.load_extension('cogs.general')
            logger.info("Loaded base cog: cogs.general")
        except Exception as e:
            logger.error(f"Failed to load base cog cogs.general: {e}")

    config_path = f'./server_configs/{guild_id}.json'
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        server_cogs = data.get('cogs', [])
    except FileNotFoundError:
        server_cogs = []
        with open(config_path, 'w') as f:
            json.dump({"cogs": server_cogs}, f, indent=4)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {config_path}. Skipping server-specific cogs.")
        return

    for cog_name in server_cogs:
        if cog_name not in available_cogs:
            logger.warning(f"Cog {cog_name} listed in server config but not in functions.json. Skipping.")
            continue
        cog = f'cogs.{cog_name}'
        if cog != 'cogs.general' and cog not in bot.extensions:
            try:
                await bot.load_extension(cog)
                logger.info(f"Loaded server-specific cog for guild {guild_id}: {cog}")
            except Exception as e:
                logger.error(f"Failed to load server-specific cog {cog} for guild {guild_id}: {e}")

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    register_bot_commands()
    if 'cogs.general' not in bot.extensions:
        try:
            await bot.load_extension('cogs.general')
            logger.info("Loaded base cog: cogs.general")
        except Exception as e:
            logger.error(f"Failed to load base cog cogs.general: {e}")

@bot.before_invoke
async def before_invoke(ctx):
    if ctx.guild:
        await load_server_cogs(ctx.guild.id)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` for a list of commands.")
    else:
        logger.error(f'Error in command {ctx.command}: {error}')
        await ctx.send("An error occurred while processing the command.")

@bot.command()
@commands.has_permissions(administrator=True)
async def enable_function(ctx, cog_name: str):
    import re
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    if not re.match(r'^[a-zA-Z0-9_-]+$', cog_name) or cog_name.startswith('.'):
        await ctx.send("Cog name can only contain letters, numbers, underscores, or hyphens, and cannot start with a period.")
        return
    if not os.path.exists(f'./cogs/{cog_name}.py'):
        await ctx.send(f"No cog named '{cog_name}' exists in the cogs directory.")
        return

    try:
        with open('functions.json', 'r') as f:
            functions_data = json.load(f)
        available_cogs = functions_data.get("cogs", {}).keys()
    except FileNotFoundError:
        await ctx.send("Error: functions.json not found.")
        return
    except json.JSONDecodeError:
        await ctx.send("Error: functions.json is invalid.")
        return

    if cog_name not in available_cogs:
        await ctx.send(f"Cog '{cog_name}' is not listed in functions.json.")
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

    try:
        await bot.load_extension(f'cogs.{cog_name}')
        logger.info(f"Enabled and loaded cog for guild {ctx.guild.id}: cogs.{cog_name}")
        await ctx.send(f"Enabled and loaded cog '{cog_name}' for this server.")
    except Exception as e:
        logger.error(f"Failed to load cog {cog_name} for guild {ctx.guild.id}: {e}")
        await ctx.send(f"Failed to load cog '{cog_name}'. Check the code for errors.")

@bot.command()
@commands.has_permissions(administrator=True)
async def disable_function(ctx, cog_name: str):
    import re
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    if not re.match(r'^[a-zA-Z0-9_-]+$', cog_name) or cog_name.startswith('.'):
        await ctx.send("Cog name can only contain letters, numbers, underscores, or hyphens, and cannot start with a period.")
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

@bot.command()
@commands.has_permissions(administrator=True)
async def add_function(ctx, cog_name: str):
    import re
    if not re.match(r'^[a-zAZ0-9_-]+$', cog_name) or cog_name.startswith('.'):
        await ctx.send("Cog name can only contain letters, numbers, underscores, or hyphens, and cannot start with a period.")
        return

    cog_path = f'cogs.{cog_name}'
    was_loaded = cog_path in bot.extensions

    if was_loaded:
        try:
            await bot.unload_extension(cog_path)
            logger.info(f"Unloaded cog {cog_path} before overwriting.")
        except Exception as e:
            logger.error(f"Failed to unload cog {cog_path} before overwriting: {e}")
            await ctx.send(f"Failed to unload existing cog '{cog_name}' for overwriting: {str(e)}")
            return

    logger.info(f"Sending DM to user {ctx.author.id} for cog code '{cog_name}'")
    try:
        await ctx.author.send(f"Please reply with the `.py` code for the cog named '{cog_name}'. Wrap the code in triple backticks (```) like this:\n```\n# Your code here\n```")
        await ctx.send("I’ve sent you a DM. Please reply there with the cog code.")
    except discord.Forbidden:
        logger.error(f"Failed to send DM to user {ctx.author.id}: DMs are disabled.")
        await ctx.send("I couldn’t DM you. Please enable DMs from server members.")
        return

    def check(msg):
        return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

    try:
        logger.info(f"Waiting for user {ctx.author.id} to reply with code for '{cog_name}'")
        msg = await bot.wait_for('message', check=check, timeout=300)
        content = msg.content.strip()
        logger.info(f"Received reply from user {ctx.author.id} for '{cog_name}': {content[:50]}...")

        if content.startswith('```') and content.endswith('```'):
            code = content[3:-3].strip()
            if not code:
                logger.warning(f"User {ctx.author.id} provided empty code for '{cog_name}'.")
                await ctx.author.send("The code you provided is empty. Please try again.")
                return

            logger.info(f"Attempting to write file for cog '{cog_name}' at ./cogs/{cog_name}.py")
            try:
                with open(f'./cogs/{cog_name}.py', 'w') as f:
                    f.write(code)
                logger.info(f'Saved (or overwrote) cog file: cogs/{cog_name}.py')
                await ctx.author.send(f"Cog '{cog_name}' has been added/overwritten. Use `!enable_function {cog_name}` in a server to enable it.")
            except Exception as e:
                logger.error(f"Failed to write file cogs/{cog_name}.py: {str(e)}")
                await ctx.author.send(f"Failed to save the cog file due to an error: {str(e)}")
        else:
            logger.warning(f"User {ctx.author.id} did not wrap code for '{cog_name}' in triple backticks.")
            await ctx.author.send("Please wrap your code in triple backticks (```). Try again.")
    except asyncio.TimeoutError:
        logger.warning(f"Timed out waiting for user {ctx.author.id} to reply for '{cog_name}'.")
        await ctx.author.send("Timed out waiting for your reply. Please use `!add_function` again.")

@bot.command()
@commands.has_permissions(administrator=True)
async def update(ctx):
    await ctx.send("Restarting Odin...")
    logger.info("Initiating bot restart.")

    await bot.close()
    if bot.http:
        await bot.http.close()
