"""
Repent - AutoMod System
Message-based automod: anti-spam, anti-invite, anti-mention, anti-caps, bad words, etc.
"""

import re
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

from database import (
    get_automod_config, get_bad_words, get_ignored_channels,
    log_action, get_guild, add_strike, clear_strikes, get_strikes,
)
from utils.embeds import alert_embed, success_embed, error_embed, info_embed
from config import OWNER_ID


INVITE_REGEX = re.compile(r"(discord\.gg\/[a-zA-Z0-9\-]+|discord(?:app)?\.com\/invite\/[a-zA-Z0-9\-]+)", re.IGNORECASE)
URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)
MENTION_REGEX = re.compile(r"<@!?(\d+)>")
ROLE_MENTION_REGEX = re.compile(r"<@&(\d+)>")
EMOJI_REGEX = re.compile(r"<a?:\w+:\d+>")


class SpamTracker:
    """In-memory message rate tracker per guild per user."""

    def __init__(self):
        # {guild_id: {user_id: [(timestamp, message_id, content)]}}
        self._data = defaultdict(lambda: defaultdict(list))
        self._lock = asyncio.Lock()

    async def add(self, guild_id: int, user_id: int, message_id: int, content: str):
        async with self._lock:
            self._data[guild_id][user_id].append((datetime.utcnow(), message_id, content))

    async def check(self, guild_id: int, user_id: int, threshold: int, window: int) -> list:
        """Return list of message IDs to delete if user is spamming."""
        async with self._lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=window)
            entries = [e for e in self._data[guild_id][user_id] if e[0] > cutoff]
            self._data[guild_id][user_id] = entries
            if len(entries) >= threshold:
                return [e[1] for e in entries]
            return []

    async def check_duplicates(self, guild_id: int, user_id: int, limit: int = 3, window: int = 10) -> list:
        """Return list of duplicate message IDs if limit is exceeded."""
        async with self._lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=window)
            entries = [e for e in self._data[guild_id][user_id] if e[0] > cutoff]
            self._data[guild_id][user_id] = entries

            # Group messages by content
            counts = defaultdict(list)
            for timestamp, msg_id, content in entries:
                counts[content].append(msg_id)

            for content, msg_ids in counts.items():
                if len(msg_ids) >= limit:
                    return msg_ids
            return []

    async def cleanup(self):
        """Remove entries older than 60 seconds."""
        async with self._lock:
            cutoff = datetime.utcnow() - timedelta(seconds=60)
            for gid in list(self._data.keys()):
                for uid in list(self._data[gid].keys()):
                    self._data[gid][uid] = [e for e in self._data[gid][uid] if e[0] > cutoff]
                    if not self._data[gid][uid]:
                        del self._data[gid][uid]
                if not self._data[gid]:
                    del self._data[gid]


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spam_tracker = SpamTracker()
        self._cleanup_task = None
        self._alert_cooldowns = {}

    async def cog_load(self):
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def cog_unload(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()

    async def _cleanup_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await asyncio.sleep(30)
            await self.spam_tracker.cleanup()

    async def _should_ignore(self, message: discord.Message, module: str = "automod") -> bool:
        """Check if message should be ignored by AutoMod."""
        if not message.guild:
            return True
        if message.author.id == self.bot.user.id:
            return True
        # Skip normal bots but keep scanning Webhooks
        if message.author.bot and not message.webhook_id:
            return True
        if message.author.guild_permissions.administrator:
            return True  # Admins bypass automod

        settings = await get_guild(message.guild.id)
        if not settings.get("automod_enabled", 1):
            return True

        ignored = await get_ignored_channels(message.guild.id, module)
        if message.channel.id in ignored:
            return True
        return False

    async def _log_automod(self, guild: discord.Guild, rule: str, user: discord.Member | discord.User, content: str, action: str, channel: discord.TextChannel = None):
        """Log automod action with rate-limiting to prevent log channel spam."""
        await log_action(guild.id, "automod", user.id, {
            "rule": rule,
            "content_preview": content[:200],
            "action": action,
        })

        # Cooldown checks: limit logs for the same user + rule to once every 10 seconds
        cooldown_key = (guild.id, user.id, rule)
        now = datetime.utcnow()
        if cooldown_key in self._alert_cooldowns:
            if now < self._alert_cooldowns[cooldown_key] + timedelta(seconds=10):
                return
        self._alert_cooldowns[cooldown_key] = now

        settings = await get_guild(guild.id)
        log_ch_id = settings.get("log_channel", 0)
        if log_ch_id:
            ch = guild.get_channel(log_ch_id)
            if ch:
                ch_mention = channel.mention if channel else "Unknown"
                embed = alert_embed(
                    f"AutoMod: {rule}",
                    f"**User:** {user.mention} (`{user.id}`)\n"
                    f"**Channel:** {ch_mention}\n"
                    f"**Action:** {action}\n"
                    f"**Preview:** {content[:500]}"
                )
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass

    async def _timeout_user(self, member: discord.Member, minutes: int, reason: str):
        try:
            until = datetime.utcnow() + timedelta(minutes=minutes)
            await member.timeout(until, reason=reason)
        except Exception:
            pass

    async def _delete_messages(self, channel: discord.TextChannel, message_ids: list):
        """Bulk delete messages by ID."""
        for mid in message_ids:
            try:
                msg = await channel.fetch_message(mid)
                await msg.delete()
            except Exception:
                pass

    async def _punish_user(self, message: discord.Message, rule: str, reason: str):
        """Escalate strike counts and apply corresponding punishments."""
        guild = message.guild
        author = message.author
        content = message.content

        # ── Webhook Special Handling ──
        if message.webhook_id:
            action = "Webhook Deleted"
            try:
                webhook = await self.bot.fetch_webhook(message.webhook_id)
                if webhook:
                    await webhook.delete(reason=f"[Repent AutoMod] Webhook deleted for rule violation: {reason}")
            except Exception as e:
                action = f"Deleted Webhook Message (Failed deletion: {e})"

            await self._log_automod(guild, rule, author, content, action, message.channel)
            return

        # ── Guild Member Handling ──
        strikes = await add_strike(guild.id, author.id)
        action = ""

        if strikes == 1:
            action = "Warning"
            try:
                await author.send(f"⚠️ **Warning**: You received an AutoMod warning in **{guild.name}** for: {reason}.")
            except Exception:
                pass
            try:
                await message.channel.send(f"{author.mention} Please follow the rules: {reason}.", delete_after=5)
            except Exception:
                pass
        elif strikes == 2:
            action = "Timeout (10m)"
            await self._timeout_user(author, 10, f"[AutoMod] {reason}")
            try:
                await message.channel.send(f"🔇 {author.mention} has been timed out for 10 minutes (Strikes: 2). Reason: {reason}.", delete_after=10)
            except Exception:
                pass
        elif strikes == 3:
            action = "Timeout (1h)"
            await self._timeout_user(author, 60, f"[AutoMod] {reason}")
            try:
                await message.channel.send(f"🔇 {author.mention} has been timed out for 1 hour (Strikes: 3). Reason: {reason}.", delete_after=10)
            except Exception:
                pass
        else:
            action = "Ban"
            try:
                await guild.ban(author, reason=f"[AutoMod] {reason} (Max strikes: {strikes})", delete_message_days=0)
                await clear_strikes(guild.id, author.id)
            except Exception:
                pass
            try:
                await message.channel.send(f"🔨 {author.name} has been banned from the server (Max strikes reached). Reason: {reason}.", delete_after=10)
            except Exception:
                pass

        await self._log_automod(guild, rule, author, content, action, message.channel)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if await self._should_ignore(message):
            return

        guild = message.guild
        author = message.author
        content = message.content
        config = await get_automod_config(guild.id)

        # ── Anti-Spam ──
        if config.get("anti_spam", 1):
            threshold = config.get("spam_threshold", 5)
            window = config.get("spam_window", 5)
            await self.spam_tracker.add(guild.id, author.id, message.id, content)

            # Check message rate
            spam_ids = await self.spam_tracker.check(guild.id, author.id, threshold, window)
            if spam_ids:
                await self._delete_messages(message.channel, spam_ids)
                await self._punish_user(message, "anti_spam", "Spamming messages")
                return

            # Check duplicate content
            dup_ids = await self.spam_tracker.check_duplicates(guild.id, author.id, limit=3, window=10)
            if dup_ids:
                await self._delete_messages(message.channel, dup_ids)
                await self._punish_user(message, "anti_spam_duplicate", "Sending duplicate messages")
                return

            # Check newlines (wall of text)
            if content.count('\n') > 10:
                try:
                    await message.delete()
                except Exception:
                    pass
                await self._punish_user(message, "anti_spam_newlines", "Wall of text (excessive newlines)")
                return

        # ── Anti-Mass-Mention ──
        if config.get("anti_mention", 1) and not (hasattr(author, "guild_permissions") and author.guild_permissions.mention_everyone):
            user_mentions = len(MENTION_REGEX.findall(content))
            role_mentions = len(ROLE_MENTION_REGEX.findall(content))
            total_mentions = user_mentions + role_mentions
            limit = config.get("mention_limit", 5)
            if total_mentions > limit:
                try:
                    await message.delete()
                except Exception:
                    pass
                await self._punish_user(message, "anti_mention", f"Mass mentions ({total_mentions} > {limit})")
                return

        # ── Anti-Invite ──
        if config.get("anti_invite", 1) and not (hasattr(author, "guild_permissions") and author.guild_permissions.manage_guild):
            invites = INVITE_REGEX.findall(content)
            if invites:
                try:
                    await message.delete()
                except Exception:
                    pass
                await self._punish_user(message, "anti_invite", "Posting server invites")
                return

        # ── Anti-Link ──
        if config.get("anti_link", 0) and not (hasattr(author, "guild_permissions") and author.guild_permissions.manage_messages):
            links = URL_REGEX.findall(content)
            if links:
                try:
                    await message.delete()
                except Exception:
                    pass
                await self._punish_user(message, "anti_link", "Posting links")
                return

        # ── Anti-Caps ──
        if config.get("anti_caps", 1) and len(content) >= 10:
            caps_percent = config.get("caps_percent", 70)
            letters = [c for c in content if c.isalpha()]
            if letters and (sum(1 for c in letters if c.isupper()) / len(letters)) * 100 >= caps_percent:
                try:
                    await message.delete()
                except Exception:
                    pass
                await self._punish_user(message, "anti_caps", "Excessive caps")
                return

        # ── Anti-Emoji Spam ──
        if config.get("anti_emoji", 1):
            emojis = EMOJI_REGEX.findall(content)
            if len(emojis) > config.get("emoji_limit", 8):
                try:
                    await message.delete()
                except Exception:
                    pass
                await self._punish_user(message, "anti_emoji", "Excessive emoji spam")
                return

        # ── Bad Word Filter ──
        bad_words = await get_bad_words(guild.id)
        if bad_words:
            lower = content.lower()
            for word in bad_words:
                if word in lower:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    await self._punish_user(message, "bad_word", f"Using forbidden word: {word}")
                    return

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        await self.on_message(after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Anti-Ghost-Ping listener."""
        if not message.guild or message.author.bot:
            return

        # Filter mentions to find non-bots who are not the author
        if message.mentions:
            real_mentions = [m for m in message.mentions if not m.bot and m.id != message.author.id]
            if real_mentions:
                mentions_str = ", ".join(m.mention for m in real_mentions)
                await log_action(message.guild.id, "ghost_ping", message.author.id, {
                    "mentions": [m.id for m in real_mentions],
                    "content": message.content[:200]
                })

                settings = await get_guild(message.guild.id)
                log_ch_id = settings.get("log_channel", 0)
                if log_ch_id:
                    ch = message.guild.get_channel(log_ch_id)
                    if ch:
                        embed = discord.Embed(
                            title="👻 Ghost Ping Detected",
                            description=f"**User:** {message.author.mention} (`{message.author.id}`)\n"
                                        f"**Channel:** {message.channel.mention}\n"
                                        f"**Pinged Users:** {mentions_str}\n"
                                        f"**Content:** {message.content[:500]}",
                            color=0xFFAA00
                        )
                        embed.timestamp = datetime.utcnow()
                        try:
                            await ch.send(embed=embed)
                        except Exception:
                            pass

    # ── AutoMod Slash Commands ──

    @discord.app_commands.command(name="automod", description="Enable or disable automod (Admin only)")
    @discord.app_commands.describe(action="enable or disable")
    async def automod(self, interaction: discord.Interaction, action: str):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        from database import update_guild
        enabled = 1 if action.lower() in ("enable", "on", "true") else 0
        await update_guild(interaction.guild.id, automod_enabled=enabled)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            embed=success_embed("AutoMod Updated", f"AutoMod has been **{status}** in this server."),
            ephemeral=False,
        )

    @discord.app_commands.command(name="badword", description="Add or remove bad words (Admin only)")
    @discord.app_commands.describe(action="add or remove", word="The word to add/remove")
    async def badword(self, interaction: discord.Interaction, action: str, word: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        from database import add_bad_word, remove_bad_word, get_bad_words
        word = word.lower().strip()
        if action.lower() == "add":
            await add_bad_word(interaction.guild.id, word)
            await interaction.response.send_message(
                embed=success_embed("Bad Word Added", f"`{word}` has been added to the filter."),
                ephemeral=False,
            )
        elif action.lower() in ("remove", "delete", "rm"):
            await remove_bad_word(interaction.guild.id, word)
            await interaction.response.send_message(
                embed=success_embed("Bad Word Removed", f"`{word}` has been removed from the filter."),
                ephemeral=False,
            )
        elif action.lower() == "list":
            words = await get_bad_words(interaction.guild.id)
            if not words:
                return await interaction.response.send_message(
                    embed=info_embed("Bad Words", "No bad words configured."), ephemeral=False
                )
            await interaction.response.send_message(
                embed=info_embed("Bad Words", ", ".join(f"`{w}`" for w in words)), ephemeral=False
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Invalid action. Use: add, remove, or list."), ephemeral=True
            )

    @discord.app_commands.command(name="ignore", description="Ignore a channel from automod (Admin only)")
    @discord.app_commands.describe(channel="Channel to ignore", module="Which module to ignore (default: all)")
    async def ignore(self, interaction: discord.Interaction, channel: discord.TextChannel, module: str = "all"):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        from database import add_ignored_channel
        await add_ignored_channel(interaction.guild.id, channel.id, module)
        await interaction.response.send_message(
            embed=success_embed("Channel Ignored", f"{channel.mention} is now ignored for `{module}` automod rules."),
            ephemeral=False,
        )

    @discord.app_commands.command(name="unignore", description="Remove a channel from automod ignore list (Admin only)")
    @discord.app_commands.describe(channel="Channel to unignore")
    async def unignore(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        from database import remove_ignored_channel
        await remove_ignored_channel(interaction.guild.id, channel.id, "all")
        await interaction.response.send_message(
            embed=success_embed("Channel Unignored", f"{channel.mention} is no longer ignored."),
            ephemeral=False,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))
