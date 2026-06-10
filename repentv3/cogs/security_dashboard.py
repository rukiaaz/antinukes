"""Repent - Security Dashboard

Real-time security monitoring with threat levels and security scoring.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID
from database import get_guild, get_whitelist, get_bot_whitelist, get_punished_users
from utils.embeds import success_embed, error_embed, info_embed


class SecurityDashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator or interaction.user.id == OWNER_ID

    async def _calculate_security_score(self, guild: discord.Guild) -> dict:
        """Calculate a comprehensive security score for the guild."""
        settings = await get_guild(guild.id)
        score = 0
        max_score = 100
        factors = []

        # Antinuke enabled (+20)
        if settings.get("antinuke_enabled", 1):
            score += 20
            factors.append(("Antinuke", 20, True))
        else:
            factors.append(("Antinuke", 20, False))

        # AutoMod enabled (+15)
        if settings.get("automod_enabled", 1):
            score += 15
            factors.append(("AutoMod", 15, True))
        else:
            factors.append(("AutoMod", 15, False))

        # Log channel configured (+15)
        if settings.get("log_channel", 0):
            score += 15
            factors.append(("Log Channel", 15, True))
        else:
            factors.append(("Log Channel", 15, False))

        # Whitelisted users (+10)
        whitelist = await get_whitelist(guild.id)
        if len(whitelist) > 0:
            score += min(10, len(whitelist))
            factors.append(("User Whitelist", min(10, len(whitelist)), True))
        else:
            factors.append(("User Whitelist", 10, False))

        # Bot whitelist (+10)
        bot_whitelist = await get_bot_whitelist(guild.id)
        if len(bot_whitelist) > 0:
            score += min(10, len(bot_whitelist))
            factors.append(("Bot Whitelist", min(10, len(bot_whitelist)), True))
        else:
            factors.append(("Bot Whitelist", 10, False))

        # Safe admins configured (+10)
        try:
            safe_admins = json.loads(settings.get("antinuke_safe_admins", "[]"))
            if len(safe_admins) > 0:
                score += min(10, len(safe_admins))
                factors.append(("Safe Admins", min(10, len(safe_admins)), True))
            else:
                factors.append(("Safe Admins", 10, False))
        except json.JSONDecodeError:
            factors.append(("Safe Admins", 10, False))

        # Verification enabled (+10)
        if settings.get("verification_enabled", 0):
            score += 10
            factors.append(("Verification", 10, True))
        else:
            factors.append(("Verification", 10, False))

        # Raid protection (+10)
        if settings.get("raid_auto_mode", 0) or settings.get("raid_mode", 0):
            score += 10
            factors.append(("Raid Protection", 10, True))
        else:
            factors.append(("Raid Protection", 10, False))

        # Bot permissions check
        bot_member = guild.me
        permission_score = 0
        if bot_member.guild_permissions.administrator:
            permission_score += 10
        if bot_member.guild_permissions.ban_members:
            permission_score += 5
        if bot_member.guild_permissions.manage_roles:
            permission_score += 5
        if bot_member.guild_permissions.manage_channels:
            permission_score += 5
        
        score += min(10, permission_score // 2)
        factors.append(("Bot Permissions", min(10, permission_score // 2), permission_score >= 20))

        return {
            "score": min(max_score, score),
            "max_score": max_score,
            "factors": factors,
            "grade": self._get_security_grade(min(max_score, score))
        }

    def _get_security_grade(self, score: int) -> str:
        """Get security grade based on score."""
        if score >= 90:
            return "A+ (Excellent)"
        elif score >= 80:
            return "A (Very Good)"
        elif score >= 70:
            return "B (Good)"
        elif score >= 60:
            return "C (Fair)"
        elif score >= 50:
            return "D (Poor)"
        else:
            return "F (Critical)"

    async def _calculate_threat_level(self, guild: discord.Guild) -> dict:
        """Calculate current threat level for the guild."""
        settings = await get_guild(guild.id)
        threat_score = 0
        factors = []

        # Recent punished users
        punished_users = await get_punished_users(guild.id)
        recent_punishments = [u for u in punished_users if (datetime.now(timezone.utc) - datetime.fromisoformat(u.get("punished_at", ""))).total_seconds() < 3600]
        
        if len(recent_punishments) > 10:
            threat_score += 30
            factors.append(("Recent Punishments", 30, len(recent_punishments)))
        elif len(recent_punishments) > 5:
            threat_score += 15
            factors.append(("Recent Punishments", 15, len(recent_punishments)))
        else:
            factors.append(("Recent Punishments", 30, len(recent_punishments)))

        # Raid mode active
        if settings.get("raid_mode", 0):
            threat_score += 40
            factors.append(("Raid Mode Active", 40, True))
        else:
            factors.append(("Raid Mode Active", 40, False))

        # Low sensitivity
        if settings.get("antinuke_sensitivity_level", 5) < 5:
            threat_score += 10
            factors.append(("Low Sensitivity", 10, True))
        else:
            factors.append(("Low Sensitivity", 10, False))

        # No verification
        if not settings.get("verification_enabled", 0):
            threat_score += 10
            factors.append(("No Verification", 10, True))
        else:
            factors.append(("No Verification", 10, False))

        # No log channel
        if not settings.get("log_channel", 0):
            threat_score += 10
            factors.append(("No Log Channel", 10, True))
        else:
            factors.append(("No Log Channel", 10, False))

        level = self._get_threat_level_name(threat_score)
        return {
            "score": threat_score,
            "max_score": 100,
            "level": level,
            "factors": factors,
            "color": self._get_threat_color(level)
        }

    def _get_threat_level_name(self, score: int) -> str:
        """Get threat level name based on score."""
        if score >= 70:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 30:
            return "MEDIUM"
        elif score >= 10:
            return "LOW"
        else:
            return "MINIMAL"

    def _get_threat_color(self, level: str) -> int:
        """Get color for threat level."""
        colors = {
            "CRITICAL": 0xFF0000,
            "HIGH": 0xFF4444,
            "MEDIUM": 0xFFAA00,
            "LOW": 0xFFCC00,
            "MINIMAL": 0x44FF88
        }
        return colors.get(level, 0x44FF88)

    @app_commands.command(name="dashboard", description="Show comprehensive security dashboard (Admin only)")
    async def dashboard(self, interaction: discord.Interaction):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        security_data = await self._calculate_security_score(guild)
        threat_data = await self._calculate_threat_level(guild)
        settings = await get_guild(guild.id)

        # Main dashboard embed
        embed = discord.Embed(
            title=f"🛡️ Security Dashboard - {guild.name}",
            description="Real-time security monitoring and threat assessment",
            color=threat_data["color"]
        )

        # Security Score
        score_emoji = "🟢" if security_data["score"] >= 70 else "🟡" if security_data["score"] >= 50 else "🔴"
        embed.add_field(
            name=f"📊 Security Score",
            value=f"{score_emoji} **{security_data['score']}/{security_data['max_score']}** ({security_data['grade']})",
            inline=False
        )

        # Threat Level
        embed.add_field(
            name=f"⚠️ Threat Level",
            value=f"**{threat_data['level']}** ({threat_data['score']}/100)",
            inline=False
        )

        # Active Protections
        protections = []
        if settings.get("antinuke_enabled", 1):
            protections.append("✅ Antinuke")
        else:
            protections.append("❌ Antinuke")
        
        if settings.get("automod_enabled", 1):
            protections.append("✅ AutoMod")
        else:
            protections.append("❌ AutoMod")
        
        if settings.get("raid_mode", 0):
            protections.append("🔒 Raid Mode")
        
        if settings.get("verification_enabled", 0):
            protections.append("🔐 Verification")
        
        embed.add_field(name="Active Protections", value=" ".join(protections[:5]), inline=False)

        # Quick Stats
        whitelist = await get_whitelist(guild.id)
        bot_whitelist = await get_bot_whitelist(guild.id)
        punished = await get_punished_users(guild.id)
        
        embed.add_field(
            name="📈 Statistics",
            value=f"**Whitelisted Users:** {len(whitelist)}\n"
                   f"**Whitelisted Bots:** {len(bot_whitelist)}\n"
                   f"**Active Punishments:** {len(punished)}\n"
                   f"**Total Members:** {guild.member_count}",
            inline=False
        )

        # Recent Activity
        recent_punishments = []
        for u in punished:
            punished_at = u.get("punished_at", "")
            if punished_at:
                try:
                    if (datetime.now(timezone.utc) - datetime.fromisoformat(punished_at)).total_seconds() < 86400:
                        recent_punishments.append(u)
                except (ValueError, TypeError):
                    pass
        if recent_punishments:
            embed.add_field(
                name="🚨 Recent Activity (24h)",
                value=f"{len(recent_punishments)} punishments in the last 24 hours",
                inline=False
            )

        embed.set_footer(text=f"Dashboard generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="securityscore", description="View detailed security score breakdown (Admin only)")
    async def securityscore(self, interaction: discord.Interaction):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        security_data = await self._calculate_security_score(guild)

        embed = discord.Embed(
            title=f"📊 Security Score Breakdown - {guild.name}",
            description=f"**Total Score:** {security_data['score']}/{security_data['max_score']} ({security_data['grade']})",
            color=0x44FF88 if security_data['score'] >= 70 else 0xFFAA00 if security_data['score'] >= 50 else 0xFF4444
        )

        # Show each factor
        for factor_name, max_points, has_it in security_data['factors']:
            status = "✅" if has_it else "❌"
            if isinstance(has_it, int):
                points = has_it
                embed.add_field(
                    name=f"{status} {factor_name}",
                    value=f"{points}/{max_points} points",
                    inline=True
                )
            else:
                points = max_points if has_it else 0
                embed.add_field(
                    name=f"{status} {factor_name}",
                    value=f"{points}/{max_points} points",
                    inline=True
                )

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="threatlevel", description="View current threat level assessment (Admin only)")
    async def threatlevel(self, interaction: discord.Interaction):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        threat_data = await self._calculate_threat_level(guild)

        embed = discord.Embed(
            title=f"⚠️ Threat Level Assessment - {guild.name}",
            description=f"**Current Level:** {threat_data['level']}",
            color=threat_data["color"]
        )

        embed.add_field(
            name="Threat Score",
            value=f"{threat_data['score']}/100",
            inline=False
        )

        # Show factors
        for factor_name, max_points, value in threat_data['factors']:
            if isinstance(value, bool):
                status = "⚠️" if value else "✅"
                points = max_points if value else 0
                embed.add_field(
                    name=f"{status} {factor_name}",
                    value=f"{points}/{max_points} points",
                    inline=True
                )
            else:
                status = "⚠️" if value > max_points / 2 else "✅"
                points = min(max_points, value)
                embed.add_field(
                    name=f"{status} {factor_name}",
                    value=f"{points}/{max_points} points ({value})",
                    inline=True
                )

        embed.set_footer(text="Higher threat scores indicate greater risk")

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="logs", description="View security logs (Admin only)")
    @app_commands.describe(
        action="recent, punished, or raid",
        limit="Number of entries to show (default: 10)"
    )
    async def logs(self, interaction: discord.Interaction, action: str, limit: int = 10):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        action_l = action.lower().strip()
        limit = max(1, min(50, limit))

        if action_l == "punished":
            from database import get_punished_users
            punished = await get_punished_users(guild.id)
            
            if not punished:
                return await interaction.response.send_message(
                    embed=info_embed("Punished Users", "No users currently punished."),
                    ephemeral=False
                )

            embed = discord.Embed(
                title="🔨 Currently Punished Users",
                description=f"Showing {min(limit, len(punished))} of {len(punished)} punished users",
                color=0xFF4444
            )

            for user_data in punished[:limit]:
                member = guild.get_member(user_data["user_id"])
                name = member.name if member else f"<@{user_data['user_id']}>"
                punishment = user_data.get("punishment_type", "ban")
                punished_at = user_data.get("punished_at", "")
                
                embed.add_field(
                    name=f"{name} ({user_data['user_id']})",
                    value=f"**Punishment:** {punishment}\n**At:** {punished_at}",
                    inline=False
                )

            return await interaction.response.send_message(embed=embed, ephemeral=False)

        elif action_l == "recent":
            from database import log_action, get_guild
            # This would require a more complex query system
            return await interaction.response.send_message(
                embed=info_embed("Recent Logs", "Recent log viewing requires enhanced log storage system."),
                ephemeral=False
            )

        else:
            return await interaction.response.send_message(
                embed=error_embed("Use: `punished` or `recent`."),
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SecurityDashboard(bot))
