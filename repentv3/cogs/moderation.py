"""
Repent - Moderation System
Full slash command suite for server moderation.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone

from config import OWNER_ID
from database import (
    add_warning, get_warnings, clear_warnings,
    add_hardban, remove_hardban, is_hardbanned,
    log_action,
)
from utils.embeds import (
    success_embed, error_embed, info_embed,
    mod_action_embed, warning_embed,
)
from utils.rate_limiter import rate_limit_cooldown
from utils.validation import ValidationUtils, ValidationError


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Ban ──
    @app_commands.command(name="ban", description="Ban a user from the server")
    @rate_limit_cooldown(rate=5, per=60)  # 5 bans per minute
    @app_commands.describe(
        user="User to ban",
        reason="Reason for ban",
        delete_days="Message history to delete (0-7)",
    )
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason", delete_days: int = 0):
        if not interaction.user.guild_permissions.ban_members and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You need Ban Members permission."), ephemeral=True)
        if user.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You cannot ban this user (higher/equal role)."), ephemeral=True)
        if user.id == self.bot.user.id:
            return await interaction.response.send_message(embed=error_embed("I cannot ban myself."), ephemeral=True)

        delete_days = max(0, min(7, delete_days))
        await interaction.guild.ban(user, reason=f"{interaction.user}: {reason}", delete_message_days=delete_days)
        await log_action(interaction.guild.id, "ban", user.id, {"reason": reason, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=mod_action_embed("Ban", interaction.user, user, reason, 0xFF4444),
            ephemeral=False,
        )

    # ── Unban ──
    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="User ID to unban", reason="Reason")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason"):
        if not interaction.user.guild_permissions.ban_members and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You need Ban Members permission."), ephemeral=True)
        
        try:
            uid = ValidationUtils.validate_user_id(user_id)
            reason = ValidationUtils.validate_reason(reason)
        except ValidationError as e:
            return await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)

        user = discord.Object(id=uid)
        await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
        await log_action(interaction.guild.id, "unban", uid, {"reason": reason, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=success_embed("Unban", f"<@{uid}> has been unbanned.\n**Reason:** {reason}"),
            ephemeral=False,
        )

    # ── Kick ──
    @app_commands.command(name="kick", description="Kick a user from the server")
    @rate_limit_cooldown(rate=10, per=60)  # 10 kicks per minute
    @app_commands.describe(user="User to kick", reason="Reason")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
        if not interaction.user.guild_permissions.kick_members and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You need Kick Members permission."), ephemeral=True)
        if user.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You cannot kick this user."), ephemeral=True)

        await user.kick(reason=f"{interaction.user}: {reason}")
        await log_action(interaction.guild.id, "kick", user.id, {"reason": reason, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=mod_action_embed("Kick", interaction.user, user, reason, 0xFFAA00),
            ephemeral=False,
        )

    # ── Timeout ──
    @app_commands.command(name="timeout", description="Timeout a user")
    @app_commands.describe(
        user="User to timeout",
        duration="Duration (e.g., 10m, 1h, 1d)",
        reason="Reason",
    )
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, duration: str, reason: str = "No reason"):
        if not interaction.user.guild_permissions.moderate_members and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You need Moderate Members permission."), ephemeral=True)
        if user.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You cannot timeout this user."), ephemeral=True)

        try:
            seconds, unit = ValidationUtils.validate_duration(duration)
            reason = ValidationUtils.validate_reason(reason)
        except ValidationError as e:
            return await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)

        until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        await user.timeout(until, reason=f"{interaction.user}: {reason}")
        await log_action(interaction.guild.id, "timeout", user.id, {"reason": reason, "duration": duration, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=mod_action_embed("Timeout", interaction.user, user, f"{reason} ({duration})", 0xFFAA00),
            ephemeral=False,
        )

    # ── Untimeout ──
    @app_commands.command(name="untimeout", description="Remove timeout from a user")
    @app_commands.describe(user="User to untimeout")
    async def untimeout(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.moderate_members and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You need Moderate Members permission."), ephemeral=True)

        await user.timeout(None, reason=f"{interaction.user}: Timeout removed")
        await log_action(interaction.guild.id, "untimeout", user.id, {"moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=success_embed("Timeout Removed", f"{user.mention}'s timeout has been removed."),
            ephemeral=False,
        )

    # ── Warn ──
    @app_commands.command(name="warn", description="Warn a user")
    @app_commands.describe(user="User to warn", reason="Reason")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
        if not interaction.user.guild_permissions.manage_messages and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You need Manage Messages permission."), ephemeral=True)

        warn_id = await add_warning(interaction.guild.id, user.id, reason, interaction.user.id)
        await log_action(interaction.guild.id, "warn", user.id, {"reason": reason, "warn_id": warn_id, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=warning_embed("Warning Issued", f"{user.mention} has been warned.\n**ID:** `{warn_id}`\n**Reason:** {reason}"),
            ephemeral=False,
        )

    # ── Warnings ──
    @app_commands.command(name="warnings", description="List warnings for a user")
    @app_commands.describe(user="User to check")
    async def warnings(self, interaction: discord.Interaction, user: discord.Member):
        warns = await get_warnings(interaction.guild.id, user.id)
        if not warns:
            return await interaction.response.send_message(
                embed=info_embed("Warnings", f"{user.mention} has no warnings."), ephemeral=False
            )
        lines = []
        for w in warns[:10]:
            mod = interaction.guild.get_member(w["warned_by"])
            mod_mention = mod.mention if mod else f"<@{w['warned_by']}>"
            lines.append(f"`#{w['id']}` — {w['reason'][:60]} — by {mod_mention}")
        await interaction.response.send_message(
            embed=info_embed(f"Warnings for {user.display_name} ({len(warns)} total)", "\n".join(lines)),
            ephemeral=False,
        )

    # ── Clear Warnings ──
    @app_commands.command(name="clearwarns", description="Clear all warnings for a user")
    @app_commands.describe(user="User to clear")
    async def clearwarns(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.manage_messages and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Messages required."), ephemeral=True)

        await clear_warnings(interaction.guild.id, user.id)
        await log_action(interaction.guild.id, "clearwarns", user.id, {"moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=success_embed("Warnings Cleared", f"All warnings for {user.mention} have been cleared."),
            ephemeral=False,
        )

    # ── Purge ──
    @app_commands.command(name="purge", description="Delete recent messages")
    @rate_limit_cooldown(rate=3, per=60)  # 3 purges per minute
    @app_commands.describe(amount="Number of messages (1-100)")
    async def purge(self, interaction: discord.Interaction, amount: int):
        if not interaction.user.guild_permissions.manage_messages and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Messages required."), ephemeral=True)

        amount = max(1, min(100, amount))
        await interaction.response.defer(thinking=True, ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(
            embed=success_embed("Purge", f"Deleted **{len(deleted)}** message(s)."),
            ephemeral=True,
        )

    # ── Purge User ──
    @app_commands.command(name="purgeuser", description="Delete messages from a specific user")
    @rate_limit_cooldown(rate=3, per=60)  # 3 purges per minute
    @app_commands.describe(user="User to purge", amount="Number of messages to check (1-100)")
    async def purgeuser(self, interaction: discord.Interaction, user: discord.Member, amount: int = 50):
        if not interaction.user.guild_permissions.manage_messages and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Messages required."), ephemeral=True)

        amount = max(1, min(100, amount))
        await interaction.response.defer(thinking=True, ephemeral=True)

        def check(m):
            return m.author.id == user.id

        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(
            embed=success_embed("Purge User", f"Deleted **{len(deleted)}** message(s) from {user.mention}."),
            ephemeral=True,
        )

    # ── Lock ──
    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.describe(channel="Channel to lock (default: current)")
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Channels required."), ephemeral=True)

        channel = channel or interaction.channel
        everyone = interaction.guild.default_role
        overwrite = channel.overwrites_for(everyone)
        overwrite.send_messages = False
        await channel.set_permissions(everyone, overwrite=overwrite, reason=f"{interaction.user}: Channel locked")
        await log_action(interaction.guild.id, "lock", 0, {"channel": channel.id, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=success_embed("Channel Locked", f"{channel.mention} has been locked."),
            ephemeral=False,
        )

    # ── Unlock ──
    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock (default: current)")
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Channels required."), ephemeral=True)

        channel = channel or interaction.channel
        everyone = interaction.guild.default_role
        overwrite = channel.overwrites_for(everyone)
        overwrite.send_messages = True
        await channel.set_permissions(everyone, overwrite=overwrite, reason=f"{interaction.user}: Channel unlocked")
        await log_action(interaction.guild.id, "unlock", 0, {"channel": channel.id, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=success_embed("Channel Unlocked", f"{channel.mention} has been unlocked."),
            ephemeral=False,
        )

    # ── Slowmode ──
    @app_commands.command(name="slowmode", description="Set slowmode for a channel")
    @app_commands.describe(seconds="Seconds of slowmode (0 to disable)", channel="Channel (default: current)")
    async def slowmode(self, interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Channels required."), ephemeral=True)

        channel = channel or interaction.channel
        seconds = max(0, min(21600, seconds))
        await channel.edit(slowmode_delay=seconds, reason=f"{interaction.user}: Slowmode set")
        status = f"**{seconds}s** slowmode" if seconds else "Slowmode disabled"
        await interaction.response.send_message(
            embed=success_embed("Slowmode Updated", f"{channel.mention}: {status}"),
            ephemeral=False,
        )

    # ── Nick ──
    @app_commands.command(name="nick", description="Change a user's nickname")
    @app_commands.describe(user="User", nickname="New nickname (blank to reset)")
    async def nick(self, interaction: discord.Interaction, user: discord.Member, nickname: str = None):
        if not interaction.user.guild_permissions.manage_nicknames and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Nicknames required."), ephemeral=True)

        await user.edit(nick=nickname, reason=f"{interaction.user}: Nick changed")
        await interaction.response.send_message(
            embed=success_embed("Nickname Updated", f"{user.mention}'s nickname set to `{nickname or 'None'}`"),
            ephemeral=False,
        )

    # ── Role Add ──
    @app_commands.command(name="roleadd", description="Add a role to a user")
    @app_commands.describe(user="User", role="Role to add")
    async def roleadd(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        if not interaction.user.guild_permissions.manage_roles and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Roles required."), ephemeral=True)
        if role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You cannot assign this role (higher/equal to yours)."), ephemeral=True)

        await user.add_roles(role, reason=f"{interaction.user}: Role add")
        await interaction.response.send_message(
            embed=success_embed("Role Added", f"Added {role.mention} to {user.mention}."),
            ephemeral=False,
        )

    # ── Role Remove ──
    @app_commands.command(name="roleremove", description="Remove a role from a user")
    @app_commands.describe(user="User", role="Role to remove")
    async def roleremove(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        if not interaction.user.guild_permissions.manage_roles and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Manage Roles required."), ephemeral=True)
        if role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("You cannot remove this role."), ephemeral=True)

        await user.remove_roles(role, reason=f"{interaction.user}: Role remove")
        await interaction.response.send_message(
            embed=success_embed("Role Removed", f"Removed {role.mention} from {user.mention}."),
            ephemeral=False,
        )

    # ── Hardban ──
    @app_commands.command(name="hardban", description="Ban a user and add to hardban list (auto-reban on rejoin)")
    @app_commands.describe(user="User to hardban", reason="Reason")
    async def hardban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
        if not interaction.user.guild_permissions.ban_members and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Ban Members required."), ephemeral=True)

        await add_hardban(interaction.guild.id, user.id, reason, interaction.user.id)
        await interaction.guild.ban(user, reason=f"[Hardban] {interaction.user}: {reason}", delete_message_days=0)
        await log_action(interaction.guild.id, "hardban", user.id, {"reason": reason, "moderator": interaction.user.id})
        await interaction.response.send_message(
            embed=mod_action_embed("Hardban", interaction.user, user, reason, 0xFF4444),
            ephemeral=False,
        )

    @app_commands.command(name="unhardban", description="Remove a user from the hardban list")
    @app_commands.describe(user_id="User ID to unhardban")
    async def unhardban(self, interaction: discord.Interaction, user_id: str):
        if not interaction.user.guild_permissions.ban_members and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Ban Members required."), ephemeral=True)
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(embed=error_embed("Invalid user ID."), ephemeral=True)

        await remove_hardban(interaction.guild.id, uid)
        try:
            user = discord.Object(id=uid)
            await interaction.guild.unban(user, reason=f"{interaction.user}: Unhardbanned")
        except Exception:
            pass
        await interaction.response.send_message(
            embed=success_embed("Unhardbanned", f"<@{uid}> has been removed from the hardban list."),
            ephemeral=False,
        )

    # ── Duration Parser ──
async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
