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
intents.dm_messages = True  # Enable DM message events
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
@commands.has_permissions(administrator=True)
async def function_update(ctx):
    """Reloads cogs based on functions.json."""
    await ctx.send("Updating cogs from functions.json...")
    await load_cogs_from_json()
    await ctx.send("Cog update complete!")

# Command to add a new cog via DM
@bot.command()
@commands.has_permissions(administrator=True)
async def add_function(ctx, cog_name: str):
    """Initiates adding a new cog by DMing the invoker for the code."""
    # Validate cog name
    if not cog_name.isalnum():
        await ctx.send("Cog name must be alphanumeric (letters and numbers only).")
        return
    if os.path.exists(f'./cogs/{cog_name}.py'):
        await ctx.send(f"A cog named '{cog_name}' already exists. Choose a different name.")
        return

    # DM the invoker
    try:
        await ctx.author.send(f"Please reply with the `.py` code for the cog named '{cog_name}'. Wrap the code in triple backticks (```) like this:\n```\n# Your code here\n```")
        await ctx.send("I’ve sent you a DM. Please reply there with the cog code.")
    except discord.Forbidden:
        await ctx.send("I couldn’t DM you. Please enable DMs from server members.")
        return

    # Wait for the invoker's reply in DM
    def check(msg):
        return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

    try:
        msg = await bot.wait_for('message', check=check, timeout=300)  # 5-minute timeout
        content = msg.content.strip()
        
        # Check if the message contains code wrapped in triple backticks
        if content.startswith('```') and content.endswith('```'):
            # Extract the code (remove the backticks)
            code = content[3:-3].strip()
            if not code:
                await ctx.author.send("The code you provided is empty. Please try again.")
                return

            # Save the code to a file in the cogs directory
            with open(f'./cogs/{cog_name}.py', 'w') as f:
                f.write(code)
            logger.info(f'Saved new cog file: cogs/{cog_name}.py')

            # Update functions.json
            try:
                with open('functions.json', 'r') as f:
                    data = json.load(f)
                cogs_list = data.get('cogs', [])
                if cog_name not in cogs_list:
                    cogs_list.append(cog_name)
                    data['cogs'] = cogs_list
                    with open('functions.json', 'w') as f:
                        json.dump(data, f, indent=4)
                logger.info(f'Updated functions.json with new cog: {cog_name}')
            except Exception as e:
                logger.error(f'Failed to update functions.json: {e}')
                await ctx.author.send("Failed to update functions.json. Cog file saved, but you’ll need to manually add it to functions.json.")
                return

            # Load the new cog
            try:
                await bot.load_extension(f'cogs.{cog_name}')
                logger.info(f'Loaded new cog: cogs.{cog_name}')
                await ctx.author.send(f"Successfully added and loaded the cog '{cog_name}'!")
            except Exception as e:
                logger.error(f'Failed to load new cog {cog_name}: {e}')
                await ctx.author.send(f"Failed to load the cog '{cog_name}'. Check the code for errors. The file has been saved to the cogs directory.")
        else:
            await ctx.author.send("Please wrap your code in triple backticks (```). Try again.")
    except asyncio.TimeoutError:
        await ctx.author.send("Timed out waiting for your reply. Please use `!add_function` again.")

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
