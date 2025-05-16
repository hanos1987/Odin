
import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

async def setup(bot):
    await bot.add_cog(General(bot))
