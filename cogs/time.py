from discord.ext import commands
import pytz
from datetime import datetime
import asyncio
import os
import sys
import subprocess
import logging

logger = logging.getLogger('Leobot')

class Time(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Time cog initialized")

    @commands.command(name="time")
    async def world_time(self, ctx):
        logger.info(f"Command !time received from {ctx.author.name} (ID: {ctx.author.id}) in channel {ctx.channel.name} (ID: {ctx.channel.id})")
        timezones = {
            "Chicago": "America/Chicago",
            "New York": "America/New_York",
            "London": "Europe/London",
            "Belgium": "Europe/Brussels",
            "Athens": "Europe/Athens",
            "Hong Kong": "Asia/Hong_Kong",
            "Hawaii": "Pacific/Honolulu",
            "Sydney": "Australia/Sydney",
        }
        time_messages = []
        for city, tz in timezones.items():
            timezone = pytz.timezone(tz)
            current_time = datetime.now(timezone).strftime("%H:%M:%S %Z on %B %d, %Y")
            time_messages.append(f"{city}: {current_time}")
        await ctx.send("\n".join(time_messages))
        logger.info(f"Successfully sent times for {', '.join(timezones.keys())}")

    @commands.command()
    async def reboot(self, ctx):
        if ctx.author.id not in {1131932116242939975, 1314875665996185613}:
            await ctx.send("Only admins can use this command!")
            return
        logger.info(f"Command !reboot invoked by {ctx.author.name} (ID: {ctx.author.id}) in channel {ctx.channel.name} (ID: {ctx.channel.id})")
        await ctx.send("Rebooting LeoBot... I'll be back in a moment!")
        logger.info("Reboot command received. Logging out and restarting...")

        for cog_name, cog in self.bot.cogs.items():
            if hasattr(cog, 'cleanup'):
                try:
                    logger.info(f"Calling cleanup for cog: {cog_name}")
                    await cog.cleanup()
                except Exception as e:
                    logger.error(f"Error during cleanup of {cog_name}: {e}")

        logger.info("Closing bot connection...")
        try:
            await self.bot.close()
            logger.info("Bot connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing bot connection: {e}")

        await asyncio.sleep(1)
        logger.info("Closing event loop...")
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.close()
                logger.info("Event loop closed successfully")
            else:
                logger.info("Event loop was already closed")
        except Exception as e:
            logger.error(f"Error closing event loop: {e}")

        logger.info("Attempting to restart the bot using subprocess...")
        try:
            subprocess.Popen([sys.executable, sys.argv[0]] + sys.argv[1:], cwd=os.getcwd())
            logger.info("New bot instance started successfully")
        except Exception as e:
            logger.error(f"Failed to start new bot instance: {e}")
            raise SystemExit("Restart failed. Please restart the bot manually")

        logger.info("Exiting current process...")
        sys.exit(0)

    async def cleanup(self):
        logger.info("Time cog cleanup complete (no resources to close)")

async def setup(bot):
    logger.info("Loading Time cog")
    await bot.add_cog(Time(bot))
    logger.info("Time cog loaded")
