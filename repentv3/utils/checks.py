"""
Repent - Permission checks and decorators
"""

import discord
from discord import app_commands
from config import OWNER_ID


async def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_ID


async def is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False


async def is_mod(interaction: discord.Interaction) -> bool:
    if await is_admin(interaction):
        return True
    if isinstance(interaction.user, discord.Member):
        return (
            interaction.user.guild_permissions.kick_members
            or interaction.user.guild_permissions.ban_members
            or interaction.user.guild_permissions.manage_messages
        )
    return False


def owner_only():
    """Slash command check: owner only."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not await is_owner(interaction):
            raise app_commands.CheckFailure("This command is restricted to the bot owner.")
        return True
    return app_commands.check(predicate)


def admin_only():
    """Slash command check: admin or above."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not await is_admin(interaction):
            raise app_commands.CheckFailure("You need Administrator permission to use this command.")
        return True
    return app_commands.check(predicate)


def mod_only():
    """Slash command check: mod or above."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not await is_mod(interaction):
            raise app_commands.CheckFailure("You need moderation permissions to use this command.")
        return True
    return app_commands.check(predicate)
