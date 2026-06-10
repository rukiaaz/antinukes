"""Repent - Advanced Verification System

Customizable verification with embeds, roles, and buttons.
"""

from __future__ import annotations

import json
import discord
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID
from database import get_guild, update_guild
from utils.embeds import success_embed, error_embed, info_embed


class VerificationButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, verification_role_id: int):
        super().__init__(style=discord.ButtonStyle.success, label="Verify")
        self.bot = bot
        self.verification_role_id = verification_role_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        
        if not guild or not member:
            return

        settings = await get_guild(guild.id)
        
        # Check if user is already verified (has the role)
        verification_role_id = settings.get("verification_role", 0)
        if verification_role_id:
            role = guild.get_role(verification_role_id)
            if role and role in member.roles:
                await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
                return

        # Check raid mode and account age if enabled
        if settings.get("raid_mode", 0):
            account_age_days = settings.get("raid_account_age", 7)
            created_days = (discord.utils.utcnow() - member.created_at).days
            if created_days < account_age_days:
                await interaction.response.send_message(
                    f"❌ Verification Failed: Your account is too new ({created_days} days old). "
                    f"The threshold is {account_age_days} days during lockdown.",
                    ephemeral=True
                )
                return

        # Give verification role
        if verification_role_id:
            role = guild.get_role(verification_role_id)
            if role:
                try:
                    await member.add_roles(role, reason="[Repent] User verified")
                    
                    # Also give autorole if configured
                    autorole_id = settings.get("autorole", 0)
                    if autorole_id:
                        autorole = guild.get_role(autorole_id)
                        if autorole:
                            try:
                                await member.add_roles(autorole, reason="[Repent] Verification autorole")
                            except Exception:
                                pass
                    
                    # Send welcome message if configured
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
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ I do not have permission to give you the verification role. Please contact a server admin.",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ Verification role not found. Please contact a server admin.",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "❌ No verification role configured. Please contact a server admin.",
                ephemeral=True
            )


