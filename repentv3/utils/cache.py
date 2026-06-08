"""
Repent - Role and channel snapshot/caching logic
"""

import discord
from database import cache_role, cache_channel, delete_cached_role, delete_cached_channel


async def snapshot_guild(guild: discord.Guild):
    """Cache all roles and channels for a guild. Called on_ready and when changes happen."""
    for role in guild.roles:
        try:
            await cache_role(guild.id, role)
        except Exception:
            pass
    for channel in guild.channels:
        try:
            await cache_channel(guild.id, channel)
        except Exception:
            pass


async def snapshot_role(role: discord.Role):
    """Cache a single role."""
    try:
        await cache_role(role.guild.id, role)
    except Exception:
        pass


async def snapshot_channel(channel: discord.abc.GuildChannel):
    """Cache a single channel."""
    try:
        await cache_channel(channel.guild.id, channel)
    except Exception:
        pass


async def remove_cached_role(role: discord.Role):
    try:
        await delete_cached_role(role.guild.id, role.id)
    except Exception:
        pass


async def remove_cached_channel(channel: discord.abc.GuildChannel):
    try:
        await delete_cached_channel(channel.guild.id, channel.id)
    except Exception:
        pass
