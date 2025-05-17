import discord
from discord.ext import commands
import json

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

        embed = discord.Embed(title="Odin Command Bank", color=discord.Color.purple())
        
        # Get all commands the user can run
        commands_list = []
        for command in self.bot.commands:
            if await command.can_run(ctx):
                description = command_descriptions.get(command.name, "No description available.")
                commands_list.append((command.name, description))
        
        # Sort commands alphabetically
        commands_list.sort(key=lambda x: x[0])
        
        # Add commands to the embed
        for cmd_name, cmd_desc in commands_list:
            embed.add_field(
                name=f"{ctx.prefix}{cmd_name}",
                value=cmd_desc,
                inline=False
            )
        
        embed.set_footer(text=f"Total Commands: {len(commands_list)}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))
