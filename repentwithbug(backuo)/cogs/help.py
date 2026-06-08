"""Repent - Slash Help

Adds /help for a unified slash-command help page.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show bot help and command listings")
    async def help_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ Repent Help & Documentation",
            description="Repent is an advanced, hardened discord security bot protecting against nukes, raids, and spam.",
            color=0x4488FF
        )

        embed.add_field(
            name="⚙️ Setup & Configuration",
            value="`/setup` - Interactive dropdown setup wizard\n"
                  "`/quicksetup` - One-command fast setup (logs, punishment, whitelist)\n"
                  "`/config view` - View current configuration\n"
                  "`/config logchannel <channel>` - Set log channel\n"
                  "`/config punishment <ban|kick|strip|timeout>` - Set action punishment\n"
                  "`/config threshold <action> <count> <seconds>` - Set threshold",
            inline=False
        )

        embed.add_field(
            name="🛡️ Antinuke & Webhooks",
            value="`/antinuke enable|disable|status` - Toggle antinuke modules\n"
                  "`/restore` - Restore deleted roles/channels from cache\n"
                  "`/punished` - List currently punished users\n"
                  "`/pardon <user>` - Remove user from punished list\n"
                  "`/nuke-webhooks` - Delete ALL webhooks in the guild",
            inline=False
        )

        embed.add_field(
            name="🚨 Anti-Raid System",
            value="`/raid status` - View anti-raid configuration & status\n"
                  "`/raid toggle <true|false>` - Manually toggle server lockdown\n"
                  "`/raid config` - Configure join rate, age filters, verification\n"
                  "`/raid unlock` - Manually lift lockdown\n"
                  "`/raid verification-setup` - Send verification message to verification channel",
            inline=False
        )

        embed.add_field(
            name="📦 Server Backup & selective Restore",
            value="`/backup create <name>` - Create manual backup snapshot of channels/roles\n"
                  "`/backup list` - List all backups created in this server\n"
                  "`/backup delete <backup_id>` - Delete a backup snapshot\n"
                  "`/backup restore <backup_id>` - Selective restoration wizard (Owner/Admin only)",
            inline=False
        )

        embed.add_field(
            name="🤖 AutoMod & Filters",
            value="`/automod <enable|disable>` - Toggle message automod\n"
                  "`/badword add|remove|list <word>` - Manage banned words list\n"
                  "`/ignore <channel> <module>` - Bypass channel for automod\n"
                  "`/unignore <channel>` - Remove channel bypass",
            inline=False
        )

        embed.add_field(
            name="👥 Trust Levels & Whitelists",
            value="`/whitelist add <user> <level>` - Whitelist user\n"
                  "`/whitelist remove <user>` - Remove user from whitelist\n"
                  "`/whitelist list` - View whitelisted users\n\n"
                  "**Trust Level 1 (Partial):** Bypasses AutoMod checks.\n"
                  "**Trust Level 2 (Full):** Bypasses AutoMod + Antinuke checks.\n"
                  "*Note: Guild Owner and Bot Owner have automatic Level 2 whitelist.*",
            inline=False
        )

        embed.set_footer(text="Repent Security | Secure and hardened")
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
