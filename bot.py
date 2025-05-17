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
        "generate_cog": "Placeholder for generating predefined cog files on the server (admin)."
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

            with open(f'./cogs/{cog_name}.py', 'w') as f:
                f.write(code)
            logger.info(f'Saved (or overwrote) cog file: cogs/{cog_name}.py')
            await ctx.author.send(f"Cog '{cog_name}' has been added/overwritten. Use `!enable_function {cog_name}` in a server to enable it.")
        else:
            await ctx.author.send("Please wrap your code in triple backticks (```). Try again.")
    except asyncio.TimeoutError:
        await ctx.author.send("Timed out waiting for your reply. Please use `!add_function` again.")

@bot.command()
@commands.has_permissions(administrator=True)
async def update(ctx):
    await ctx.send("Restarting Odin...")
    logger.info("Initiating bot restart.")

    await bot.close()
    if bot.http:
        await bot.http.close()

    import sys
    import os
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.command()
@commands.has_permissions(administrator=True)
async def logs(ctx):
    try:
        result = subprocess.run(
            ['journalctl', '-u', 'odin.service', '-n', '20', '--no-pager'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logs = result.stdout.strip()
            if not logs:
                await ctx.send("No logs found for odin.service.")
                return
            if len(logs) > 1900:
                logs = "..." + logs[-1900:]
            await ctx.send(f"**Odin Service Logs**:\n```\n{logs}\n```")
        else:
            logger.error(f"Failed to fetch logs: {result.stderr}")
            await ctx.send(f"Failed to fetch logs:\n```\n{result.stderr}\n```")
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        await ctx.send(f"Error fetching logs: {str(e)}")

@bot.command()
@commands.has_permissions(administrator=True)
async def install_deps(ctx):
    await ctx.send("Installing dependencies from requirements.txt within the virtual environment...")
    try:
        venv_pip = '/root/Discord-Bots/Odin/venv/bin/pip'
        result = subprocess.run(
            [venv_pip, 'install', '-r', 'requirements.txt'],
            cwd='/root/Discord-Bots/Odin',
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info("Dependencies installed successfully.")
            await ctx.send(f"Dependencies installed successfully:\n```\n{result.stdout}\n```")
        else:
            logger.error(f"Failed to install dependencies: {result.stderr}")
            await ctx.send(f"Failed to install dependencies:\n```\n{result.stderr}\n```")
            return

        await ctx.send("Restarting Odin to apply changes...")
        logger.info("Initiating bot restart after dependency installation.")

        await bot.close()
        if bot.http:
            await bot.http.close()

        import sys
        import os
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.error(f"Error during dependency installation or restart: {e}")
        await ctx.send(f"Error during dependency installation or restart: {str(e)}")

@bot.command()
@commands.has_permissions(administrator=True)
async def rename(ctx, old_name: str, new_name: str):
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', new_name):
        await ctx.send("New command name can only contain letters, numbers, underscores, or hyphens.")
        return

    try:
        with open('functions.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        await ctx.send("Error: functions.json not found.")
        return
    except json.JSONDecodeError:
        await ctx.send("Error: functions.json is invalid.")
        return

    command_found = False
    cog_name = None

    bot_commands = data.get("bot_commands", {})
    if old_name in bot_commands:
        description = bot_commands.pop(old_name)
        bot_commands[new_name] = description
        data["bot_commands"] = bot_commands
        command_found = True

    if not command_found:
        cogs = data.get("cogs", {})
        for cog, cog_data in cogs.items():
            commands = cog_data.get("commands", {})
            if old_name in commands:
                description = commands.pop(old_name)
                commands[new_name] = description
                cog_data["commands"] = commands
                cogs[cog] = cog_data
                cog_name = cog
                command_found = True
                break

    if not command_found:
        await ctx.send(f"Command '{old_name}' not found in functions.json.")
        return

    if old_name in ["ping", "info", "help", "cmd_bank"]:
        cog_name = "general"
    elif old_name in ["update", "add_function", "enable_function", "disable_function", "logs", "install_deps", "rename", "change_prefix", "generate_cog"]:
        cog_name = None
    elif old_name == "function_generator":
        cog_name = "function_generator"

    if cog_name and cog_name != "general":
        if new_name != cog_name:
            await ctx.send(f"Command name must match the cog file name '{cog_name}'.py for non-general cogs.")
            return

    for section in [data.get("bot_commands", {})] + [cog_data.get("commands", {}) for cog_data in data.get("cogs", {}).values()]:
        if new_name in section:
            await ctx.send(f"Command '{new_name}' already exists in functions.json.")
            return

    data["cogs"] = cogs

    with open('functions.json', 'w') as f:
        json.dump(data, f, indent=4)

    if cog_name and cog_name != "general":
        try:
            if f'cogs.{cog_name}' in bot.extensions:
                await bot.unload_extension(f'cogs.{cog_name}')
                await bot.load_extension(f'cogs.{cog_name}')
                logger.info(f"Reloaded cog {cog_name} after renaming command.")
            await ctx.send(f"Renamed command '{old_name}' to '{new_name}'. Cog '{cog_name}' reloaded if enabled.")
        except Exception as e:
            logger.error(f"Failed to reload cog {cog_name}: {e}")
            await ctx.send(f"Renamed command '{old_name}' to '{new_name}', but failed to reload cog '{cog_name}': {str(e)}")
    else:
        await ctx.send(f"Renamed command '{old_name}' to '{new_name}'. No cog reload needed.")

@bot.command()
@commands.has_permissions(administrator=True)
async def change_prefix(ctx):
    prefix_options = ['!', '@', '#', '$', '%']
    
    options_message = "Please select a new command prefix by replying with the number:\n"
    for i, prefix in enumerate(prefix_options, 1):
        options_message += f"{i}. {prefix}\n"
    options_message += f"\nCurrent prefix: {bot.command_prefix}"

    await ctx.send(options_message)

    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.isdigit()

    try:
        response = await bot.wait_for('message', check=check, timeout=60)
        choice = int(response.content)

        if 1 <= choice <= len(prefix_options):
            new_prefix = prefix_options[choice - 1]
            
            bot.command_prefix = new_prefix
            
            try:
                with open('config.json', 'r') as f:
                    config_data = json.load(f)
                config_data['prefix'] = new_prefix
                with open('config.json', 'w') as f:
                    json.dump(config_data, f, indent=4)
                await ctx.send(f"Command prefix changed to `{new_prefix}`. Use `{new_prefix}help` for commands.")
            except Exception as e:
                logger.error(f"Failed to update config.json with new prefix: {e}")
                await ctx.send(f"Changed prefix to `{new_prefix}`, but failed to save to config.json: {str(e)}")
        else:
            await ctx.send("Invalid selection. Please run the command again and choose a valid number.")
    except asyncio.TimeoutError:
        await ctx.send("Timed out waiting for your selection. Please run the command again.")

@bot.command()
@commands.has_permissions(administrator=True)
async def generate_cog(ctx, cog_name: str):
    """Placeholder for generating predefined cog files on the server (admin)."""
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', cog_name) or cog_name.startswith('.'):
        await ctx.send("Cog name can only contain letters, numbers, underscores, or hyphens, and cannot start with a period.")
        return

    await ctx.send("This command is a placeholder for generating predefined cogs. No cogs are currently available for automatic generation. Use `!add_function` to create custom cogs.")

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
