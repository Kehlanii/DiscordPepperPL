import logging
import os

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.db import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PepperBot")


class PepperBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.session: aiohttp.ClientSession = None
        self.db = Database()

    async def setup_hook(self):
        """Initialize session with optimized connector, db, load cogs, and sync slash commands."""
        
        connector = aiohttp.TCPConnector(
            limit=50,
            limit_per_host=10,
            ttl_dns_cache=600,
            enable_cleanup_closed=True,
            force_close=False,
        )
        
        timeout = aiohttp.ClientTimeout(
            total=15,
            connect=5,
            sock_read=10,
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'Connection': 'keep-alive',
                'Accept-Encoding': 'gzip, deflate',
            },
        )

        # Initialize Database
        await self.db.init()

        # Load cogs
        try:
            await self.load_extension("cogs.pepper")
            logger.info("Loaded extension: cogs.pepper")

            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s) globally.")

        except Exception as e:
            logger.error(f"Failed to setup bot: {e}", exc_info=True)

    async def close(self):
        """Cleanup session and db on shutdown."""
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        await super().close()

    async def on_ready(self):
        logger.info(f"{self.user} has connected to Discord!")
        logger.info(f"Bot is in {len(self.guilds)} guild(s)")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="Good Bad Girls")
        )

    async def on_command_error(self, ctx, error):
        """Global error handler for legacy commands."""
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing Argument",
                description=f"Usage: `{ctx.prefix}{ctx.command} {ctx.command.signature}`",
                color=0xFF0000,
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"Command error in {ctx.command}: {error}", exc_info=True)
            embed = discord.Embed(
                title="⚠️ Unexpected Error",
                description="An error occurred while processing your command.",
                color=0xFFA500,
            )
            await ctx.send(embed=embed)


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in .env file!")
        return

    bot = PepperBot()

    try:
        bot.run(token)
    except discord.LoginFailure:
        logger.error("Invalid Discord token!")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)


if __name__ == "__main__":
    main()