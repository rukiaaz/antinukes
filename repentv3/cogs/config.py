"""Repent - Configuration Commands

Setup wizard, whitelist management, config viewing, antinuke settings.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID, DEFAULT_ANTINUKE_THRESHOLDS, PUNISHMENT_TYPES
from database import (
    get_guild,
    update_guild,
    get_whitelist,
    add_whitelist,
    remove_whitelist,
    get_antinuke_threshold,
    set_antinuke_threshold,
    log_action,
)
from utils.embeds import success_embed, error_embed, info_embed


class InteractiveSetupView(discord.ui.View):
    """Interactive multi-step setup view."""
    def __init__(self, bot: commands.Bot, user: discord.Member):
        super().__init__(timeout=600)
        self.bot = bot
        self.user = user

        # State
        self.log_channel = None
        self.punishment = "ban"
        self.whitelist_done = False
        self.protections_enabled = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Only the command invoker can use this menu.", ephemeral=True)
            return False
        return True

    # 1. Log Channel Selector
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Log Channel...",
        row=0
    )
    async def select_log_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        self.log_channel = channel
        await update_guild(interaction.guild.id, log_channel=channel.id)
        await interaction.response.send_message(f"✅ Log channel set to {channel.mention}", ephemeral=True)
        await self.update_embed(interaction)

    # 2. Punishment Selector
    @discord.ui.select(
        placeholder="Select Punishment...",
        options=[
            discord.SelectOption(label="Ban", value="ban", description="Ban the offender"),
            discord.SelectOption(label="Kick", value="kick", description="Kick the offender"),
            discord.SelectOption(label="Strip Roles", value="strip", description="Strip all roles from offender"),
            discord.SelectOption(label="Timeout", value="timeout", description="Timeout offender for 28 days"),
        ],
        row=1
    )
    async def select_punishment(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.punishment = select.values[0]
        await update_guild(interaction.guild.id, punishment=self.punishment)
        await interaction.response.send_message(f"✅ Punishment set to `{self.punishment}`", ephemeral=True)
        await self.update_embed(interaction)

    # 3. Whitelist Owner & Invoker Button
    @discord.ui.button(label="Auto-Whitelist Owner & Invoker", style=discord.ButtonStyle.primary, row=2, emoji="🛡️")
    async def whitelist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        await add_whitelist(guild.id, guild.owner_id, 2, interaction.user.id)
        if interaction.user.id != guild.owner_id:
            await add_whitelist(guild.id, interaction.user.id, 2, interaction.user.id)
        self.whitelist_done = True
        button.disabled = True
        await interaction.response.send_message("✅ Whitelisted Server Owner & Invoker with Full trust.", ephemeral=True)
        await self.update_embed(interaction)

    # 4. Enable All Protections Button
    @discord.ui.button(label="Enable All Protections", style=discord.ButtonStyle.success, row=2, emoji="⚡")
    async def protections_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        await update_guild(guild.id, antinuke_enabled=1, automod_enabled=1, raid_mode=0)
        self.protections_enabled = True
        button.disabled = True
        await interaction.response.send_message("✅ Activated Antinuke, AutoMod, and Anti-Raid protections.", ephemeral=True)
        await self.update_embed(interaction)

    # 5. Auto-Create Channel Button
    @discord.ui.button(label="Create Logs Channel", style=discord.ButtonStyle.secondary, row=3, emoji="📁")
    async def create_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        ch = discord.utils.get(guild.text_channels, name="repent-logs")
        if not ch:
            try:
                ch = await guild.create_text_channel(
                    name="repent-logs",
                    reason="[Repent] Auto-created log channel during setup",
                    overwrites={
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
                    }
                )
            except discord.Forbidden:
                return await interaction.response.send_message("❌ I do not have permission to create channels.", ephemeral=True)

        self.log_channel = ch
        await update_guild(guild.id, log_channel=ch.id)
        button.disabled = True
        await interaction.response.send_message(f"✅ Created and set log channel to {ch.mention}", ephemeral=True)
        await self.update_embed(interaction)

    # 6. Done Button
    @discord.ui.button(label="Done / Finish", style=discord.ButtonStyle.danger, row=3, emoji="🏁")
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_member = interaction.guild.me
        warnings = []
        if not bot_member.guild_permissions.administrator:
            warnings.append("⚠️ The bot is not an Administrator. Please grant Admin permissions for maximum protection.")
        if not bot_member.guild_permissions.ban_members:
            warnings.append("⚠️ Missing `Ban Members` permission.")
        if not bot_member.guild_permissions.kick_members:
            warnings.append("⚠️ Missing `Kick Members` permission.")
        if not bot_member.guild_permissions.manage_roles:
            warnings.append("⚠️ Missing `Manage Roles` permission.")
        if not bot_member.guild_permissions.manage_channels:
            warnings.append("⚠️ Missing `Manage Channels` permission.")

        warning_text = "\n".join(warnings) if warnings else "✅ All permission checks passed! Bot is ready."

        embed = discord.Embed(
            title="🏁 Setup Complete",
            description=f"Congratulations, **{self.bot.user.name}** setup is finished!\n\n"
                        f"**Log Channel:** {self.log_channel.mention if self.log_channel else '*Not Configured*'}\n"
                        f"**Punishment:** `{self.punishment}`\n"
                        f"**Owner/Invoker Whitelist:** {'✅ Done' if self.whitelist_done else '❌ Skipped'}\n"
                        f"**All Protections Active:** {'✅ Yes' if self.protections_enabled else '❌ No'}\n\n"
                        f"**Permission Status:**\n{warning_text}",
            color=0x44FF88
        )
        embed.set_footer(text="Repent Security Bot")

        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

    async def update_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔧 Repent One-Click Setup Wizard",
            description="Complete the interactive steps below to fully secure your server.",
            color=0x4488FF
        )
        embed.add_field(name="1️⃣ Log Channel", value=self.log_channel.mention if self.log_channel else "Not selected yet", inline=True)
        embed.add_field(name="2️⃣ Punishment", value=f"`{self.punishment}`", inline=True)
        embed.add_field(name="3️⃣ Whitelist Owner & Invoker", value="✅ Whitelisted" if self.whitelist_done else "Pending", inline=True)
        embed.add_field(name="4️⃣ Enable Protections", value="✅ Active (Antinuke, AutoMod, Anti-Raid)" if self.protections_enabled else "Pending", inline=True)

        try:
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            pass


class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator or interaction.user.id == OWNER_ID

    async def _send_config_view(self, interaction: discord.Interaction):
        guild = interaction.guild
        settings = await get_guild(guild.id)

        whitelisted = await get_whitelist(guild.id)
        wl_count = len(whitelisted)

        embed = discord.Embed(title=f"⚙️ {guild.name} Configuration", color=0x4488FF)
        log_ch = guild.get_channel(settings.get("log_channel", 0))
        mod_ch = guild.get_channel(settings.get("mod_channel", 0))
        welcome_ch = guild.get_channel(settings.get("welcome_channel", 0))
        farewell_ch = guild.get_channel(settings.get("farewell_channel", 0))
        autorole = guild.get_role(settings.get("autorole", 0))

        embed.add_field(name="Antinuke", value="✅ Enabled" if settings.get("antinuke_enabled") else "❌ Disabled", inline=True)
        embed.add_field(name="AutoMod", value="✅ Enabled" if settings.get("automod_enabled") else "❌ Disabled", inline=True)
        embed.add_field(name="Punishment", value=f"`{settings.get('punishment', 'ban')}`", inline=True)
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set", inline=True)
        embed.add_field(name="Mod Channel", value=mod_ch.mention if mod_ch else "Not set", inline=True)
        embed.add_field(name="Welcome", value=welcome_ch.mention if welcome_ch else "Not set", inline=True)
        embed.add_field(name="Farewell", value=farewell_ch.mention if farewell_ch else "Not set", inline=True)
        embed.add_field(name="Autorole", value=autorole.mention if autorole else "Not set", inline=True)
        embed.add_field(name="Whitelisted", value=f"{wl_count} user(s)", inline=True)

        return await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _enable_antinuke_with_animation(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        # Loading message
        await interaction.response.send_message(
            embed=info_embed("Enabling Antinuke…", "Preparing protection checks"),
            ephemeral=True,
        )

        try:
            message = await interaction.original_response()
        except Exception:
            message = None

        steps = [
            "Preparing protection checks",
            "Updating thresholds",
            "Warming up handlers",
            "Finalizing…",
        ]

        for i, step in enumerate(steps, start=1):
            await asyncio.sleep(0.5)
            embed = info_embed("Enabling Antinuke…", f"{step} ({i}/{len(steps)})")
            if message:
                try:
                    await message.edit(embed=embed)
                except Exception:
                    pass

        await update_guild(interaction.guild.id, antinuke_enabled=1)
        await interaction.followup.send(
            embed=success_embed("Antinuke Enabled", "All protection modules are now active."),
            ephemeral=False,
        )

    # ── One-Click Setup Wizard ──
    @app_commands.command(name="setup", description="Interactive setup wizard (Admin only)")
    async def setup(self, interaction: discord.Interaction):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)
        if not interaction.guild:
            return

        await get_guild(interaction.guild.id)  # Ensure guild exists in DB

        embed = discord.Embed(
            title="🔧 Repent One-Click Setup Wizard",
            description="Complete the interactive steps below to fully secure your server.",
            color=0x4488FF
        )
        embed.add_field(name="1️⃣ Log Channel", value="Not selected yet", inline=True)
        embed.add_field(name="2️⃣ Punishment", value="`ban` (Default)", inline=True)
        embed.add_field(name="3️⃣ Whitelist Owner & Invoker", value="Pending", inline=True)
        embed.add_field(name="4️⃣ Enable Protections", value="Pending", inline=True)

        view = InteractiveSetupView(self.bot, interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── Quicksetup ──
    @app_commands.command(name="quicksetup", description="One-command full setup: configures logs, punishment, whitelists, and protections")
    async def quicksetup(self, interaction: discord.Interaction):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        await interaction.response.defer(thinking=True)

        # 1. Log channel
        ch = discord.utils.get(guild.text_channels, name="repent-logs")
        if not ch:
            try:
                ch = await guild.create_text_channel(
                    name="repent-logs",
                    reason="[Repent] Created via /quicksetup",
                    overwrites={
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
                    }
                )
            except discord.Forbidden:
                return await interaction.followup.send(embed=error_embed("Failed to create `#repent-logs` channel due to missing permissions."))

        # 2. Update settings in DB
        await update_guild(guild.id, log_channel=ch.id, punishment="ban", antinuke_enabled=1, automod_enabled=1, raid_mode=0)

        # 3. Whitelist owner & invoker
        await add_whitelist(guild.id, guild.owner_id, 2, interaction.user.id)
        if interaction.user.id != guild.owner_id:
            await add_whitelist(guild.id, interaction.user.id, 2, interaction.user.id)

        # 4. Check permissions
        bot_member = guild.me
        warnings = []
        if not bot_member.guild_permissions.administrator:
            warnings.append("⚠️ The bot is not an Administrator. Grant Admin permissions for maximum protection.")
        if not bot_member.guild_permissions.ban_members:
            warnings.append("⚠️ Missing `Ban Members` permission.")
        if not bot_member.guild_permissions.kick_members:
            warnings.append("⚠️ Missing `Kick Members` permission.")
        if not bot_member.guild_permissions.manage_roles:
            warnings.append("⚠️ Missing `Manage Roles` permission.")
        if not bot_member.guild_permissions.manage_channels:
            warnings.append("⚠️ Missing `Manage Channels` permission.")

        warning_text = "\n".join(warnings) if warnings else "✅ All permission checks passed! Bot is ready."

        embed = discord.Embed(
            title="⚡ Quick Setup Complete",
            description=f"Repent has been fully configured and activated in **{guild.name}**!\n\n"
                        f"**Log Channel:** {ch.mention}\n"
                        f"**Punishment:** `ban`\n"
                        f"**Owner/Invoker Whitelist:** Whitelisted (Full Trust)\n"
                        f"**Protections Active:** Antinuke, AutoMod, Anti-Raid\n\n"
                        f"**Permission Status:**\n{warning_text}",
            color=0x44FF88
        )
        embed.set_footer(text="Repent Security Bot")
        await interaction.followup.send(embed=embed)

    # ── Config View ──
    @app_commands.command(name="config", description="View or set configuration (Admin only)")
    @app_commands.describe(
        action="view, logchannel, modchannel, punishment, threshold",
        value="Value to set",
    )
    async def config(self, interaction: discord.Interaction, action: str, value: str = None):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        action_l = action.lower().strip()
        guild = interaction.guild
        settings = await get_guild(guild.id)

        if action_l == "view":
            return await self._send_config_view(interaction)

        if action_l == "logchannel":
            ch = await self._resolve_channel(guild, value)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Channel not found."), ephemeral=True)
            await update_guild(guild.id, log_channel=ch.id)
            return await interaction.response.send_message(
                embed=success_embed("Config Updated", f"Log channel set to {ch.mention}"),
                ephemeral=False,
            )

        if action_l == "modchannel":
            ch = await self._resolve_channel(guild, value)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Channel not found."), ephemeral=True)
            await update_guild(guild.id, mod_channel=ch.id)
            return await interaction.response.send_message(
                embed=success_embed("Config Updated", f"Mod channel set to {ch.mention}"),
                ephemeral=False,
            )

        if action_l == "punishment":
            val = (value or "").lower().strip()
            if val not in PUNISHMENT_TYPES:
                return await interaction.response.send_message(
                    embed=error_embed(f"Invalid punishment. Choose: {', '.join(PUNISHMENT_TYPES)}"),
                    ephemeral=True,
                )
            await update_guild(guild.id, punishment=val)
            return await interaction.response.send_message(
                embed=success_embed("Config Updated", f"Punishment set to `{val}`"),
                ephemeral=False,
            )

        if action_l == "threshold":
            parts = (value or "").split()
            if len(parts) < 3:
                return await interaction.response.send_message(
                    embed=error_embed(
                        "Usage: `/config threshold <action> <count> <seconds>`\n"
                        "Example: `/config threshold ban 3 10`"
                    ),
                    ephemeral=True,
                )
            action_type = parts[0]
            try:
                count = int(parts[1])
                window = int(parts[2])
            except ValueError:
                return await interaction.response.send_message(embed=error_embed("Count and seconds must be numbers."), ephemeral=True)

            await set_antinuke_threshold(guild.id, action_type, count, window)
            return await interaction.response.send_message(
                embed=success_embed("Threshold Updated", f"`{action_type}`: {count} per {window}s"),
                ephemeral=False,
            )

        return await interaction.response.send_message(embed=error_embed("Unknown action."), ephemeral=True)

    # ── Antinuke Commands ──
    @app_commands.command(name="antinuke", description="Manage antinuke settings (Admin only)")
    @app_commands.describe(action="enable, disable, or status")
    async def antinuke(self, interaction: discord.Interaction, action: str):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        action_l = action.lower().strip()
        guild = interaction.guild

        if action_l in ("enable", "on"):
            return await self._enable_antinuke_with_animation(interaction)

        if action_l in ("disable", "off"):
            await update_guild(guild.id, antinuke_enabled=0)
            return await interaction.response.send_message(
                embed=success_embed("Antinuke Disabled", "⚠️ **Warning:** Your server is now unprotected!"),
                ephemeral=False,
            )

        if action_l == "status":
            settings = await get_guild(guild.id)
            enabled = settings.get("antinuke_enabled", 1)
            punishment = settings.get("punishment", "ban")

            embed = discord.Embed(title="🛡️ Antinuke Status", color=0x4488FF)
            embed.add_field(name="Status", value="✅ Enabled" if enabled else "❌ Disabled", inline=True)
            embed.add_field(name="Punishment", value=f"`{punishment}`", inline=True)

            lines = []
            for action_type in DEFAULT_ANTINUKE_THRESHOLDS:
                max_count, window = await get_antinuke_threshold(guild.id, action_type)
                lines.append(f"`{action_type}`: {max_count}/{window}s")
            embed.add_field(name="Thresholds", value="\n".join(lines), inline=False)

            return await interaction.response.send_message(embed=embed, ephemeral=False)

        return await interaction.response.send_message(embed=error_embed("Use: `enable`, `disable`, or `status`."), ephemeral=True)

    # ── Whitelist Commands ──
    @app_commands.command(name="whitelist", description="Manage whitelisted users (Admin only)")
    @app_commands.describe(
        action="add, remove, or list",
        user="User to add/remove",
        level="Trust level (1 = partial, 2 = full)",
    )
    async def whitelist(
        self,
        interaction: discord.Interaction,
        action: str,
        user: discord.Member = None,
        level: int = 1,
    ):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        action_l = action.lower().strip()

        if action_l == "add":
            if not user:
                return await interaction.response.send_message(embed=error_embed("Provide a user."), ephemeral=True)
            if user.id == OWNER_ID:
                return await interaction.response.send_message(
                    embed=error_embed("The bot owner is automatically whitelisted and cannot be added to the list."),
                    ephemeral=True,
                )
            level_c = max(1, min(2, level))
            await add_whitelist(guild.id, user.id, level_c, interaction.user.id)
            await log_action(
                guild.id,
                "whitelist_add",
                user.id,
                {"level": level_c, "added_by": interaction.user.id},
            )
            level_name = "Full" if level_c == 2 else "Partial"
            return await interaction.response.send_message(
                embed=success_embed("Whitelisted", f"{user.mention} added with **{level_name}** trust level."),
                ephemeral=False,
            )

        if action_l == "remove":
            if not user:
                return await interaction.response.send_message(embed=error_embed("Provide a user."), ephemeral=True)
            if user.id == OWNER_ID:
                return await interaction.response.send_message(embed=error_embed("Cannot remove the bot owner from the whitelist."), ephemeral=True)
            await remove_whitelist(guild.id, user.id)
            await log_action(guild.id, "whitelist_remove", user.id, {"removed_by": interaction.user.id})
            return await interaction.response.send_message(
                embed=success_embed("Removed", f"{user.mention} removed from the whitelist."),
                ephemeral=False,
            )

        if action_l == "list":
            entries = await get_whitelist(guild.id)
            if not entries:
                return await interaction.response.send_message(embed=info_embed("Whitelist", "No users whitelisted."), ephemeral=False)

            lines = []
            for e in entries[:20]:
                member = guild.get_member(e["user_id"])
                name = member.mention if member else f"<@{e['user_id']}>"
                level_name = "Full" if e["trust_level"] == 2 else "Partial"
                lines.append(f"{name} — **{level_name}** (`{e['trust_level']}`)")

            embed = info_embed("Whitelisted Users", "\n".join(lines))
            embed.add_field(name="Note", value=f"Bot owner (`{OWNER_ID}`) is always fully whitelisted.", inline=False)
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        return await interaction.response.send_message(embed=error_embed("Use: `add`, `remove`, or `list`."), ephemeral=True)

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


async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))
