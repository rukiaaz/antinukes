"""
Repent - Advanced Discord Antinuke & Security Bot
Entry point. Loads cogs, initializes cache, auto-purges old data.
"""

import os
import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import signal

from config import TOKEN, BOT_NAME, VERSION, OWNER_ID, CACHE_AUTO_SAVE_INTERVAL
from database import init_db, purge_old_data, close_all_connections
from utils.cache import snapshot_guild
from utils.logger import get_logger
from utils.health_check import get_health_checker
from utils.cache_layer import get_cache_layer


class Repent(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        # Members intent required for accurate antinuke + welcome
        # Message content required for automod
        # Audit log required for on_audit_log_entry_create

        super().__init__(
            command_prefix="x",  # Legacy prefix kept for emergencies
            intents=intents,
            owner_id=OWNER_ID,
            help_command=None,
        )
        self.start_time = datetime.now(timezone.utc)
        self.logger = get_logger()
        self._shutdown_event = asyncio.Event()

    async def setup_hook(self):
        # Initialize database
        await init_db()
        await purge_old_data()
        self.logger.info("Database initialized and old data purged")

        # Initialize health checker
        get_health_checker(self)
        self.logger.info("Health checker initialized")
        
        # Initialize cache layer
        cache_layer = get_cache_layer()
        await cache_layer.start()
        self.logger.info("Cache layer initialized")

        # Load all cogs
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(cog_name)
                    self.logger.info(f"Loaded cog: {cog_name}")
                except Exception as e:
                    self.logger.error(f"Failed to load cog {cog_name}", exc_info=True)

        # Sync slash commands
        try:
            await self.tree.sync()
            self.logger.info("Slash commands synced globally")
        except Exception as e:
            self.logger.error(f"Failed to sync commands", exc_info=True)

        # Start background tasks
        self.cache_snapshot_loop.start()
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

    async def on_ready(self):
        self.logger.info("=" * 50)
        self.logger.info(f"{BOT_NAME} v{VERSION} is online!")
        self.logger.info(f"Logged in as: {self.user} ({self.user.id})")
        self.logger.info(f"Owner: {OWNER_ID}")
        self.logger.info(f"Guilds: {len(self.guilds)}")
        self.logger.info(f"Users: {sum(g.member_count for g in self.guilds)}")
        self.logger.info("=" * 50)

        # Initial cache snapshot for all guilds
        for guild in self.guilds:
            try:
                await snapshot_guild(guild)
                self.logger.info(f"Snapshotted guild: {guild.name} ({guild.id})")
            except Exception as e:
                self.logger.error(f"Failed to snapshot guild {guild.id}", exc_info=True)

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | xhelp"
            ),
            status=discord.Status.online,
        )

    async def on_guild_join(self, guild: discord.Guild):
        """Cache newly joined guild immediately."""
        try:
            await snapshot_guild(guild)
            self.logger.info(f"Joined and cached guild: {guild.name} ({guild.id})")
        except Exception as e:
            self.logger.error(f"Failed to cache guild {guild.id}", exc_info=True)

        # Notify owner
        try:
            owner = await self.fetch_user(OWNER_ID)
            if owner:
                embed = discord.Embed(
                    title="📥 New Server",
                    description=f"**{guild.name}** (`{guild.id}`)\nMembers: {guild.member_count}",
                    color=0x44FF88,
                )
                await owner.send(embed=embed)
        except Exception as e:
            self.logger.error("Failed to notify owner of new guild", exc_info=True)

    async def on_guild_remove(self, guild: discord.Guild):
        self.logger.info(f"Left guild: {guild.name} ({guild.id})")

    async def on_member_join(self, member: discord.Member):
        """Check hardbans immediately on join."""
        from database import is_hardbanned
        if await is_hardbanned(member.guild.id, member.id):
            try:
                await member.guild.ban(
                    member,
                    reason="[Repent] Hardban — auto reban on rejoin",
                    delete_message_days=0,
                )
                self.logger.security("HARDBAN_REBAN", f"Re-banned user {member.id}", guild_id=member.guild.id, user_id=member.id)
            except Exception as e:
                self.logger.error(f"Failed to reban hardbanned user {member.id}", exc_info=True)

    # ── Cache snapshot loop ──
    @tasks.loop(seconds=CACHE_AUTO_SAVE_INTERVAL)
    async def cache_snapshot_loop(self):
        for guild in self.guilds:
            try:
                await snapshot_guild(guild)
            except Exception as e:
                self.logger.error(f"Failed to snapshot guild {guild.id} in loop", exc_info=True)

    @cache_snapshot_loop.before_loop
    async def before_cache_loop(self):
        await self.wait_until_ready()

    # ── Error Handlers ──
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        self.logger.command_error(str(ctx.command), ctx.author.id, str(error))

    async def on_tree_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Permission Denied",
                    description=str(error),
                    color=0xFF4444,
                ),
                ephemeral=True,
            )
        else:
            self.logger.command_error(str(interaction.command), interaction.user.id, str(error))
            try:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="An unexpected error occurred. The issue has been logged.",
                        color=0xFF4444,
                    ),
                    ephemeral=True,
                )
            except Exception:
                pass

    # ── Graceful Shutdown ──
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        try:
            import signal
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except Exception as e:
            self.logger.error(f"Failed to setup signal handlers: {e}")

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
        # Set the shutdown event in a thread-safe way
        self.loop.call_soon_threadsafe(self._shutdown_event.set)

    async def shutdown(self):
        """Perform graceful shutdown."""
        self.logger.info("Starting graceful shutdown")
        
        try:
            # Cancel background tasks
            self.cache_snapshot_loop.cancel()
            
            # Stop cache layer
            cache_layer = get_cache_layer()
            await cache_layer.stop()
            self.logger.info("Cache layer stopped")
            
            # Close database connections
            await close_all_connections()
            self.logger.info("Database connections closed")
            
            # Close Discord connection
            await self.close()
            self.logger.info("Discord connection closed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            self.logger.info("Graceful shutdown complete")


# ── Run ──
if __name__ == "__main__":
    if not TOKEN:
        print("[FATAL] DISCORD_TOKEN not found. Set it in your .env file.")
        exit(1)
    if OWNER_ID == 0:
        print("[WARN] OWNER_ID not set. Some features will be restricted.")

    bot = Repent()
    try:
        bot.run(TOKEN, reconnect=True)
    except Exception as e:
        print(f"[FATAL] Failed to start bot: {e}")
