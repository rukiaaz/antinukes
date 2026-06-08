"""
Repent - Embed builders
Clean, consistent embeds for all bot responses.
"""

import discord
from datetime import datetime, timezone
from config import BOT_NAME, COLOR_ALERT, COLOR_SUCCESS, COLOR_INFO, COLOR_WARNING


def _footer(embed: discord.Embed):
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=f"{BOT_NAME}", icon_url=None)
    return embed


def alert_embed(title: str, description: str = "") -> discord.Embed:
    """Red alert embed for antinuke triggers, punishments, critical events."""
    embed = discord.Embed(
        title=f"🚨 {title}",
        description=description,
        color=COLOR_ALERT,
    )
    return _footer(embed)


def success_embed(title: str, description: str = "") -> discord.Embed:
    """Green success embed for confirmations."""
    embed = discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=COLOR_SUCCESS,
    )
    return _footer(embed)


def info_embed(title: str, description: str = "") -> discord.Embed:
    """Blue info embed for status, lists, general info."""
    embed = discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=COLOR_INFO,
    )
    return _footer(embed)


def warning_embed(title: str, description: str = "") -> discord.Embed:
    """Yellow warning embed for cautions."""
    embed = discord.Embed(
        title=f"⚠️ {title}",
        description=description,
        color=COLOR_WARNING,
    )
    return _footer(embed)


def antinuke_embed(
    action: str,
    target: str,
    responsible: str,
    punishment: str,
    guild: discord.Guild,
) -> discord.Embed:
    """Standardized antinuke alert embed."""
    embed = discord.Embed(
        title="🚨 Antinuke Triggered",
        description=f"Suspicious activity detected in **{guild.name}**",
        color=COLOR_ALERT,
    )
    embed.add_field(name="Action", value=f"`{action}`", inline=True)
    embed.add_field(name="Target", value=target, inline=True)
    embed.add_field(name="Responsible", value=responsible, inline=True)
    embed.add_field(name="Punishment Applied", value=f"`{punishment}`", inline=False)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    return _footer(embed)


def mod_action_embed(
    action: str,
    moderator: discord.Member,
    target: discord.Member,
    reason: str,
    color: int = COLOR_INFO,
) -> discord.Embed:
    """Standardized moderation action embed for logging."""
    embed = discord.Embed(
        title=f"🛡️ {action}",
        color=color,
    )
    embed.add_field(name="Moderator", value=moderator.mention, inline=True)
    embed.add_field(name="Target", value=target.mention, inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    return _footer(embed)


def log_embed(
    title: str,
    fields: list,
    color: int = COLOR_INFO,
    thumbnail: str = None,
) -> discord.Embed:
    """
    Generic log embed with max 4 fields.
    fields: list of (name, value, inline) tuples
    """
    embed = discord.Embed(title=title, color=color)
    for name, value, inline in fields[:4]:
        embed.add_field(name=name, value=value, inline=inline)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    return _footer(embed)


def error_embed(description: str = "An error occurred.") -> discord.Embed:
    """Red error embed for command failures."""
    embed = discord.Embed(
        title="❌ Error",
        description=description,
        color=COLOR_ALERT,
    )
    return _footer(embed)
