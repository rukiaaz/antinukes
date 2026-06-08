"""Repent - Anti-Raid System

Detects mass joins, triggers server lockdown, filters new accounts, and runs verification gates.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set, Optional
from collections import deque

import discord
from discord.ext import commands

from database import get_guild, update_guild, log_raid_start, log_raid_end, log_action
from utils.embeds import error_embed, info_embed, success_embed
from config import OWNER_ID, DEFAULT_PUNISHMENT


class VerificationView(discord.ui.View):
    """Persistent verification button view."""
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success, custom_id="repent_verify_button", emoji="🛡️")
    async def verify_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        if not guild or not member:
            return

        settings = await get_guild(guild.id)
        unverified_role = discord.utils.get(guild.roles, name="Repent Unverified")

        if unverified_role and unverified_role not in member.roles:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return

        # If raid mode is active, enforce account age check
        if settings.get("raid_mode", 0):
            account_age_days = settings.get("raid_account_age", 7)
            created_days = (datetime.now(timezone.utc) - member.created_at.replace(tzinfo=None)).days
            if created_days < account_age_days:
                await interaction.response.send_message(
                    f"❌ Verification Failed: Your account is too new ({created_days} days old). The threshold is {account_age_days} days during lockdown.",
                    ephemeral=True
                )
                return

        # Remove unverified role
        try:
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="[Repent] Completed verification")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I do not have permission to remove your unverified role. Please contact a server admin.", ephemeral=True)
            return
        except Exception:
            pass

        # Give autorole
        autorole_id = settings.get("autorole", 0)
        if autorole_id:
            role = guild.get_role(autorole_id)
            if role:
                try:
                    await member.add_roles(role, reason="[Repent] Verification Autorole")
                except Exception:
                    pass

        # Send welcome message
        welcome_ch_id = settings.get("welcome_channel", 0)
        welcome_msg = settings.get("welcome_msg", "")
        if welcome_ch_id and welcome_msg:
            ch = guild.get_channel(welcome_ch_id)
            if ch:
                msg = (welcome_msg
                       .replace("{user}", member.mention)
                       .replace("{username}", member.name)
                       .replace("{server}", guild.name)
                       .replace("{count}", str(guild.member_count)))
                embed = discord.Embed(description=msg, color=0x44FF88)
                embed.set_author(name=f"Welcome to {guild.name}", icon_url=guild.icon.url if guild.icon else None)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"Member #{guild.member_count}")
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass

        await interaction.response.send_message("✅ Verification successful! Welcome to the server.", ephemeral=True)


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.join_tracker: Dict[int, deque[datetime]] = {}
        self.active_raids: Dict[int, dict] = {}
        self.original_everyone_perms: Dict[int, int] = {}

    async def cog_load(self):
        self.bot.add_view(VerificationView(self.bot))

    def cog_unload(self):
        # Cancel any running auto-unlock timers
        for raid in self.active_raids.values():
            if "timer" in raid:
                raid["timer"].cancel()

    async def _log_to_channel(self, guild: discord.Guild, text: str) -> None:
        try:
            settings = await get_guild(guild.id)
            log_ch_id = settings.get("log_channel", 0)
            if not log_ch_id:
                return
            ch = guild.get_channel(log_ch_id)
            if ch:
                await ch.send(text)
        except Exception:
            pass

    async def trigger_raid_mode(self, guild: discord.Guild, joins_detected: int):
        settings = await get_guild(guild.id)
        if settings.get("raid_mode", 0):
            return

        # Update DB
        await update_guild(guild.id, raid_mode=1)

        # Log raid start
        raid_id = await log_raid_start(guild.id, joins_detected, lockdown_triggered=1)
        self.active_raids[guild.id] = {
            "raid_id": raid_id,
            "timer": asyncio.create_task(self.auto_unlock_timer(guild.id, 900))  # 15 minutes
        }

        # Lockdown @everyone
        everyone = guild.default_role
        original_perms = everyone.permissions
        self.original_everyone_perms[guild.id] = original_perms.value

        new_perms = discord.Permissions(original_perms.value)
        new_perms.update(
            send_messages=False,
            send_messages_in_threads=False,
            create_public_threads=False,
            create_private_threads=False,
            connect=False
        )

        try:
            await everyone.edit(permissions=new_perms, reason="[Repent Anti-Raid] Guild Lockdown")
        except Exception as e:
            print(f"[ANTIRAID] Failed to lockdown guild {guild.id}: {e}")

        # Embed Alert
        embed = discord.Embed(
            title="🚨 Raid Detected — Lockdown Active!",
            description=f"Mass join flood detected: **{joins_detected} joins** in the last {settings.get('raid_join_window', 10)} seconds.\n\n"
                        f"🔒 **Lockdown Status:** Active (All channels locked for `@everyone`)\n"
                        f"🛡️ **Anti-Raid Mode:** Enabled (New accounts age filter active)\n"
                        f"⏳ **Auto-Unlock:** In 15 minutes of inactivity.",
            color=0xFF4444
        )
        embed.set_footer(text="Repent Anti-Raid System")
        embed.timestamp = datetime.now(timezone.utc)

        log_ch_id = settings.get("log_channel", 0)
        if log_ch_id:
            ch = guild.get_channel(log_ch_id)
            if ch:
                await ch.send(embed=embed)

        try:
            owner = guild.get_member(guild.owner_id)
            if owner:
                await owner.send(embed=embed)
        except Exception:
            pass

    async def auto_unlock_timer(self, guild_id: int, delay: int):
        await asyncio.sleep(delay)
        guild = self.bot.get_guild(guild_id)
        if guild:
            await self.unlock_guild(guild, "Auto-unlock after 15 minutes of inactivity")

    async def unlock_guild(self, guild: discord.Guild, reason: str):
        settings = await get_guild(guild.id)
        if not settings.get("raid_mode", 0):
            return

        # Update DB
        await update_guild(guild.id, raid_mode=0)

        # Remove timer
        raid_info = self.active_raids.pop(guild.id, None)
        if raid_info:
            if "timer" in raid_info:
                raid_info["timer"].cancel()
            await log_raid_end(raid_info["raid_id"], resolved=1)

        # Restore permissions
        everyone = guild.default_role
        saved_perms = self.original_everyone_perms.pop(guild.id, None)
        if saved_perms is not None:
            new_perms = discord.Permissions(saved_perms)
        else:
            new_perms = everyone.permissions
            new_perms.update(send_messages=True, send_messages_in_threads=True, connect=True)

        try:
            await everyone.edit(permissions=new_perms, reason=f"[Repent Anti-Raid] Unlock: {reason}")
        except Exception as e:
            print(f"[ANTIRAID] Failed to unlock guild {guild.id}: {e}")

        # Alert
        embed = discord.Embed(
            title="🔓 Server Unlocked",
            description=f"Anti-Raid lockdown has been lifted.\n**Reason:** {reason}\n\nAll normal user permissions have been restored.",
            color=0x44FF88
        )
        embed.timestamp = datetime.now(timezone.utc)

        log_ch_id = settings.get("log_channel", 0)
        if log_ch_id:
            ch = guild.get_channel(log_ch_id)
            if ch:
                await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await get_guild(guild.id)

        # Whitelist checks
        if member.id == OWNER_ID or member.id == guild.owner_id:
            return

        is_raid_active = settings.get("raid_mode", 0)

        if is_raid_active:
            # Enforce Account Age Filter
            account_age_days = settings.get("raid_account_age", 7)
            created_days = (datetime.now(timezone.utc) - member.created_at.replace(tzinfo=None)).days
            if created_days < account_age_days:
                try:
                    await member.send(f"⚠️ You were kicked from **{guild.name}** because your account is too new ({created_days} days old) and the server is in Raid Mode.")
                except Exception:
                    pass
                try:
                    await member.kick(reason=f"[Repent Anti-Raid] Account age filter ({created_days}d < {account_age_days}d)")
                    await log_action(guild.id, "raid_kick", member.id, {"reason": f"Account age {created_days}d < threshold {account_age_days}d"})
                    await self._log_to_channel(guild, f"📥 **Kick**: {member.mention} (`{member.id}`) was auto-kicked (Account age: {created_days} days).")
                except Exception:
                    pass
                return

            # Verification channel check
            verification_channel_id = settings.get("verification_channel", 0)
            if verification_channel_id:
                ch = guild.get_channel(verification_channel_id)
                if ch:
                    unverified_role = discord.utils.get(guild.roles, name="Repent Unverified")
                    if not unverified_role:
                        try:
                            unverified_role = await guild.create_role(
                                name="Repent Unverified",
                                reason="[Repent Anti-Raid] Created unverified role for verification gate"
                            )
                        except Exception:
                            pass

                    if unverified_role:
                        try:
                            await member.add_roles(unverified_role, reason="[Repent Anti-Raid] Placed in verification gate")
                            try:
                                await member.send(f"🔒 **{guild.name}** is in Raid Mode. Please verify in the verification channel: {ch.mention}.")
                            except Exception:
                                pass
                        except Exception:
                            pass
                return

        # Track Join Rate
        guild_id = guild.id
        if guild_id not in self.join_tracker:
            self.join_tracker[guild_id] = deque()

        now = datetime.now(timezone.utc)
        self.join_tracker[guild_id].append(now)

        window = settings.get("raid_join_window", 10)
        cutoff = now - timedelta(seconds=window)
        while self.join_tracker[guild_id] and self.join_tracker[guild_id][0] <= cutoff:
            self.join_tracker[guild_id].popleft()

        threshold = settings.get("raid_join_threshold", 10)
        if len(self.join_tracker[guild_id]) >= threshold:
            await self.trigger_raid_mode(guild, len(self.join_tracker[guild_id]))

    # ── Command Group ──
    @discord.app_commands.default_permissions(administrator=True)
    class RaidGroup(discord.app_commands.Group):
        def __init__(self, bot: commands.Bot, cog: AntiRaid):
            super().__init__(name="raid", description="Anti-Raid management commands")
            self.bot = bot
            self.cog = cog

        @discord.app_commands.command(name="status", description="Show the current anti-raid status and configuration")
        async def status(self, interaction: discord.Interaction):
            if not interaction.guild:
                return
            settings = await get_guild(interaction.guild.id)
            is_active = settings.get("raid_mode", 0)

            status_str = "🔴 **Lockdown Active**" if is_active else "🟢 **Normal Operation**"

            ver_ch_id = settings.get("verification_channel", 0)
            ver_ch_str = f"<#{ver_ch_id}>" if ver_ch_id else "*None*"

            embed = discord.Embed(
                title="🛡️ Anti-Raid Status",
                description=f"Status: {status_str}\n\n"
                            f"**Threshold:** {settings.get('raid_join_threshold', 10)} joins\n"
                            f"**Window:** {settings.get('raid_join_window', 10)} seconds\n"
                            f"**Account Age Filter:** {settings.get('raid_account_age', 7)} days\n"
                            f"**Verification Channel:** {ver_ch_str}",
                color=0x4488FF if not is_active else 0xFF4444
            )
            await interaction.response.send_message(embed=embed)

        @discord.app_commands.command(name="toggle", description="Manually enable/disable raid lockdown mode")
        @discord.app_commands.describe(enabled="Enable or disable raid lockdown mode")
        async def toggle(self, interaction: discord.Interaction, enabled: bool):
            if not interaction.guild:
                return

            settings = await get_guild(interaction.guild.id)
            current = settings.get("raid_mode", 0)

            if enabled and not current:
                await interaction.response.defer(thinking=True)
                await self.cog.trigger_raid_mode(interaction.guild, 0)
                await interaction.followup.send(embed=success_embed("Raid Mode Activated", "Server has been locked down manually."))
            elif not enabled and current:
                await interaction.response.defer(thinking=True)
                await self.cog.unlock_guild(interaction.guild, f"Manually unlocked by {interaction.user}")
                await interaction.followup.send(embed=success_embed("Raid Mode Deactivated", "Server lockdown lifted manually."))
            else:
                await interaction.response.send_message(embed=info_embed("Info", f"Raid mode is already {'enabled' if enabled else 'disabled'}."))

        @discord.app_commands.command(name="config", description="Configure anti-raid settings")
        @discord.app_commands.describe(
            threshold="Number of joins to trigger raid mode",
            window="Sliding window in seconds",
            account_age="Minimum account age in days to allow joining during raid mode",
            verification_channel="Verification channel for new members"
        )
        async def config(
            self,
            interaction: discord.Interaction,
            threshold: Optional[int] = None,
            window: Optional[int] = None,
            account_age: Optional[int] = None,
            verification_channel: Optional[discord.TextChannel] = None
        ):
            if not interaction.guild:
                return

            updates = {}
            if threshold is not None:
                updates["raid_join_threshold"] = threshold
            if window is not None:
                updates["raid_join_window"] = window
            if account_age is not None:
                updates["raid_account_age"] = account_age
            if verification_channel is not None:
                updates["verification_channel"] = verification_channel.id

            if not updates:
                return await interaction.response.send_message(embed=error_embed("No configuration options provided."))

            await update_guild(interaction.guild.id, **updates)

            desc = "\n".join(f"**{k.replace('raid_', '').replace('_', ' ').title()}:** {v}" for k, v in updates.items())
            await interaction.response.send_message(embed=success_embed("Configuration Updated", desc))

        @discord.app_commands.command(name="unlock", description="Manually lift the lockdown and restore normal permissions")
        async def unlock(self, interaction: discord.Interaction):
            if not interaction.guild:
                return
            settings = await get_guild(interaction.guild.id)
            if not settings.get("raid_mode", 0):
                return await interaction.response.send_message(embed=error_embed("Server is not currently locked down."))

            await interaction.response.defer(thinking=True)
            await self.cog.unlock_guild(interaction.guild, f"Manually unlocked by {interaction.user}")
            await interaction.followup.send(embed=success_embed("Server Unlocked", "Lockdown has been lifted."))

        @discord.app_commands.command(name="verification-setup", description="Setup verification message in the verification channel")
        async def verification_setup(self, interaction: discord.Interaction):
            if not interaction.guild:
                return

            settings = await get_guild(interaction.guild.id)
            ver_ch_id = settings.get("verification_channel", 0)
            if not ver_ch_id:
                return await interaction.response.send_message(embed=error_embed("Please set a verification channel first using `/raid config`."), ephemeral=True)

            ch = interaction.guild.get_channel(ver_ch_id)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Configured verification channel not found."), ephemeral=True)

            embed = discord.Embed(
                title="🛡️ Server Verification Gate",
                description="Welcome to the server! To prevent spam, selfbots, and raids, we require you to verify before accessing the rest of the server.\n\n"
                            "Click the **Verify** button below to complete verification.",
                color=0x4488FF
            )
            embed.set_footer(text="Repent Security")

            view = VerificationView(self.bot)
            try:
                await ch.send(embed=embed, view=view)
                await interaction.response.send_message(embed=success_embed("Verification Gate Set", f"Verification message sent to {ch.mention}."), ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(embed=error_embed(f"Failed to send message: {e}"), ephemeral=True)

    def cog_load_complete(self):
        # We need to register the slash command group
        # In discord.py v2, this is how we register groups from cogs:
        self.bot.tree.add_command(self.RaidGroup(self.bot, self))

    async def cog_load(self):
        await super().cog_load()
        # Add the command group during cog load
        try:
            self.bot.tree.add_command(self.RaidGroup(self.bot, self))
        except Exception:
            pass  # Already added


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))
