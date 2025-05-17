import discord
from discord.ext import commands
import json
import os

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._register_commands()

    def _register_commands(self):
        """Register this cog's commands in commands.json."""
        commands_to_register = {
            "ping": "Check the bot's latency.",
            "info": "Display bot information.",
            "help": "Shows the help message.",
            "cmd_bank": "Lists all available commands with their descriptions."
        }
        try:
            try:
                with open('commands.json', 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {"commands": {}}

            # Update commands.json with this cog's commands
            data["commands"].update(commands_to_register)
            with open('commands.json', 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Failed to register commands for General cog: {e}")

    @commands.command()
    async def ping(self, ctx):
        """Check the bot's latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f'Pong! Latency: {latency}ms')

    @commands.command()
    async def info(self, ctx):
        """Display bot information."""
        embed = discord.Embed(title="Bot Info", color=discord.Color.blue())
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Prefix", value=ctx.prefix, inline=True)
        embed.set_footer(text=f"Created by {ctx.bot.user.name}")
        await ctx.send(embed=embed)

    @commands.command()
    async def help(self, ctx):
        """Shows this help message."""
        embed = discord.Embed(title="Odin Help", color=discord.Color.green())
        embed.add_field(
            name="Available Commands",
            value=f"Use `{ctx.prefix}cmd_bank` to see all available commands and their descriptions.",
            inline=False
        )
        embed.set_footer(text=f"Prefix: {ctx.prefix}")
        await ctx.send(embed=embed)

    @commands.command()
    async def cmd_bank(self, ctx):
        """Lists all available commands with their descriptions."""
        # Load command descriptions from commands.json
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

        # Load server-specific cog configuration
        server_cogs = []
        if ctx.guild:
            config_path = f'./server_configs/{ctx.guild.id}.json'
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                server_cogs = config_data.get('cogs', [])
            except FileNotFoundError:
                server_cogs = []

        embed = discord.Embed(title="Odin Command Bank", color=discord.Color.purple())
        
        # Get all commands from commands.json
        commands_list = []
        for cmd_name, cmd_desc in command_descriptions.items():
            # Determine if the command's cog is enabled
            # Map commands to their cogs (based on Odin's structure)
            cog_name = None
            if cmd_name in ["ping", "info", "help", "cmd_bank"]:
                cog_name = "general"  # General cog commands
            elif cmd_name in ["update", "add_function", "enable_function", "disable_function", "logs", "install_deps"]:
                cog_name = None  # Bot-level commands (not in a cog)
            elif cmd_name == "generate_program":
                cog_name = "program_generator"  # ProgramGenerator cog
            # Add more mappings as new cogs are added

            # Determine status
            if cog_name is None:
                status = ""  # Bot-level commands are always available
            elif cog_name == "general":
                status = "* (enabled)*"  # General cog is always enabled
            else:
                status = "* (enabled)*" if cog_name in server_cogs else "* (disabled)*"

            commands_list.append((cmd_name, cmd_desc, status))
        
        # Sort commands alphabetically
        commands_list.sort(key=lambda x: x[0])
        
        # Add commands to the embed
        for cmd_name, cmd_desc, status in commands_list:
            embed.add_field(
                name=f"{ctx.prefix}{cmd_name} {status}",
                value=cmd_desc,
                inline=False
            )
        
        embed.set_footer(text=f"Total Commands: {len(commands_list)}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))
