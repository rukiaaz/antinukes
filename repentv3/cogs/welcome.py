"""
Repent - Welcome / Farewell System
Customizable welcome messages, farewells, and auto-role.
"""

import discord
from discord.ext import commands

from database import get_guild, update_guild
from utils.embeds import success_embed, error_embed, info_embed


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _format_message(self, template: str, member: discord.Member, guild: discord.Guild) -> str:
        """Replace template variables."""
        if not template:
            return ""
        return (template
                .replace("{user}", member.mention)
                .replace("{username}", member.name)
                .replace("{server}", guild.name)
                .replace("{count}", str(guild.member_count))
                .replace("{guild}", guild.name))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await get_guild(guild.id)

        # Skip welcome/autorole if raid mode is active (handled by verification gate)
        if settings.get("raid_mode", 0):
            return

        # Autorole
        autorole_id = settings.get("autorole", 0)
        if autorole_id:
            role = guild.get_role(autorole_id)
            if role:
                try:
                    await member.add_roles(role, reason="[Repent] Autorole")
                except Exception:
                    pass

        # Welcome message
        welcome_ch_id = settings.get("welcome_channel", 0)
        welcome_msg = settings.get("welcome_msg", "")
        if welcome_ch_id and welcome_msg:
            ch = guild.get_channel(welcome_ch_id)
            if ch:
                msg = self._format_message(welcome_msg, member, guild)
                embed = discord.Embed(
                    description=msg,
                    color=0x44FF88,
                )
                embed.set_author(name=f"Welcome to {guild.name}", icon_url=guild.icon.url if guild.icon else None)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"Member #{guild.member_count}")
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        settings = await get_guild(guild.id)

        farewell_ch_id = settings.get("farewell_channel", 0)
        farewell_msg = settings.get("farewell_msg", "")
        if farewell_ch_id and farewell_msg:
            ch = guild.get_channel(farewell_ch_id)
            if ch:
                msg = self._format_message(farewell_msg, member, guild)
                embed = discord.Embed(
                    description=msg,
                    color=0xFFAA00,
                )
                embed.set_author(name=f"Goodbye from {guild.name}", icon_url=guild.icon.url if guild.icon else None)
                embed.set_thumbnail(url=member.display_avatar.url)
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handle boost events."""
        guild = after.guild
        settings = await get_guild(guild.id)

        # Check if user just boosted
        before_premium = before.premium_since
        after_premium = after.premium_since

        # User just started boosting
        if before_premium is None and after_premium is not None:
            boost_ch_id = settings.get("boost_channel", 0)
            boost_msg = settings.get("boost_msg", "")
            if boost_ch_id and boost_msg:
                ch = guild.get_channel(boost_ch_id)
                if ch:
                    msg = self._format_message(boost_msg, after, guild)
                    embed = discord.Embed(
                        description=msg,
                        color=0xFF69B4,  # Pink for boost
                    )
                    embed.set_author(name=f"🚀 Server Boosted!", icon_url=guild.icon.url if guild.icon else None)
                    embed.set_thumbnail(url=after.display_avatar.url)
                    embed.set_footer(text=f"Thanks for the boost, {after.name}!")
                    try:
                        await ch.send(embed=embed)
                    except Exception:
                        pass

    # ── Welcome Commands ──
    @discord.app_commands.command(name="welcome", description="Configure welcome settings (Admin only)")
    @discord.app_commands.describe(
        action="set, message, or autorole",
        channel_or_role="Channel for welcome messages or role for autorole",
        text="Welcome message template",
    )
    async def welcome(self, interaction: discord.Interaction, action: str, channel_or_role: str = None, text: str = None):
        from config import OWNER_ID
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild

        if action.lower() == "set":
            if not channel_or_role:
                return await interaction.response.send_message(embed=error_embed("Provide a channel."), ephemeral=True)
            ch = await self._resolve_channel(guild, channel_or_role)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Channel not found."), ephemeral=True)
            await update_guild(guild.id, welcome_channel=ch.id)
            await interaction.response.send_message(
                embed=success_embed("Welcome Channel Set", f"Welcome messages will be sent to {ch.mention}"),
                ephemeral=False,
            )

        elif action.lower() == "message":
            if not text:
                settings = await get_guild(guild.id)
                current = settings.get("welcome_msg", "")
                return await interaction.response.send_message(
                    embed=info_embed("Welcome Message", f"Current:\n{current or 'Not set'}\n\nVariables: `{{user}}`, `{{server}}`, `{{count}}`"),
                    ephemeral=False,
                )
            await update_guild(guild.id, welcome_msg=text)
            await interaction.response.send_message(
                embed=success_embed("Welcome Message Set", f"Message updated.\nPreview: {text.replace('{user}', interaction.user.mention).replace('{server}', guild.name).replace('{count}', str(guild.member_count))}"),
                ephemeral=False,
            )

        elif action.lower() == "autorole":
            if not channel_or_role:
                return await interaction.response.send_message(embed=error_embed("Provide a role."), ephemeral=True)
            role = await self._resolve_role(guild, channel_or_role)
            if not role:
                return await interaction.response.send_message(embed=error_embed("Role not found."), ephemeral=True)
            await update_guild(guild.id, autorole=role.id)
            await interaction.response.send_message(
                embed=success_embed("Autorole Set", f"New members will receive {role.mention}"),
                ephemeral=False,
            )

        else:
            await interaction.response.send_message(
                embed=error_embed("Invalid action. Use: `set`, `message`, or `autorole`."), ephemeral=True
            )

    # ── Farewell Commands ──
    @discord.app_commands.command(name="farewell", description="Configure farewell settings (Admin only)")
    @discord.app_commands.describe(
        action="set or message",
        channel="Channel for farewell messages",
        text="Farewell message template",
    )
    async def farewell(self, interaction: discord.Interaction, action: str, channel: str = None, text: str = None):
        from config import OWNER_ID
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild

        if action.lower() == "set":
            if not channel:
                return await interaction.response.send_message(embed=error_embed("Provide a channel."), ephemeral=True)
            ch = await self._resolve_channel(guild, channel)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Channel not found."), ephemeral=True)
            await update_guild(guild.id, farewell_channel=ch.id)
            await interaction.response.send_message(
                embed=success_embed("Farewell Channel Set", f"Farewell messages will be sent to {ch.mention}"),
                ephemeral=False,
            )

        elif action.lower() == "message":
            if not text:
                settings = await get_guild(guild.id)
                current = settings.get("farewell_msg", "")
                return await interaction.response.send_message(
                    embed=info_embed("Farewell Message", f"Current:\n{current or 'Not set'}\n\nVariables: `{{user}}`, `{{server}}`, `{{count}}`"),
                    ephemeral=False,
                )
            await update_guild(guild.id, farewell_msg=text)
            await interaction.response.send_message(
                embed=success_embed("Farewell Message Set", f"Message updated.\nPreview: {text.replace('{user}', interaction.user.mention).replace('{server}', guild.name).replace('{count}', str(guild.member_count))}"),
                ephemeral=False,
            )

        else:
            await interaction.response.send_message(
                embed=error_embed("Invalid action. Use: `set` or `message`."), ephemeral=True
            )

    # ── Boost Commands ──
    @discord.app_commands.command(name="boost", description="Configure boost settings (Admin only)")
    @discord.app_commands.describe(
        action="set or message",
        channel="Channel for boost messages",
        text="Boost message template",
    )
    async def boost(self, interaction: discord.Interaction, action: str, channel: str = None, text: str = None):
        from config import OWNER_ID
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild

        if action.lower() == "set":
            if not channel:
                return await interaction.response.send_message(embed=error_embed("Provide a channel."), ephemeral=True)
            ch = await self._resolve_channel(guild, channel)
            if not ch:
                return await interaction.response.send_message(embed=error_embed("Channel not found."), ephemeral=True)
            await update_guild(guild.id, boost_channel=ch.id)
            await interaction.response.send_message(
                embed=success_embed("Boost Channel Set", f"Boost messages will be sent to {ch.mention}"),
                ephemeral=False,
            )

        elif action.lower() == "message":
            if not text:
                settings = await get_guild(guild.id)
                current = settings.get("boost_msg", "")
                return await interaction.response.send_message(
                    embed=info_embed("Boost Message", f"Current:\n{current or 'Not set'}\n\nVariables: `{{user}}`, `{{server}}`, `{{count}}`"),
                    ephemeral=False,
                )
            await update_guild(guild.id, boost_msg=text)
            await interaction.response.send_message(
                embed=success_embed("Boost Message Set", f"Message updated.\nPreview: {text.replace('{user}', interaction.user.mention).replace('{server}', guild.name).replace('{count}', str(guild.member_count))}"),
                ephemeral=False,
            )

        else:
            await interaction.response.send_message(
                embed=error_embed("Invalid action. Use: `set` or `message`."), ephemeral=True
            )

    async def _resolve_channel(self, guild: discord.Guild, value: str):
        """Resolve channel from mention, ID, or name."""
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
        """Resolve role from mention, ID, or name."""
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
