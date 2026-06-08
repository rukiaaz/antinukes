"""
Repent - Leveling System
XP per message, ranks, leaderboards, level roles.
"""

import random
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone

from config import DEFAULT_XP_MIN, DEFAULT_XP_MAX, DEFAULT_XP_COOLDOWN
from database import (
    get_xp, add_xp, set_xp_level, reset_xp,
    get_leaderboard, get_level_roles, add_level_role, remove_level_role,
    get_xp_cooldown, set_xp_cooldown,
    update_guild, get_guild,
)
from utils.embeds import success_embed, error_embed, info_embed
from utils.paginator import LeaderboardPaginator


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a level."""
        return int((level / 0.1) ** 2)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        # Check cooldown
        last = await get_xp_cooldown(guild_id, user_id)
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if (datetime.now(timezone.utc) - last_dt).total_seconds() < DEFAULT_XP_COOLDOWN:
                    return
            except Exception:
                pass

        # Add XP
        xp_gain = random.randint(DEFAULT_XP_MIN, DEFAULT_XP_MAX)
        new_level, leveled_up = await add_xp(guild_id, user_id, xp_gain)
        await set_xp_cooldown(guild_id, user_id)

        if leveled_up:
            # Check level role rewards
            level_roles = await get_level_roles(guild_id)
            for lr in level_roles:
                if lr["level"] == new_level:
                    role = message.guild.get_role(lr["role_id"])
                    if role:
                        try:
                            await message.author.add_roles(role, reason=f"[Repent] Level {new_level} reward")
                        except Exception:
                            pass

            # Send level up message
            settings = await get_guild(guild_id)
            level_up_msg = f"🎉 {message.author.mention} leveled up to **Level {new_level}**!"

            if settings.get("level_up_dm", 0):
                try:
                    await message.author.send(level_up_msg)
                except Exception:
                    pass
            else:
                try:
                    await message.channel.send(level_up_msg, delete_after=10)
                except Exception:
                    pass

    @discord.app_commands.command(name="rank", description="Check your rank or another user's rank")
    @discord.app_commands.describe(user="User to check (default: yourself)")
    async def rank(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = await get_xp(interaction.guild.id, target.id)
        xp = data.get("xp", 0)
        level = data.get("level", 0)

        # Calculate rank position
        leaderboard = await get_leaderboard(interaction.guild.id, limit=9999)
        rank = next((i + 1 for i, e in enumerate(leaderboard) if e["user_id"] == target.id), "?")

        # Progress to next level
        current_level_xp = self._xp_for_level(level)
        next_level_xp = self._xp_for_level(level + 1)
        progress = xp - current_level_xp
        needed = next_level_xp - current_level_xp
        percent = (progress / needed * 100) if needed > 0 else 0
        bar = self._progress_bar(percent)

        embed = discord.Embed(
            title=f"📊 {target.display_name}'s Rank",
            color=0x4488FF,
        )
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="XP", value=f"**{xp}**", inline=True)
        embed.add_field(name="Rank", value=f"**#{rank}**", inline=True)
        embed.add_field(
            name="Progress",
            value=f"{bar} **{progress}/{needed}** ({percent:.1f}%)",
            inline=False,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @discord.app_commands.command(name="leaderboard", description="Show the XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        entries = await get_leaderboard(interaction.guild.id, limit=20)
        if not entries:
            return await interaction.response.send_message(
                embed=info_embed("Leaderboard", "No data yet. Start chatting to earn XP!"),
                ephemeral=False,
            )
        view = LeaderboardPaginator(entries, per_page=10, title="XP Leaderboard", guild=interaction.guild)
        await interaction.response.send_message(embed=view.pages[0], view=view, ephemeral=False)

    @discord.app_commands.command(name="setlevel", description="Set a user's level (Admin only)")
    @discord.app_commands.describe(user="User to set level for", level="New level")
    async def setlevel(self, interaction: discord.Interaction, user: discord.Member, level: int):
        from config import OWNER_ID
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        level = max(0, level)
        await set_xp_level(interaction.guild.id, user.id, level)
        await interaction.response.send_message(
            embed=success_embed("Level Set", f"{user.mention}'s level has been set to **{level}**."),
            ephemeral=False,
        )

    @discord.app_commands.command(name="resetxp", description="Reset a user's XP (Admin only)")
    @discord.app_commands.describe(user="User to reset")
    async def resetxp(self, interaction: discord.Interaction, user: discord.Member):
        from config import OWNER_ID
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        await reset_xp(interaction.guild.id, user.id)
        await interaction.response.send_message(
            embed=success_embed("XP Reset", f"{user.mention}'s XP and level have been reset."),
            ephemeral=False,
        )

    @discord.app_commands.command(name="levelrole", description="Manage level role rewards (Admin only)")
    @discord.app_commands.describe(
        action="add or remove",
        level="Level required",
        role="Role to award",
    )
    async def levelrole(self, interaction: discord.Interaction, action: str, level: int, role: discord.Role = None):
        from config import OWNER_ID
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild_id = interaction.guild.id

        if action.lower() == "add":
            if not role:
                return await interaction.response.send_message(embed=error_embed("Provide a role."), ephemeral=True)
            await add_level_role(guild_id, level, role.id)
            await interaction.response.send_message(
                embed=success_embed("Level Role Added", f"At level **{level}**, members receive {role.mention}."),
                ephemeral=False,
            )
        elif action.lower() in ("remove", "rm", "delete"):
            await remove_level_role(guild_id, level)
            await interaction.response.send_message(
                embed=success_embed("Level Role Removed", f"Level **{level}** reward removed."),
                ephemeral=False,
            )
        elif action.lower() == "list":
            roles = await get_level_roles(guild_id)
            if not roles:
                return await interaction.response.send_message(
                    embed=info_embed("Level Roles", "No level roles configured."), ephemeral=False
                )
            lines = []
            for lr in roles:
                r = interaction.guild.get_role(lr["role_id"])
                lines.append(f"Level **{lr['level']}** → {r.mention if r else f'Unknown role `({lr['role_id']})`'}")
            await interaction.response.send_message(
                embed=info_embed("Level Roles", "\n".join(lines)), ephemeral=False
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Use: `add`, `remove`, or `list`."), ephemeral=True
            )

    @discord.app_commands.command(name="levelsetup", description="Configure leveling settings (Admin only)")
    @discord.app_commands.describe(
        channel="Channel for level-up messages (leave blank for current channel)",
        dm="Send level-up messages via DM instead",
    )
    async def levelsetup(self, interaction: discord.Interaction, channel: discord.TextChannel = None, dm: bool = False):
        from config import OWNER_ID
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        updates = {}
        if dm:
            updates["level_up_dm"] = 1
            updates["level_up_channel"] = 0
        elif channel:
            updates["level_up_channel"] = channel.id
            updates["level_up_dm"] = 0

        if updates:
            await update_guild(guild.id, **updates)
            await interaction.response.send_message(
                embed=success_embed("Leveling Configured",
                    "Level-up messages will be sent " + ("via DM" if dm else f"to {channel.mention}") + "."),
                ephemeral=False,
            )
        else:
            await interaction.response.send_message(
                embed=info_embed("Leveling Setup", "Provide a channel or set dm=True."), ephemeral=True
            )

    def _progress_bar(self, percent: float, length: int = 15) -> str:
        filled = int(length * percent / 100)
        filled = min(filled, length)
        return "█" * filled + "░" * (length - filled)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
