"""Repent - Enhanced Anti-Raid System

Advanced raid protection with quarantine, account age filtering, webhook alerts, and raid scoring.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set, Optional
from collections import deque

import discord
from discord import app_commands
from discord.ext import commands

from database import get_guild, update_guild, log_raid_start, log_raid_end, log_action
from utils.embeds import error_embed, info_embed, success_embed
from config import OWNER_ID, DEFAULT_PUNISHMENT


class EnhancedAntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.join_tracker: Dict[int, deque[datetime]] = {}
        self.active_raids: Dict[int, dict] = {}
        self.raid_scores: Dict[int, Dict[int, int]] = {}  # guild_id -> user_id -> score
        self.logger = None

    async def cog_load(self):
        from utils.logger import get_logger
        self.logger = get_logger()

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator or interaction.user.id == OWNER_ID

    async def _resolve_channel(self, guild: discord.Guild, value: str):
        if not value:
            return None
        value = value.strip()
        if value.startswith("<") and value.endswith(">"):
            value = value.strip("<#>")
        try:
            cid = int(value)
            return guild.get_channel(cid)
        except ValueError:
            for ch in guild.channels:
                if ch.name.lower() == value.lower():
                    return ch
        return None

    async def _resolve_role(self, guild: discord.Guild, value: str):
        if not value:
            return None
        value = value.strip()
        if value.startswith("<") and value.endswith(">"):
            value = value.strip("<@&>")
        try:
            rid = int(value)
            return guild.get_role(rid)
        except ValueError:
            for r in guild.roles:
                if r.name.lower() == value.lower():
                    return r
        return None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Enhanced member join handler with raid detection and quarantine."""
        guild = member.guild
        guild_id = guild.id

        # Initialize guild tracking if needed
        if guild_id not in self.join_tracker:
            self.join_tracker[guild_id] = deque()
            self.raid_scores[guild_id] = {}

        # Add to join tracker
        self.join_tracker[guild_id].append(datetime.now(timezone.utc))

        # Get guild settings
        settings = await get_guild(guild_id)
        raid_threshold = settings.get("raid_join_threshold", 10)
        raid_window = settings.get("raid_join_window", 10)
        sensitivity = settings.get("raid_sensitivity_level", 5)
        auto_mode = settings.get("raid_auto_mode", 0)
        account_age_days = settings.get("raid_account_age", 7)
        quarantine_ch_id = settings.get("raid_quarantine_channel", 0)

        # Calculate raid score for this user
        raid_score = 0
        if (datetime.now(timezone.utc) - member.created_at).days < account_age_days:
            raid_score += 3  # New account
        if not member.avatar:
            raid_score += 1  # No avatar
        if member.default_avatar:
            raid_score += 1  # Default avatar
        if len(member.name) < 3 or any(c in member.name for c in ['_.', '-', '0123456789']):
            raid_score += 2  # Suspicious username pattern

        self.raid_scores[guild_id][member.id] = raid_score

        # Check for raid conditions
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=raid_window)
        self.join_tracker[guild_id] = deque([t for t in self.join_tracker[guild_id] if t > cutoff])

        join_count = len(self.join_tracker[guild_id])

        # Account age check
        if (datetime.now(timezone.utc) - member.created_at).days < account_age_days:
            if settings.get("raid_mode", 0) or auto_mode:
                try:
                    await member.kick(reason=f"[Repent Anti-Raid] Account too new: {member.created_at}")
                    if self.logger:
                        self.logger.raid_action("ACCOUNT_AGE_KICK", f"Kicked {member.id} for new account", guild_id=guild_id)
                    
                    # Send webhook alert if configured
                    webhook_url = settings.get("raid_webhook_url", "")
                    if webhook_url:
                        await self._send_webhook_alert(webhook_url, "Account Age Kick", member, "Account too new")
                    
                    return
                except Exception:
                    pass

        # Quarantine suspicious users
        if raid_score >= (10 - sensitivity) and quarantine_ch_id:
            quarantine_ch = guild.get_channel(quarantine_ch_id)
            if quarantine_ch:
                try:
                    await member.move_to(quarantine_ch, reason="[Repent Anti-Raid] Quarantined suspicious user")
                    if self.logger:
                        self.logger.raid_action("QUARANTINE", f"Quarantined {member.id} (score: {raid_score})", guild_id=guild_id)
                    
                    # Send webhook alert
                    webhook_url = settings.get("raid_webhook_url", "")
                    if webhook_url:
                        await self._send_webhook_alert(webhook_url, "User Quarantined", member, f"Raid score: {raid_score}")
                except Exception:
                    pass

        # Trigger raid mode if threshold exceeded
        if join_count >= raid_threshold and not settings.get("raid_mode", 0):
            if auto_mode:
                await update_guild(guild_id, raid_mode=1)
                await log_raid_start(guild_id, join_count, settings.get("raid_mode", 0))
                
                if self.logger:
                    self.logger.raid_start(guild_id, join_count)
                
                # Send webhook alert
                webhook_url = settings.get("raid_webhook_url", "")
                if webhook_url:
                    await self._send_webhook_alert(webhook_url, "Raid Mode Activated", None, f"{join_count} joins in {raid_window}s")

    async def _send_webhook_alert(self, webhook_url: str, title: str, member: discord.Member = None, description: str = ""):
        """Send raid alert via webhook."""
        try:
            webhook = discord.SyncWebhook.from_url(webhook_url)
            embed = discord.Embed(
                title=f"🚨 {title}",
                description=description,
                color=0xFF4444,
                timestamp=datetime.now(timezone.utc)
            )
            if member:
                embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
                embed.add_field(name="Account Age", value=f"{(datetime.now(timezone.utc) - member.created_at).days} days", inline=True)
                embed.add_field(name="Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
            embed.set_footer(text="Repent Anti-Raid System")
            webhook.send(embed=embed)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to send webhook alert: {e}")

    # ── Anti-Raid Commands ──
    @app_commands.command(name="raid", description="Manage anti-raid configuration (Admin only)")
    @app_commands.describe(action="status, toggle, config, unlock, sensitivity, maxjoins, minage, quarantine, webhook")
    async def raid(self, interaction: discord.Interaction, action: str, value: str = None):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        action_l = action.lower().strip()

        if action_l == "status":
            settings = await get_guild(guild.id)
            embed = discord.Embed(title="🚨 Anti-Raid Status", color=0xFFAA00)
            embed.add_field(name="Raid Mode", value="🔒 LOCKDOWN" if settings.get("raid_mode", 0) else "✅ Normal", inline=True)
            embed.add_field(name="Sensitivity", value=f"{settings.get('raid_sensitivity_level', 5)}/10", inline=True)
            embed.add_field(name="Max Joins", value=settings.get("raid_join_threshold", 10), inline=True)
            embed.add_field(name="Account Age", value=f"{settings.get('raid_account_age', 7)} days", inline=True)
            embed.add_field(name="Auto Mode", value="✅ Enabled" if settings.get("raid_auto_mode", 0) else "❌ Disabled", inline=True)
            
            quarantine_ch = guild.get_channel(settings.get("raid_quarantine_channel", 0))
            embed.add_field(name="Quarantine Channel", value=quarantine_ch.mention if quarantine_ch else "Not set", inline=True)
            
            webhook_url = settings.get("raid_webhook_url", "")
            embed.add_field(name="Webhook Alerts", value="✅ Configured" if webhook_url else "❌ Not set", inline=True)

            # Show recent joins
            if guild.id in self.join_tracker:
                recent_joins = len([t for t in self.join_tracker[guild.id] if (datetime.now(timezone.utc) - t).total_seconds() < 60])
                embed.add_field(name="Recent Joins (1m)", value=recent_joins, inline=True)

            return await interaction.response.send_message(embed=embed, ephemeral=False)

        elif action_l in ("toggle", "lockdown"):
            if not value:
                settings = await get_guild(guild.id)
                current = settings.get("raid_mode", 0)
                return await interaction.response.send_message(
                    embed=info_embed("Raid Mode", f"Currently: {'🔒 LOCKDOWN' if current else '✅ Normal'}"),
                    ephemeral=False
                )
            
            if value.lower() in ("true", "on", "enable", "1"):
                await update_guild(guild.id, raid_mode=1)
                await log_action(guild.id, "raid_mode_enabled", 0, {"enabled_by": interaction.user.id})
                return await interaction.response.send_message(
                    embed=success_embed("Raid Mode Enabled", "Server is now in LOCKDOWN mode."),
                    ephemeral=False
                )
            else:
                await update_guild(guild.id, raid_mode=0)
                await log_action(guild.id, "raid_mode_disabled", 0, {"disabled_by": interaction.user.id})
                return await interaction.response.send_message(
                    embed=success_embed("Raid Mode Disabled", "Server is now in NORMAL mode."),
                    ephemeral=False
                )

        elif action_l == "unlock":
            await update_guild(guild.id, raid_mode=0)
            await log_action(guild.id, "raid_mode_unlocked", 0, {"unlocked_by": interaction.user.id})
            if guild.id in self.join_tracker:
                self.join_tracker[guild.id].clear()
            return await interaction.response.send_message(
                embed=success_embed("Server Unlocked", "Raid mode has been disabled."),
                ephemeral=False
            )

        elif action_l == "sensitivity":
            if not value:
                settings = await get_guild(guild.id)
                return await interaction.response.send_message(
                    embed=info_embed("Raid Sensitivity", f"Current: {settings.get('raid_sensitivity_level', 5)}/10 (1=least sensitive, 10=most sensitive)"),
                    ephemeral=False
                )
            try:
                level = max(1, min(10, int(value)))
                await update_guild(guild.id, raid_sensitivity_level=level)
                return await interaction.response.send_message(
                    embed=success_embed("Sensitivity Set", f"Raid sensitivity set to {level}/10."),
                    ephemeral=False
                )
            except ValueError:
                return await interaction.response.send_message(embed=error_embed("Sensitivity must be a number 1-10."), ephemeral=True)

        elif action_l == "maxjoins":
            if not value:
                settings = await get_guild(guild.id)
                return await interaction.response.send_message(
                    embed=info_embed("Max Joins", f"Current: {settings.get('raid_join_threshold', 10)} joins per window"),
                    ephemeral=False
                )
            try:
                count = max(1, min(100, int(value)))
                await update_guild(guild.id, raid_join_threshold=count)
                return await interaction.response.send_message(
                    embed=success_embed("Max Joins Set", f"Raid will trigger at {count} joins."),
                    ephemeral=False
                )
            except ValueError:
                return await interaction.response.send_message(embed=error_embed("Max joins must be a number 1-100."), ephemeral=True)

        elif action_l == "minage":
            if not value:
                settings = await get_guild(guild.id)
                return await interaction.response.send_message(
                    embed=info_embed("Minimum Account Age", f"Current: {settings.get('raid_account_age', 7)} days"),
                    ephemeral=False
                )
            try:
                days = max(0, int(value))
                await update_guild(guild.id, raid_account_age=days)
                return await interaction.response.send_message(
                    embed=success_embed("Account Age Set", f"Accounts must be {days}+ days old."),
                    ephemeral=False
                )
            except ValueError:
                return await interaction.response.send_message(embed=error_embed("Age must be a number (days)."), ephemeral=True)

        elif action_l == "quarantine":
            if not value:
                settings = await get_guild(guild.id)
                ch = guild.get_channel(settings.get("raid_quarantine_channel", 0))
                return await interaction.response.send_message(
                    embed=info_embed("Quarantine Channel", f"Current: {ch.mention if ch else 'Not set'}"),
                    ephemeral=False
                )
            ch = await self._resolve_channel(guild, value)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Channel not found."), ephemeral=True)
            await update_guild(guild.id, raid_quarantine_channel=ch.id)
            return await interaction.response.send_message(
                embed=success_embed("Quarantine Channel Set", f"Suspicious users will be moved to {ch.mention}"),
                ephemeral=False
            )

        elif action_l == "webhook":
            if not value:
                settings = await get_guild(guild.id)
                webhook_url = settings.get("raid_webhook_url", "")
                return await interaction.response.send_message(
                    embed=info_embed("Webhook Alerts", f"Current: {'✅ Configured' if webhook_url else '❌ Not set'}"),
                    ephemeral=False
                )
            await update_guild(guild.id, raid_webhook_url=value)
            return await interaction.response.send_message(
                embed=success_embed("Webhook Set", "Raid alerts will be sent to this webhook."),
                ephemeral=False
            )

        elif action_l == "auto":
            if not value:
                settings = await get_guild(guild.id)
                return await interaction.response.send_message(
                    embed=info_embed("Auto Mode", f"Current: {'✅ Enabled' if settings.get('raid_auto_mode', 0) else '❌ Disabled'}"),
                    ephemeral=False
                )
            if value.lower() in ("true", "on", "enable", "1"):
                await update_guild(guild.id, raid_auto_mode=1)
                return await interaction.response.send_message(
                    embed=success_embed("Auto Mode Enabled", "Raid mode will trigger automatically."),
                    ephemeral=False
                )
            else:
                await update_guild(guild.id, raid_auto_mode=0)
                return await interaction.response.send_message(
                    embed=success_embed("Auto Mode Disabled", "Raid mode must be triggered manually."),
                    ephemeral=False
                )

        else:
            return await interaction.response.send_message(
                embed=error_embed("Use: `status`, `toggle`, `unlock`, `sensitivity`, `maxjoins`, `minage`, `quarantine`, `webhook`, or `auto`."),
                ephemeral=True
            )

    @app_commands.command(name="raidscore", description="Check raid score for a user (Mod only)")
    @app_commands.describe(user="User to check")
    async def raidscore(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild_id = interaction.guild.id
        raid_score = self.raid_scores.get(guild_id, {}).get(user.id, 0)

        embed = discord.Embed(
            title=f"🎯 Raid Score for {user.name}",
            description=f"**Score:** {raid_score}/10 (Higher = More Suspicious)",
            color=0xFF4444 if raid_score >= 5 else 0xFFAA00 if raid_score >= 3 else 0x44FF88
        )

        # Score breakdown
        reasons = []
        if (datetime.now(timezone.utc) - user.created_at).days < 7:
            reasons.append("🔴 New account (< 7 days)")
        if not user.avatar:
            reasons.append("🟡 No avatar")
        if user.default_avatar:
            reasons.append("🟡 Default avatar")
        if len(user.name) < 3 or any(c in user.name for c in ['_.', '-', '0123456789']):
            reasons.append("🟡 Suspicious username pattern")

        if reasons:
            embed.add_field(name="Score Factors", value="\n".join(reasons), inline=False)
        else:
            embed.add_field(name="Score Factors", value="✅ No suspicious patterns detected", inline=False)

        embed.add_field(name="Account Created", value=user.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="Account Age", value=f"{(datetime.now(timezone.utc) - user.created_at).days} days", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EnhancedAntiRaid(bot))