class Verification(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

    @app_commands.command(name="verification", description="Configure verification system (Admin only)")
    @app_commands.describe(
        action="set, message, role, embed, button, send, disable, or status",
        channel="Channel for verification",
        value="Value for the action (role, text, etc.)",
    )
    async def verification(
        self,
        interaction: discord.Interaction,
        action: str,
        channel: str = None,
        value: str = None,
    ):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        action_l = action.lower().strip()

        if action_l == "set":
            if not channel:
                return await interaction.response.send_message(embed=error_embed("Provide a channel."), ephemeral=True)
            ch = await self._resolve_channel(guild, channel)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Channel not found."), ephemeral=True)
            await update_guild(guild.id, verification_channel=ch.id, verification_enabled=1)
            return await interaction.response.send_message(
                embed=success_embed("Verification Channel Set", f"Verification will be sent to {ch.mention}"),
                ephemeral=False,
            )

        elif action_l == "role":
            if not value:
                settings = await get_guild(guild.id)
                current = settings.get("verification_role", 0)
                current_role = guild.get_role(current) if current else None
                return await interaction.response.send_message(
                    embed=info_embed("Verification Role", f"Current: {current_role.mention if current_role else 'Not set'}"),
                    ephemeral=False,
                )
            role = await self._resolve_role(guild, value)
            if not role:
                return await interaction.response.send_message(embed=error_embed("Role not found."), ephemeral=True)
            await update_guild(guild.id, verification_role=role.id)
            return await interaction.response.send_message(
                embed=success_embed("Verification Role Set", f"Users will receive {role.mention} upon verification."),
                ephemeral=False,
            )

        elif action_l == "message":
            if not value:
                settings = await get_guild(guild.id)
                current = settings.get("verification_description", "")
                return await interaction.response.send_message(
                    embed=info_embed("Verification Message", f"Current:\n{current or 'Not set'}"),
                    ephemeral=False,
                )
            await update_guild(guild.id, verification_description=value)
            return await interaction.response.send_message(
                embed=success_embed("Verification Message Set", "Message updated."),
                ephemeral=False,
            )

        elif action_l == "embed":
            if not value:
                settings = await get_guild(guild.id)
                return await interaction.response.send_message(
                    embed=info_embed(
                        "Verification Embed Settings",
                        f"Title: `{settings.get('verification_title', 'Verification Required')}`\n"
                        f"Color: `{settings.get('verification_color', '4488FF')}`\n"
                        f"Button Text: `{settings.get('verification_button_text', 'Verify')}`\n\n"
                        f"Use: `/verification embed title <text>` to set title\n"
                        f"Use: `/verification embed color <hex>` to set color\n"
                        f"Use: `/verification embed button <text>` to set button text"
                    ),
                    ephemeral=False,
                )
            
            # Handle sub-commands for embed settings
            parts = value.split(maxsplit=1)
            if len(parts) < 2:
                return await interaction.response.send_message(embed=error_embed("Usage: `/verification embed title <text>` or `color <hex>` or `button <text>`"), ephemeral=True)
            
            sub_action = parts[0].lower()
            sub_value = parts[1]
            
            if sub_action == "title":
                await update_guild(guild.id, verification_title=sub_value)
                return await interaction.response.send_message(embed=success_embed("Title Set", f"Embed title set to: `{sub_value}`"), ephemeral=False)
            
            elif sub_action == "color":
                try:
                    # Parse hex color
                    color_hex = sub_value.lstrip('#')
                    color_int = int(color_hex, 16)
                    await update_guild(guild.id, verification_color=color_int)
                    return await interaction.response.send_message(embed=success_embed("Color Set", f"Embed color set to: #{color_hex}"), ephemeral=False)
                except ValueError:
                    return await interaction.response.send_message(embed=error_embed("Invalid hex color. Use format: #RRGGBB"), ephemeral=True)
            
            elif sub_action == "button":
                await update_guild(guild.id, verification_button_text=sub_value)
                return await interaction.response.send_message(embed=success_embed("Button Text Set", f"Button text set to: `{sub_value}`"), ephemeral=False)
            
            else:
                return await interaction.response.send_message(embed=error_embed("Use: `title`, `color`, or `button`"), ephemeral=True)

        elif action_l == "send":
            settings = await get_guild(guild.id)
            verification_ch_id = settings.get("verification_channel", 0)
            verification_role_id = settings.get("verification_role", 0)
            
            if not verification_ch_id:
                return await interaction.response.send_message(embed=error_embed("Verification channel not set. Use `/verification set` first."), ephemeral=True)
            
            if not verification_role_id:
                return await interaction.response.send_message(embed=error_embed("Verification role not set. Use `/verification role` first."), ephemeral=True)
            
            ch = guild.get_channel(verification_ch_id)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Verification channel not found."), ephemeral=True)
            
            # Create verification embed
            title = settings.get("verification_title", "Verification Required")
            description = settings.get("verification_description", "Click the button below to verify yourself and gain access to the server.")
            color = settings.get("verification_color", 0x4488FF)
            button_text = settings.get("verification_button_text", "Verify")
            
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text=f"Powered by {self.bot.user.name}")
            
            view = discord.ui.View()
            view.add_item(VerificationButton(self.bot, verification_role_id))
            # Update button label
            view.children[0].label = button_text
            
            try:
                await ch.send(embed=embed, view=view)
                return await interaction.response.send_message(embed=success_embed("Verification Sent", f"Verification message sent to {ch.mention}"), ephemeral=False)
            except discord.Forbidden:
                return await interaction.response.send_message(embed=error_embed("I do not have permission to send messages in that channel."), ephemeral=True)

        elif action_l == "disable":
            await update_guild(guild.id, verification_enabled=0)
            return await interaction.response.send_message(
                embed=success_embed("Verification Disabled", "Verification system has been disabled."),
                ephemeral=False,
            )

        elif action_l == "status":
            settings = await get_guild(guild.id)
            enabled = settings.get("verification_enabled", 0)
            ch = guild.get_channel(settings.get("verification_channel", 0))
            role = guild.get_role(settings.get("verification_role", 0))
            
            embed = discord.Embed(title="🔐 Verification Status", color=0x4488FF)
            embed.add_field(name="Status", value="✅ Enabled" if enabled else "❌ Disabled", inline=True)
            embed.add_field(name="Channel", value=ch.mention if ch else "Not set", inline=True)
            embed.add_field(name="Role", value=role.mention if role else "Not set", inline=True)
            embed.add_field(name="Title", value=f"`{settings.get('verification_title', 'Verification Required')}`", inline=False)
            embed.add_field(name="Button Text", value=f"`{settings.get('verification_button_text', 'Verify')}`", inline=False)
            
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        else:
            return await interaction.response.send_message(
                embed=error_embed("Use: `set`, `role`, `message`, `embed`, `send`, `disable`, or `status`."),
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Verification(bot))
