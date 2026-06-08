"""
Repent - Advanced Discord Antinuke & Security Bot
Entry point. Loads cogs, initializes cache, auto-purges old data.
"""

import os
import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime

from config import TOKEN, BOT_NAME, VERSION, OWNER_ID, CACHE_AUTO_SAVE_INTERVAL
from database import init_db, purge_old_data
from utils.cache import snapshot_guild


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
        self.start_time = datetime.utcnow()

    async def setup_hook(self):
        # Initialize database
        await init_db()
        await purge_old_data()
        print(f"[DB] Initialized and purged old data.")

        # Load all cogs
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(cog_name)
                    print(f"[COG] Loaded: {cog_name}")
                except Exception as e:
                    print(f"[COG] Failed to load {cog_name}: {e}")

        # Sync slash commands
        try:
            await self.tree.sync()
            print(f"[SYNC] Slash commands synced globally.")
        except Exception as e:
            print(f"[SYNC] Failed to sync commands: {e}")

        # Start background tasks
        self.cache_snapshot_loop.start()

    async def on_ready(self):
        print(f"═" * 50)
        print(f"  {BOT_NAME} v{VERSION} is online!")
        print(f"  Logged in as: {self.user} ({self.user.id})")
        print(f"  Owner: {OWNER_ID}")
        print(f"  Guilds: {len(self.guilds)}")
        print(f"  Users: {sum(g.member_count for g in self.guilds)}")
        print(f"═" * 50)

        # Initial cache snapshot for all guilds
        for guild in self.guilds:
            try:
                await snapshot_guild(guild)
                print(f"[CACHE] Snapshotted: {guild.name} ({guild.id})")
            except Exception as e:
                print(f"[CACHE] Failed to snapshot {guild.id}: {e}")

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
            print(f"[JOIN] Joined and cached: {guild.name} ({guild.id})")
        except Exception as e:
            print(f"[JOIN] Failed to cache {guild.id}: {e}")

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
        except Exception:
            pass

    async def on_guild_remove(self, guild: discord.Guild):
        print(f"[LEAVE] Left: {guild.name} ({guild.id})")

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
                print(f"[HARDBAN] Re-banned {member.id} in {member.guild.id}")
            except Exception as e:
                print(f"[HARDBAN] Failed to reban {member.id}: {e}")

    # ── Cache snapshot loop ──
    @tasks.loop(seconds=CACHE_AUTO_SAVE_INTERVAL)
    async def cache_snapshot_loop(self):
        for guild in self.guilds:
            try:
                await snapshot_guild(guild)
            except Exception:
                pass

    @cache_snapshot_loop.before_loop
    async def before_cache_loop(self):
        await self.wait_until_ready()

    # ── Error Handlers ──
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        print(f"[CMD ERROR] {ctx.command}: {error}")

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
            print(f"[SLASH ERROR] {interaction.command}: {error}")
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
