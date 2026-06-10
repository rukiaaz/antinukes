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
    add_bot_whitelist,
    remove_bot_whitelist,
    get_bot_whitelist,
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
        self.welcome_channel = None
        self.boost_channel = None
        self.bot_whitelist_done = False
        self.verification_channel = None
        self.verification_role = None
        self.verification_enabled = False

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

    # 3. Welcome Channel Selector
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Welcome Channel (Optional)...",
        row=2
    )
    async def select_welcome_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        self.welcome_channel = channel
        await update_guild(interaction.guild.id, welcome_channel=channel.id)
        await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}", ephemeral=True)
        await self.update_embed(interaction)

    # 4. Boost Channel Selector
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Boost Channel (Optional)...",
        row=2
    )
    async def select_boost_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        self.boost_channel = channel
        await update_guild(interaction.guild.id, boost_channel=channel.id)
        await interaction.response.send_message(f"✅ Boost channel set to {channel.mention}", ephemeral=True)
        await self.update_embed(interaction)

    # 5. Verification Channel Selector
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Verification Channel (Optional)...",
        row=3
    )
    async def select_verification_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        self.verification_channel = channel
        await update_guild(interaction.guild.id, verification_channel=channel.id)
        await interaction.response.send_message(f"✅ Verification channel set to {channel.mention}", ephemeral=True)
        await self.update_embed(interaction)

    # 6. Verification Role Selector
    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select Verification Role (Optional)...",
        row=3
    )
    async def select_verification_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        self.verification_role = role
        await update_guild(interaction.guild.id, verification_role=role.id)
        await interaction.response.send_message(f"✅ Verification role set to {role.mention}", ephemeral=True)
        await self.update_embed(interaction)

    # 7. Whitelist Owner & Invoker Button
    @discord.ui.button(label="Auto-Whitelist Owner & Invoker", style=discord.ButtonStyle.primary, row=4, emoji="🛡️")
    async def whitelist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        await add_whitelist(guild.id, guild.owner_id, 2, interaction.user.id)
        if interaction.user.id != guild.owner_id:
            await add_whitelist(guild.id, interaction.user.id, 2, interaction.user.id)
        self.whitelist_done = True
        button.disabled = True
        await interaction.response.send_message("✅ Whitelisted Server Owner & Invoker with Full trust.", ephemeral=True)
        await self.update_embed(interaction)

    # 8. Auto-Whitelist Bots Button
    @discord.ui.button(label="Auto-Whitelist Common Bots", style=discord.ButtonStyle.secondary, row=4, emoji="🤖")
    async def bot_whitelist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        whitelisted_count = 0
        # Whitelist common bot types
        for member in guild.members:
            if member.bot:
                # Whitelist bots that are likely to be utility bots
                # (you can add more sophisticated detection logic here)
                await add_bot_whitelist(guild.id, member.id, interaction.user.id, "Auto-whitelisted during setup")
                whitelisted_count += 1
        
        self.bot_whitelist_done = True
        button.disabled = True
        await interaction.response.send_message(f"✅ Whitelisted {whitelisted_count} bots in the server.", ephemeral=True)
        await self.update_embed(interaction)

    # 9. Enable All Protections Button
    @discord.ui.button(label="Enable All Protections", style=discord.ButtonStyle.success, row=5, emoji="⚡")
    async def protections_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        await update_guild(guild.id, antinuke_enabled=1, automod_enabled=1, raid_mode=0)
        self.protections_enabled = True
        button.disabled = True
        await interaction.response.send_message("✅ Activated Antinuke, AutoMod, and Anti-Raid protections.", ephemeral=True)
        await self.update_embed(interaction)

    # 10. Auto-Create Channel Button
    @discord.ui.button(label="Create Logs Channel", style=discord.ButtonStyle.secondary, row=5, emoji="📁")
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

    # 11. Send Verification Button
    @discord.ui.button(label="Send Verification Message", style=discord.ButtonStyle.success, row=6, emoji="🔐")
    async def send_verification_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.verification_channel or not self.verification_role:
            return await interaction.response.send_message("❌ Please set verification channel and role first.", ephemeral=True)
        
        guild = interaction.guild
        await update_guild(guild.id, verification_enabled=1)
        self.verification_enabled = True
        button.disabled = True
        
        # Send verification message
        from cogs.verification import VerificationButton
        embed = discord.Embed(
            title="Verification Required",
            description="Click the button below to verify yourself and gain access to the server.",
            color=0x4488FF
        )
        embed.set_footer(text=f"Powered by {self.bot.user.name}")
        
        view = discord.ui.View()
        view.add_item(VerificationButton(self.bot, self.verification_role.id))
        
        try:
            await self.verification_channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Verification message sent to {self.verification_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send verification message: {e}", ephemeral=True)
        
        await self.update_embed(interaction)

    # 12. Done Button
    @discord.ui.button(label="Done / Finish", style=discord.ButtonStyle.danger, row=6, emoji="🏁")
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
                        f"**Welcome Channel:** {self.welcome_channel.mention if self.welcome_channel else '*Not Configured*'}\n"
                        f"**Boost Channel:** {self.boost_channel.mention if self.boost_channel else '*Not Configured*'}\n"
                        f"**Verification Channel:** {self.verification_channel.mention if self.verification_channel else '*Not Configured*'}\n"
                        f"**Verification Role:** {self.verification_role.mention if self.verification_role else '*Not Configured*'}\n"
                        f"**Punishment:** `{self.punishment}`\n"
                        f"**Owner/Invoker Whitelist:** {'✅ Done' if self.whitelist_done else '❌ Skipped'}\n"
                        f"**Bot Whitelist:** {'✅ Done' if self.bot_whitelist_done else '❌ Skipped'}\n"
                        f"**Verification Sent:** {'✅ Yes' if self.verification_enabled else '❌ No'}\n"
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
        embed.add_field(name="3️⃣ Welcome Channel", value=self.welcome_channel.mention if self.welcome_channel else "Optional", inline=True)
        embed.add_field(name="4️⃣ Boost Channel", value=self.boost_channel.mention if self.boost_channel else "Optional", inline=True)
        embed.add_field(name="5️⃣ Verification Channel", value=self.verification_channel.mention if self.verification_channel else "Optional", inline=True)
        embed.add_field(name="6️⃣ Verification Role", value=self.verification_role.mention if self.verification_role else "Optional", inline=True)
        embed.add_field(name="7️⃣ Whitelist Owner & Invoker", value="✅ Whitelisted" if self.whitelist_done else "Pending", inline=True)
        embed.add_field(name="8️⃣ Bot Whitelist", value="✅ Done" if self.bot_whitelist_done else "Optional", inline=True)
        embed.add_field(name="9️⃣ Enable Protections", value="✅ Active" if self.protections_enabled else "Pending", inline=True)
        embed.add_field(name="🔟 Verification Sent", value="✅ Yes" if self.verification_enabled else "Optional", inline=True)

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
        boost_ch = guild.get_channel(settings.get("boost_channel", 0))
        autorole = guild.get_role(settings.get("autorole", 0))

        embed.add_field(name="Antinuke", value="✅ Enabled" if settings.get("antinuke_enabled") else "❌ Disabled", inline=True)
        embed.add_field(name="AutoMod", value="✅ Enabled" if settings.get("automod_enabled") else "❌ Disabled", inline=True)
        embed.add_field(name="Punishment", value=f"`{settings.get('punishment', 'ban')}`", inline=True)
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set", inline=True)
        embed.add_field(name="Mod Channel", value=mod_ch.mention if mod_ch else "Not set", inline=True)
        embed.add_field(name="Welcome", value=welcome_ch.mention if welcome_ch else "Not set", inline=True)
        embed.add_field(name="Farewell", value=farewell_ch.mention if farewell_ch else "Not set", inline=True)
        embed.add_field(name="Boost", value=boost_ch.mention if boost_ch else "Not set", inline=True)
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
        embed.add_field(name="3️⃣ Welcome Channel", value="Optional", inline=True)
        embed.add_field(name="4️⃣ Boost Channel", value="Optional", inline=True)
        embed.add_field(name="5️⃣ Verification Channel", value="Optional", inline=True)
        embed.add_field(name="6️⃣ Verification Role", value="Optional", inline=True)
        embed.add_field(name="7️⃣ Whitelist Owner & Invoker", value="Pending", inline=True)
        embed.add_field(name="8️⃣ Bot Whitelist", value="Optional", inline=True)
        embed.add_field(name="9️⃣ Enable Protections", value="Pending", inline=True)
        embed.add_field(name="🔟 Verification Sent", value="Optional", inline=True)

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

    # ── Bot Whitelist Commands ──
    @app_commands.command(name="botwhitelist", description="Manage whitelisted bots - they won't be punished by antinuke (Admin only)")
    @app_commands.describe(
        action="add, remove, or list",
        bot="Bot to add/remove",
        reason="Reason for whitelisting",
    )
    async def botwhitelist(
        self,
        interaction: discord.Interaction,
        action: str,
        bot: discord.Member = None,
        reason: str = "Trusted bot",
    ):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        action_l = action.lower().strip()

        if action_l == "add":
            if not bot:
                return await interaction.response.send_message(embed=error_embed("Provide a bot."), ephemeral=True)
            if not bot.bot:
                return await interaction.response.send_message(embed=error_embed("This is not a bot."), ephemeral=True)
            
            await add_bot_whitelist(guild.id, bot.id, interaction.user.id, reason)
            await log_action(
                guild.id,
                "bot_whitelist_add",
                bot.id,
                {"reason": reason, "added_by": interaction.user.id},
            )
            return await interaction.response.send_message(
                embed=success_embed("Bot Whitelisted", f"{bot.mention} is now whitelisted and won't be punished by antinuke.\n**Reason:** {reason}"),
                ephemeral=False,
            )

        if action_l == "remove":
            if not bot:
                return await interaction.response.send_message(embed=error_embed("Provide a bot."), ephemeral=True)
            if not bot.bot:
                return await interaction.response.send_message(embed=error_embed("This is not a bot."), ephemeral=True)
            
            await remove_bot_whitelist(guild.id, bot.id)
            await log_action(guild.id, "bot_whitelist_remove", bot.id, {"removed_by": interaction.user.id})
            return await interaction.response.send_message(
                embed=success_embed("Bot Removed", f"{bot.mention} removed from bot whitelist."),
                ephemeral=False,
            )

        if action_l == "list":
            entries = await get_bot_whitelist(guild.id)
            if not entries:
                return await interaction.response.send_message(embed=info_embed("Bot Whitelist", "No bots whitelisted."), ephemeral=False)

            lines = []
            for e in entries[:20]:
                member = guild.get_member(e["bot_id"])
                name = member.mention if member else f"<@{e['bot_id']}>"
                reason_text = e.get("reason", "No reason")
                lines.append(f"{name} — `{reason_text}`")

            embed = info_embed("Whitelisted Bots", "\n".join(lines))
            embed.add_field(name="Note", value="Whitelisted bots won't be punished by antinuke systems.", inline=False)
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        return await interaction.response.send_message(embed=error_embed("Use: `add`, `remove`, or `list`."), ephemeral=True)

    # ── Safe Admin Commands ──
    @app_commands.command(name="safeadmin", description="Manage safe admins - immune to antinuke (Admin only)")
    @app_commands.describe(action="add, remove, or list", user="User to add/remove")
    async def safeadmin(self, interaction: discord.Interaction, action: str, user: discord.Member = None):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        action_l = action.lower().strip()
        settings = await get_guild(guild.id)

        if action_l == "add":
            if not user:
                return await interaction.response.send_message(embed=error_embed("Provide a user."), ephemeral=True)
            
            # Get current safe admins
            try:
                import json
                safe_admins_json = settings.get("antinuke_safe_admins", "[]")
                safe_admins = json.loads(safe_admins_json)
            except json.JSONDecodeError:
                safe_admins = []
            
            if user.id in safe_admins:
                return await interaction.response.send_message(embed=error_embed("User is already a safe admin."), ephemeral=True)
            
            safe_admins.append(user.id)
            await update_guild(guild.id, antinuke_safe_admins=json.dumps(safe_admins))
            await log_action(guild.id, "safe_admin_added", user.id, {"added_by": interaction.user.id})
            
            return await interaction.response.send_message(
                embed=success_embed("Safe Admin Added", f"{user.mention} is now immune to antinuke punishments."),
                ephemeral=False,
            )

        elif action_l == "remove":
            if not user:
                return await interaction.response.send_message(embed=error_embed("Provide a user."), ephemeral=True)
            
            # Get current safe admins
            try:
                import json
                safe_admins_json = settings.get("antinuke_safe_admins", "[]")
                safe_admins = json.loads(safe_admins_json)
            except json.JSONDecodeError:
                safe_admins = []
            
            if user.id not in safe_admins:
                return await interaction.response.send_message(embed=error_embed("User is not a safe admin."), ephemeral=True)
            
            safe_admins.remove(user.id)
            await update_guild(guild.id, antinuke_safe_admins=json.dumps(safe_admins))
            await log_action(guild.id, "safe_admin_removed", user.id, {"removed_by": interaction.user.id})
            
            return await interaction.response.send_message(
                embed=success_embed("Safe Admin Removed", f"{user.mention} is no longer immune to antinuke."),
                ephemeral=False,
            )

        elif action_l == "list":
            try:
                import json
                safe_admins_json = settings.get("antinuke_safe_admins", "[]")
                safe_admins = json.loads(safe_admins_json)
            except json.JSONDecodeError:
                safe_admins = []
            
            if not safe_admins:
                return await interaction.response.send_message(
                    embed=info_embed("Safe Admins", "No safe admins configured."),
                    ephemeral=False,
                )
            
            lines = []
            for admin_id in safe_admins:
                member = guild.get_member(admin_id)
                name = member.mention if member else f"<@{admin_id}>"
                lines.append(name)
            
            embed = info_embed("Safe Admins", "\n".join(lines))
            embed.add_field(name="Note", value="Safe admins are immune to antinuke punishments.", inline=False)
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        else:
            return await interaction.response.send_message(embed=error_embed("Use: `add`, `remove`, or `list`."), ephemeral=True)

    # ── Enhanced Antinuke Commands ──
    @app_commands.command(name="antinukeconfig", description="Configure advanced antinuke settings (Admin only)")
    @app_commands.describe(
        action="sensitivity, lockdown, instantrestore, logging, or status",
        value="Value to set"
    )
    async def antinukeconfig(self, interaction: discord.Interaction, action: str, value: str = None):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        action_l = action.lower().strip()
        settings = await get_guild(guild.id)

        if action_l == "sensitivity":
            if not value:
                current = settings.get("antinuke_sensitivity_level", 5)
                return await interaction.response.send_message(
                    embed=info_embed("Antinuke Sensitivity", f"Current: {current}/10 (1=least sensitive, 10=most sensitive)"),
                    ephemeral=False
                )
            try:
                level = max(1, min(10, int(value)))
                await update_guild(guild.id, antinuke_sensitivity_level=level)
                return await interaction.response.send_message(
                    embed=success_embed("Sensitivity Set", f"Antinuke sensitivity set to {level}/10."),
                    ephemeral=False
                )
            except ValueError:
                return await interaction.response.send_message(embed=error_embed("Sensitivity must be a number 1-10."), ephemeral=True)

        elif action_l == "lockdown":
            if not value:
                current = settings.get("antinuke_lockdown_mode", 0)
                return await interaction.response.send_message(
                    embed=info_embed("Lockdown Mode", f"Current: {'🔒 LOCKDOWN' if current else '✅ Normal'}"),
                    ephemeral=False
                )
            if value.lower() in ("true", "on", "enable", "1"):
                await update_guild(guild.id, antinuke_lockdown_mode=1)
                return await interaction.response.send_message(
                    embed=success_embed("Lockdown Enabled", "Server is in antinuke lockdown mode."),
                    ephemeral=False
                )
            else:
                await update_guild(guild.id, antinuke_lockdown_mode=0)
                return await interaction.response.send_message(
                    embed=success_embed("Lockdown Disabled", "Server is in normal mode."),
                    ephemeral=False
                )

        elif action_l == "instantrestore":
            if not value:
                current = settings.get("antinuke_instant_restore", 1)
                return await interaction.response.send_message(
                    embed=info_embed("Instant Restore", f"Current: {'✅ Enabled' if current else '❌ Disabled'}"),
                    ephemeral=False
                )
            if value.lower() in ("true", "on", "enable", "1"):
                await update_guild(guild.id, antinuke_instant_restore=1)
                return await interaction.response.send_message(
                    embed=success_embed("Instant Restore Enabled", "Deleted channels/roles will be instantly restored."),
                    ephemeral=False
                )
            else:
                await update_guild(guild.id, antinuke_instant_restore=0)
                return await interaction.response.send_message(
                    embed=success_embed("Instant Restore Disabled", "Manual restore required."),
                    ephemeral=False
                )

        elif action_l == "logging":
            if not value:
                current = settings.get("antinuke_log_all_punishments", 1)
                return await interaction.response.send_message(
                    embed=info_embed("Punishment Logging", f"Current: {'✅ Enabled' if current else '❌ Disabled'}"),
                    ephemeral=False
                )
            if value.lower() in ("true", "on", "enable", "1"):
                await update_guild(guild.id, antinuke_log_all_punishments=1)
                return await interaction.response.send_message(
                    embed=success_embed("Logging Enabled", "All punishments will be logged."),
                    ephemeral=False
                )
            else:
                await update_guild(guild.id, antinuke_log_all_punishments=0)
                return await interaction.response.send_message(
                    embed=success_embed("Logging Disabled", "Only critical punishments will be logged."),
                    ephemeral=False
                )

        elif action_l == "status":
            embed = discord.Embed(title="🛡️ Advanced Antinuke Status", color=0x4488FF)
            embed.add_field(name="Sensitivity", value=f"{settings.get('antinuke_sensitivity_level', 5)}/10", inline=True)
            embed.add_field(name="Lockdown Mode", value="🔒 LOCKDOWN" if settings.get("antinuke_lockdown_mode", 0) else "✅ Normal", inline=True)
            embed.add_field(name="Instant Restore", value="✅ Enabled" if settings.get("antinuke_instant_restore", 1) else "❌ Disabled", inline=True)
            embed.add_field(name="Detailed Logging", value="✅ Enabled" if settings.get("antinuke_log_all_punishments", 1) else "❌ Disabled", inline=True)
            
            try:
                import json
                safe_admins_json = settings.get("antinuke_safe_admins", "[]")
                safe_admins = json.loads(safe_admins_json)
                embed.add_field(name="Safe Admins", value=str(len(safe_admins)), inline=True)
            except json.JSONDecodeError:
                embed.add_field(name="Safe Admins", value="0", inline=True)

            return await interaction.response.send_message(embed=embed, ephemeral=False)

        else:
            return await interaction.response.send_message(
                embed=error_embed("Use: `sensitivity`, `lockdown`, `instantrestore`, `logging`, or `status`."),
                ephemeral=True
            )

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
