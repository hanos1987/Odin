# Command to rename a command in commands.json
@bot.command()
@commands.has_permissions(administrator=True)
async def rename(ctx, old_name: str, new_name: str):
    """Renames a command in commands.json (admin)."""
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', new_name):
        await ctx.send("New command name can only contain letters, numbers, underscores, or hyphens.")
        return

    try:
        with open('commands.json', 'r') as f:
            data = json.load(f)
        command_descriptions = data.get("commands", {})
    except FileNotFoundError:
        await ctx.send("Error: commands.json not found.")
        return
    except json.JSONDecodeError:
        await ctx.send("Error: commands.json is invalid.")
        return

    if old_name not in command_descriptions:
        await ctx.send(f"Command '{old_name}' not found in commands.json.")
        return

    if new_name in command_descriptions:
        await ctx.send(f"Command '{new_name}' already exists in commands.json.")
        return

    cog_name = None
    if old_name in ["ping", "info", "help", "cmd_bank"]:
        cog_name = "general"
    elif old_name in ["update", "add_function", "enable_function", "disable_function", "logs", "install_deps", "rename", "change_prefix"]:
        cog_name = None
    elif old_name == "function_generator":
        cog_name = "function_generator"

    if cog_name and cog_name != "general":
        if new_name != cog_name:
            await ctx.send(f"Command name must match the cog file name '{cog_name}'.py for non-general cogs.")
            return

    description = command_descriptions.pop(old_name)
    command_descriptions[new_name] = description
    data["commands"] = command_descriptions

    with open('commands.json', 'w') as f:
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
