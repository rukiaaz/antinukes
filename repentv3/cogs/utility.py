"""Repent - Utility Commands

Userinfo, serverinfo, ping, afk, avatar, and more.

Includes:
- /spam <message> <count>
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_NAME, VERSION, OWNER_ID, COLOR_INFO, COLOR_SUCCESS
from database import get_afk, remove_afk, set_afk
from utils.embeds import error_embed, info_embed, success_embed
from utils.health_check import get_health_checker


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.now(timezone.utc)

    @app_commands.command(name="userinfo", description="Show info about a user")
    @app_commands.describe(user="User to check (default: yourself)")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        roles = [r.mention for r in target.roles if r.name != "@everyone"][:10]
        join_pos = (
            sorted(interaction.guild.members, key=lambda m: m.joined_at or datetime.now(timezone.utc)).index(target) + 1
        )

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            color=target.color if getattr(target.color, "value", None) else COLOR_INFO,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Username", value=f"{target.name}\n`{target.id}`", inline=True)
        embed.add_field(name="Nickname", value=target.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)

        if target.joined_at:
            embed.add_field(
                name="Joined",
                value=f"<t:{int(target.joined_at.timestamp())}:F>\n(<t:{int(target.joined_at.timestamp())}:R>)",
                inline=False,
            )
        else:
            embed.add_field(name="Joined", value="N/A", inline=False)

        embed.add_field(
            name="Created",
            value=f"<t:{int(target.created_at.timestamp())}:F>\n(<t:{int(target.created_at.timestamp())}:R>)",
            inline=False,
        )
        embed.add_field(
            name=f"Roles ({len(target.roles) - 1})",
            value=" ".join(roles) if roles else "None",
            inline=False,
        )
        embed.add_field(name="Join Position", value=f"#{join_pos}", inline=True)
        embed.add_field(name="Top Role", value=target.top_role.mention, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="serverinfo", description="Show server information")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        owner = guild.get_member(guild.owner_id) or await self.bot.fetch_user(guild.owner_id)

        total = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots = total - humans if total else 0

        embed = discord.Embed(title=f"🏠 {guild.name}", color=COLOR_INFO)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Owner", value=f"{owner.mention}\n`{guild.owner_id}`", inline=True)
        embed.add_field(name="Members", value=f"**{total}** total\n{humans} humans / {bots} bots", inline=True)
        embed.add_field(
            name="Boost",
            value=f"Level {guild.premium_tier}\n{guild.premium_subscription_count} boosts",
            inline=True,
        )
        embed.add_field(
            name="Channels",
            value=f"{len(guild.text_channels)} text / {len(guild.voice_channels)} voice / {len(guild.categories)} categories",
            inline=True,
        )
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Emojis", value=str(len(guild.emojis)), inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(guild.created_at.timestamp())}:F>\n(<t:{int(guild.created_at.timestamp())}:R>)",
            inline=False,
        )
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=False)

        if guild.vanity_url_code:
            embed.add_field(name="Vanity", value=f"discord.gg/{guild.vanity_url_code}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="avatar", description="Show a user's avatar")
    @app_commands.describe(user="User (default: yourself)")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        embed = discord.Embed(title=f"🖼️ {target.display_name}'s Avatar", color=COLOR_INFO)
        embed.set_image(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="roleinfo", description="Show info about a role")
    @app_commands.describe(role="Role to inspect")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        members = len(role.members)
        color = role.color if getattr(role.color, "value", None) else COLOR_INFO

        embed = discord.Embed(title=f"📛 {role.name}", color=color)
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Members", value=str(members), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        embed.add_field(name="Hoist", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:R>", inline=False)
        embed.add_field(name="Permissions", value=f"```\n{role.permissions.value}\n```", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="channelinfo", description="Show channel info")
    @app_commands.describe(channel="Channel (default: current)")
    async def channelinfo(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        ch = channel or interaction.channel
        embed = discord.Embed(title=f"#️⃣ {ch.name}", color=COLOR_INFO)
        embed.add_field(name="ID", value=f"`{ch.id}`", inline=True)
        embed.add_field(name="Type", value=str(ch.type), inline=True)
        embed.add_field(name="NSFW", value="Yes" if ch.nsfw else "No", inline=True)
        embed.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s" if ch.slowmode_delay else "None", inline=True)
        embed.add_field(name="Category", value=ch.category.name if ch.category else "None", inline=True)
        embed.add_field(name="Position", value=str(ch.position), inline=True)
        embed.add_field(name="Created", value=f"<t:{int(ch.created_at.timestamp())}:R>", inline=False)
        if ch.topic:
            embed.add_field(name="Topic", value=ch.topic[:500], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        ws_latency = round(self.bot.latency * 1000)
        start = time.perf_counter()
        await interaction.response.send_message("Testing...", ephemeral=True)
        end = time.perf_counter()
        api_latency = round((end - start) * 1000)

        embed = discord.Embed(title="🏓 Pong!", color=COLOR_SUCCESS)
        embed.add_field(name="WebSocket", value=f"`{ws_latency}ms`", inline=True)
        embed.add_field(name="API", value=f"`{api_latency}ms`", inline=True)
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="uptime", description="Show bot uptime")
    async def uptime(self, interaction: discord.Interaction):
        delta = datetime.now(timezone.utc) - self.start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        embed = discord.Embed(title="⏱️ Uptime", description=f"**{uptime_str}**", color=COLOR_INFO)
        embed.add_field(name="Started", value=f"<t:{int(self.start_time.timestamp())}:F>", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="afk", description="Set your AFK status")
    @app_commands.describe(reason="AFK reason")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        await set_afk(interaction.guild.id, interaction.user.id, reason)
        await interaction.response.send_message(
            embed=success_embed("AFK Set", f"{interaction.user.mention} is now AFK: **{reason}**"),
            ephemeral=False,
        )

    @app_commands.command(name="botinfo", description="Show bot information")
    async def botinfo(self, interaction: discord.Interaction):
        total_guilds = len(self.bot.guilds)
        total_users = sum(g.member_count for g in self.bot.guilds)
        commands_count = len(self.bot.tree.get_commands())

        embed = discord.Embed(
            title=f"🤖 {BOT_NAME}",
            description=f"**{BOT_NAME}** v{VERSION} — Advanced antinuke, moderation, and utility bot.",
            color=COLOR_INFO,
        )
        embed.add_field(name="Guilds", value=str(total_guilds), inline=True)
        embed.add_field(name="Users", value=str(total_users), inline=True)
        embed.add_field(name="Commands", value=str(commands_count), inline=True)
        embed.add_field(name="Library", value=f"discord.py {discord.__version__}", inline=True)
        embed.add_field(name="Owner", value=f"<@{OWNER_ID}>", inline=True)
        embed.add_field(name="Uptime", value=f"<t:{int(self.start_time.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"{BOT_NAME} v{VERSION}")

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="invite", description="Get the bot invite link")
    async def invite(self, interaction: discord.Interaction):
        perms = discord.Permissions(8)  # Administrator
        url = discord.utils.oauth_url(self.bot.user.id, permissions=perms)
        embed = discord.Embed(
            title=f"🔗 Invite {BOT_NAME}",
            description=(f"[Click here to invite {BOT_NAME}]({url})\n\n"
                         "Recommended: Administrator permission for full antinuke protection."),
            color=COLOR_SUCCESS,
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # ── /spam ──
    @app_commands.command(name="spam", description="Spam a message (Admin only)")
    @app_commands.describe(message="Message to send", count="How many times (1-10)")
    async def spam(self, interaction: discord.Interaction, message: str, count: int):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                embed=error_embed("Administrator required."), ephemeral=True
            )

        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            return await interaction.response.send_message(embed=error_embed("Invalid channel."), ephemeral=True)

        if interaction.guild and interaction.guild.me:
            perms = channel.permissions_for(interaction.guild.me)
            if not perms.send_messages:
                return await interaction.response.send_message(
                    embed=error_embed("I don't have permission to send messages in this channel."),
                    ephemeral=True,
                )

        count = max(1, min(10, count))
        await interaction.response.send_message(
            embed=info_embed("Spamming…", f"Sending `{count}` message(s)."),
            ephemeral=True,
        )

        for i in range(count):
            try:
                await channel.send(message)
            except Exception:
                pass
            if i != count - 1:
                await asyncio.sleep(0.4)

        await interaction.followup.send(
            embed=success_embed("Done", f"Sent `{count}` message(s)."),
            ephemeral=True,
        )

    # AFK behavior
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # Only query DB for likely triggers
        if message.mentions:
            for mention in message.mentions:
                afk_data = await get_afk(message.guild.id, mention.id)
                if not afk_data:
                    continue
                try:
                    await message.reply(
                        f"💤 {mention.mention} is AFK: **{afk_data['reason']}** "
                        f"(since <t:{int(datetime.fromisoformat(afk_data['set_at']).timestamp())}:R>)",
                        delete_after=8,
                    )
                except Exception:
                    pass

        # Remove AFK if the author speaks
        afk_data = await get_afk(message.guild.id, message.author.id)
        if not afk_data:
            return

        await remove_afk(message.guild.id, message.author.id)
        try:
            await message.reply(
                f"👋 Welcome back {message.author.mention}! Your AFK has been removed.",
                delete_after=5,
            )
        except Exception:
            pass

    @app_commands.command(name="health", description="Check bot health status (Admin only)")
    async def health(self, interaction: discord.Interaction):
        """Check bot health and status."""
        if interaction.user.id != OWNER_ID and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=error_embed("This command is restricted to administrators."),
                ephemeral=True
            )
        
        await interaction.response.defer(thinking=True)
        
        try:
            health_checker = get_health_checker(self.bot)
            health_report = await health_checker.get_health_report()
            uptime = health_checker.get_uptime()
            
            # Create health embed
            status_color = {
                "healthy": 0x44FF88,
                "degraded": 0xFFAA00,
                "unhealthy": 0xFF4444
            }.get(health_report["overall_status"], 0xFF4444)
            
            embed = discord.Embed(
                title=f"🏥 Bot Health Status",
                description=f"**Overall Status:** {health_report['overall_status'].upper()}",
                color=status_color
            )
            
            # Discord status
            discord_status = health_report.get("discord", {})
            embed.add_field(
                name="📡 Discord Connection",
                value=f"Status: {discord_status.get('status', 'unknown')}\n"
                      f"Latency: {discord_status.get('latency', 'N/A')}ms\n"
                      f"Guilds: {discord_status.get('guilds', 0)}\n"
                      f"Users: {discord_status.get('users', 0)}",
                inline=True
            )
            
            # Database status
            db_status = health_report.get("database", {})
            embed.add_field(
                name="🗄️ Database",
                value=f"Status: {db_status.get('status', 'unknown')}\n"
                      f"Query Time: {db_status.get('query_time_ms', 'N/A')}ms",
                inline=True
            )
            
            # System status
            system_status = health_report.get("system", {})
            embed.add_field(
                name="💻 System",
                value=f"CPU: {system_status.get('cpu_percent', 'N/A')}%\n"
                      f"Memory: {system_status.get('memory_mb', 'N/A')}MB\n"
                      f"Threads: {system_status.get('threads', 'N/A')}",
                inline=True
            )
            
            # Cache status
            cache_status = health_report.get("cache", {})
            embed.add_field(
                name="🗃️ Cache",
                value=f"Status: {cache_status.get('status', 'unknown')}\n"
                      f"Entries: {cache_status.get('cached_entries', 0)}",
                inline=True
            )
            
            embed.add_field(name="⏱️ Uptime", value=uptime, inline=False)
            embed.set_footer(text=f"Last check: {health_report.get('timestamp', 'N/A')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                embed=error_embed(f"Failed to get health report: {str(e)}"),
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))

