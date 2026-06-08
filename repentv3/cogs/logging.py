"""
Repent - Logging System
Comprehensive audit logging for all server events.
"""

import discord
from discord.ext import commands

from database import get_guild, log_action
from utils.embeds import log_embed, info_embed, alert_embed
from config import COLOR_INFO, COLOR_SUCCESS, COLOR_ALERT, COLOR_WARNING


class Logging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_log_channel(self, guild: discord.Guild):
        """Get the configured log channel for a guild."""
        settings = await get_guild(guild.id)
        ch_id = settings.get("log_channel", 0)
        if not ch_id:
            return None
        return guild.get_channel(ch_id)

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed):
        ch = await self._get_log_channel(guild)
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception:
                pass

    # ── Member Events ──
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = log_embed(
            "👤 Member Joined",
            [
                ("User", f"{member.mention}\n`{member.id}`", False),
                ("Account Created", f"<t:{int(member.created_at.timestamp())}:R>", True),
                ("Member Count", str(member.guild.member_count), True),
            ],
            COLOR_SUCCESS,
            member.display_avatar.url,
        )
        await self._send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = log_embed(
            "🚪 Member Left",
            [
                ("User", f"{member.mention}\n`{member.id}`", False),
                ("Joined At", f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "N/A", True),
                ("Member Count", str(member.guild.member_count), True),
            ],
            COLOR_WARNING,
            member.display_avatar.url,
        )
        await self._send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = log_embed(
            "🔨 Member Banned",
            [
                ("User", f"{user.mention}\n`{user.id}`", False),
                ("Type", "Manual ban", True),
            ],
            COLOR_ALERT,
            user.display_avatar.url,
        )
        await self._send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = log_embed(
            "🔓 Member Unbanned",
            [
                ("User", f"{user.mention}\n`{user.id}`", False),
            ],
            COLOR_SUCCESS,
            user.display_avatar.url,
        )
        await self._send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Timeout change
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                embed = log_embed(
                    "⏰ Member Timed Out",
                    [
                        ("User", f"{after.mention}\n`{after.id}`", False),
                        ("Until", f"<t:{int(after.timed_out_until.timestamp())}:R>", True),
                    ],
                    COLOR_WARNING,
                    after.display_avatar.url,
                )
            else:
                embed = log_embed(
                    "⏰ Timeout Removed",
                    [
                        ("User", f"{after.mention}\n`{after.id}`", False),
                    ],
                    COLOR_SUCCESS,
                    after.display_avatar.url,
                )
            await self._send_log(after.guild, embed)

        # Nickname change
        if before.nick != after.nick:
            embed = log_embed(
                "📝 Nickname Changed",
                [
                    ("User", after.mention, False),
                    ("Before", before.nick or "None", True),
                    ("After", after.nick or "None", True),
                ],
                COLOR_INFO,
                after.display_avatar.url,
            )
            await self._send_log(after.guild, embed)

        # Role changes
        before_roles = set(before.roles)
        after_roles = set(after.roles)
        added = after_roles - before_roles
        removed = before_roles - after_roles
        if added:
            embed = log_embed(
                "📝 Role Added",
                [
                    ("User", after.mention, False),
                    ("Role", ", ".join(r.mention for r in list(added)[:4]), True),
                ],
                COLOR_SUCCESS,
                after.display_avatar.url,
            )
            await self._send_log(after.guild, embed)
        if removed:
            embed = log_embed(
                "📝 Role Removed",
                [
                    ("User", after.mention, False),
                    ("Role", ", ".join(r.mention for r in list(removed)[:4]), True),
                ],
                COLOR_WARNING,
                after.display_avatar.url,
            )
            await self._send_log(after.guild, embed)

    # ── Message Events ──
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return
        if before.content == after.content:
            return
        if not before.guild:
            return

        embed = log_embed(
            "✏️ Message Edited",
            [
                ("Author", after.author.mention, False),
                ("Channel", after.channel.mention, True),
                ("Jump", f"[Jump to message]({after.jump_url})", True),
                ("Before", before.content[:1000] or "(empty)", False),
                ("After", after.content[:1000] or "(empty)", False),
            ],
            COLOR_INFO,
            after.author.display_avatar.url,
        )
        await self._send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        embed = log_embed(
            "🗑️ Message Deleted",
            [
                ("Author", message.author.mention, False),
                ("Channel", message.channel.mention, True),
                ("Content", message.content[:1000] or "(empty/attachment)", False),
            ],
            COLOR_ALERT,
            message.author.display_avatar.url,
        )
        await self._send_log(message.guild, embed)

    # ── Channel Events ──
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        embed = log_embed(
            "📁 Channel Created",
            [
                ("Channel", channel.mention if hasattr(channel, 'mention') else channel.name, False),
                ("Type", str(channel.type), True),
                ("ID", f"`{channel.id}`", True),
            ],
            COLOR_SUCCESS,
        )
        await self._send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = log_embed(
            "🗑️ Channel Deleted",
            [
                ("Name", f"#{channel.name}", False),
                ("Type", str(channel.type), True),
                ("ID", f"`{channel.id}`", True),
            ],
            COLOR_ALERT,
        )
        await self._send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        changes = []
        if before.name != after.name:
            changes.append(("Name", f"{before.name} → {after.name}", True))
        if getattr(before, "topic", None) != getattr(after, "topic", None):
            changes.append(("Topic", "Updated", True))
        if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
            changes.append(("NSFW", f"{getattr(before, 'nsfw', False)} → {getattr(after, 'nsfw', False)}", True))
        if getattr(before, "slowmode_delay", 0) != getattr(after, "slowmode_delay", 0):
            changes.append(("Slowmode", f"{getattr(before, 'slowmode_delay', 0)}s → {getattr(after, 'slowmode_delay', 0)}s", True))

        if changes:
            embed = log_embed(
                "📝 Channel Updated",
                [("Channel", after.mention if hasattr(after, 'mention') else after.name, False)] + changes,
                COLOR_INFO,
            )
            await self._send_log(after.guild, embed)

    # ── Role Events ──
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = log_embed(
            "📁 Role Created",
            [
                ("Role", role.mention, False),
                ("Name", role.name, True),
                ("Color", str(role.color), True),
            ],
            COLOR_SUCCESS,
        )
        await self._send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = log_embed(
            "🗑️ Role Deleted",
            [
                ("Name", role.name, False),
                ("Color", str(role.color), True),
                ("Position", str(role.position), True),
            ],
            COLOR_ALERT,
        )
        await self._send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []
        if before.name != after.name:
            changes.append(("Name", f"{before.name} → {after.name}", True))
        if before.color != after.color:
            changes.append(("Color", f"{before.color} → {after.color}", True))
        if before.permissions.value != after.permissions.value:
            changes.append(("Permissions", "Modified", True))
        if before.hoist != after.hoist:
            changes.append(("Hoist", f"{before.hoist} → {after.hoist}", True))

        if changes:
            embed = log_embed(
                "📝 Role Updated",
                [("Role", after.mention, False)] + changes[:3],
                COLOR_INFO,
            )
            await self._send_log(after.guild, embed)

    # ── Voice Events ──
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel != after.channel:
            if not before.channel and after.channel:
                embed = log_embed(
                    "🔊 Voice Join",
                    [
                        ("User", member.mention, False),
                        ("Channel", after.channel.mention, True),
                    ],
                    COLOR_SUCCESS,
                    member.display_avatar.url,
                )
                await self._send_log(member.guild, embed)
            elif before.channel and not after.channel:
                embed = log_embed(
                    "🔇 Voice Leave",
                    [
                        ("User", member.mention, False),
                        ("Channel", before.channel.mention, True),
                    ],
                    COLOR_WARNING,
                    member.display_avatar.url,
                )
                await self._send_log(member.guild, embed)
            elif before.channel and after.channel:
                embed = log_embed(
                    "🔀 Voice Move",
                    [
                        ("User", member.mention, False),
                        ("From", before.channel.mention, True),
                        ("To", after.channel.mention, True),
                    ],
                    COLOR_INFO,
                    member.display_avatar.url,
                )
                await self._send_log(member.guild, embed)

    # ── Server Update ──
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        changes = []
        if before.name != after.name:
            changes.append(("Name", f"{before.name} → {after.name}", True))
        if before.icon != after.icon:
            changes.append(("Icon", "Changed", True))
        if before.verification_level != after.verification_level:
            changes.append(("Verification", f"{before.verification_level} → {after.verification_level}", True))
        if before.vanity_url_code != after.vanity_url_code:
            changes.append(("Vanity", f"{before.vanity_url_code} → {after.vanity_url_code}", True))

        if changes:
            embed = log_embed(
                "🏠 Server Updated",
                changes[:4],
                COLOR_WARNING,
                after.icon.url if after.icon else None,
            )
            await self._send_log(after, embed)

    # ── Invite Events ──
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        embed = log_embed(
            "🔗 Invite Created",
            [
                ("Code", f"`{invite.code}`", False),
                ("Channel", invite.channel.mention if invite.channel else "Unknown", True),
                ("Inviter", invite.inviter.mention if invite.inviter else "Unknown", True),
            ],
            COLOR_SUCCESS,
        )
        await self._send_log(invite.guild, embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        embed = log_embed(
            "🔗 Invite Deleted",
            [
                ("Code", f"`{invite.code}`", False),
                ("Channel", invite.channel.mention if invite.channel else "Unknown", True),
            ],
            COLOR_WARNING,
        )
        await self._send_log(invite.guild, embed)

    # ── Guild Join / Remove ──
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Log to console, no channel to log to yet
        pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Logging(bot))
