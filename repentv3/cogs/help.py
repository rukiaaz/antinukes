"""Repent - Slash Help

Adds /help for a unified dropdown-based command menu.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class HelpDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Setup & Configuration",
                description="Setup wizard, config, whitelist",
                value="setup"
            ),
            discord.SelectOption(
                label="Antinuke & Security",
                description="Antinuke, restore, punished users",
                value="antinuke"
            ),
            discord.SelectOption(
                label="Anti-Raid System",
                description="Raid protection, verification",
                value="antiraid"
            ),
            discord.SelectOption(
                label="Backup & Restore",
                description="Server backups and restoration",
                value="backup"
            ),
            discord.SelectOption(
                label="Trust Levels & Whitelists",
                description="User and bot whitelisting",
                value="whitelist"
            ),
            discord.SelectOption(
                label="Verification System",
                description="Custom verification with embeds",
                value="verification"
            ),
            discord.SelectOption(
                label="Security Dashboard",
                description="Security scoring and threat levels",
                value="dashboard"
            ),
            discord.SelectOption(
                label="Moderation",
                description="Ban, kick, timeout, warnings",
                value="moderation"
            ),
            discord.SelectOption(
                label="Advanced Moderation",
                description="Mass actions, notes, strikes",
                value="advanced_mod"
            ),
            discord.SelectOption(
                label="Utility Commands",
                description="Userinfo, serverinfo, ping, etc.",
                value="utility"
            ),
        ]
        super().__init__(
            placeholder="Select a category to view commands...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = discord.Embed(
            title=f"Repent Bot Commands - {category}",
            color=0x4488FF
        )

        if category == "setup":
            embed.description = "Bot setup and configuration"
            embed.add_field(
                name="Commands",
                value="`/setup` - Interactive setup wizard\n"
                      "`/quicksetup` - Quick setup (logs, punishment, whitelist)\n"
                      "`/config view` - View configuration\n"
                      "`/config logchannel` - Set log channel\n"
                      "`/config modchannel` - Set mod channel\n"
                      "`/config punishment` - Set punishment type\n"
                      "`/config threshold` - Set antinuke threshold\n"
                      "`/antinuke enable/disable` - Toggle antinuke\n"
                      "`/antinuke status` - View antinuke status\n"
                      "`/antinukeconfig sensitivity` - Set sensitivity\n"
                      "`/antinukeconfig lockdown` - Toggle lockdown\n"
                      "`/antinukeconfig instantrestore` - Toggle instant restore\n"
                      "`/rolewhitelist add/remove` - Manage role whitelists",
                inline=False
            )

        elif category == "antinuke":
            embed.description = "Antinuke and security commands"
            embed.add_field(
                name="Commands",
                value="`/antinuke enable/disable` - Toggle antinuke\n"
                      "`/antinuke status` - View status\n"
                      "`/antinukeconfig sensitivity` - Set sensitivity\n"
                      "`/antinukeconfig lockdown` - Toggle lockdown\n"
                      "`/antinukeconfig instantrestore` - Toggle instant restore\n"
                      "`/antinukeconfig logging` - Toggle logging\n"
                      "`/safeadmin add/remove` - Manage safe admins\n"
                      "`/safeadmin list` - View safe admins\n"
                      "`/antinuke_restore` - Restore deleted roles/channels\n"
                      "`/punished` - List punished users\n"
                      "`/pardon` - Remove user from punished list",
                inline=False
            )

        elif category == "antiraid":
            embed.description = "Anti-raid system commands"
            embed.add_field(
                name="Commands",
                value="`/raid status` - View configuration & status\n"
                      "`/raid toggle` - Toggle server lockdown\n"
                      "`/raid unlock` - Lift lockdown\n"
                      "`/raid sensitivity` - Set detection sensitivity\n"
                      "`/raid maxjoins` - Set max joins before lockdown\n"
                      "`/raid minage` - Set minimum account age\n"
                      "`/raid quarantine` - Set quarantine channel\n"
                      "`/raid webhook` - Set raid alert webhook\n"
                      "`/raid auto` - Toggle automatic raid mode\n"
                      "`/raidscore` - Check user raid score",
                inline=False
            )

        elif category == "backup":
            embed.description = "Server backup and restoration"
            embed.add_field(
                name="Commands",
                value="`/backup create` - Create backup snapshot\n"
                      "`/backup list` - List all backups\n"
                      "`/backup delete` - Delete backup\n"
                      "`/backup restore` - Restore from backup",
                inline=False
            )

        elif category == "moderation":
            embed.description = "User moderation commands"
            embed.add_field(
                name="Commands",
                value="`/ban` - Ban a user\n"
                      "`/unban` - Unban a user\n"
                      "`/kick` - Kick a user\n"
                      "`/timeout` - Timeout a user\n"
                      "`/untimeout` - Remove timeout\n"
                      "`/warn` - Warn a user\n"
                      "`/warnings` - View warnings\n"
                      "`/clearwarns` - Clear warnings\n"
                      "`/hardban` - Hardban (auto-reban)\n"
                      "`/unhardban` - Remove hardban\n"
                      "`/purge` - Purge messages\n"
                      "`/purgeuser` - Purge messages from user\n"
                      "`/lock/unlock` - Lock/unlock channel\n"
                      "`/slowmode` - Set slowmode\n"
                      "`/nick` - Change nickname\n"
                      "`/roleadd` - Add role to user\n"
                      "`/roleremove` - Remove role from user",
                inline=False
            )

        elif category == "whitelist":
            embed.description = "User and bot whitelist management"
            embed.add_field(
                name="Commands",
                value="`/whitelist add/remove` - Manage user whitelist\n"
                      "`/whitelist list` - View whitelisted users\n"
                      "`/botwhitelist add/remove` - Manage bot whitelist\n"
                      "`/botwhitelist list` - View whitelisted bots\n"
                      "`/safeadmin add/remove` - Manage safe admins\n"
                      "`/safeadmin list` - View safe admins\n"
                      "`/rolewhitelist add/remove` - Manage role whitelists\n\n"
                      "**Level 1:** Bypasses AutoMod\n"
                      "**Level 2:** Bypasses AutoMod + Antinuke\n"
                      "**Bot Whitelist:** Bots immune to antinuke\n"
                      "**Safe Admins:** Immune to all punishments",
                inline=False
            )

        elif category == "advanced_mod":
            embed.description = "Advanced moderation and mass actions"
            embed.add_field(
                name="Commands",
                value="`/massban` - Ban multiple users\n"
                      "`/masskick` - Kick multiple users\n"
                      "`/softban` - Ban and unban (deletes messages)\n"
                      "`/tempban` - Temporary ban\n"
                      "`/note` - Add moderation note\n"
                      "`/notes` - View user notes\n"
                      "`/strike` - Add strike (3+ = auto punishment)\n"
                      "`/strikes` - View user strikes\n"
                      "`/forgive` - Remove strike\n"
                      "`/clearstrikes` - Clear all strikes\n"
                      "`/channellock/unlock` - Lock/unlock channel\n"
                      "`/setslowmode` - Set slowmode\n"
                      "`/nsfw` - Mark channel as NSFW\n"
                      "`/nsfwremove` - Remove NSFW marking",
                inline=False
            )

        elif category == "verification":
            embed.description = "Custom verification system"
            embed.add_field(
                name="Commands",
                value="`/verification` - Configure verification system\n"
                      "Configure channel, role, message, embed settings",
                inline=False
            )

        elif category == "dashboard":
            embed.description = "Security monitoring and threat assessment"
            embed.add_field(
                name="Commands",
                value="`/dashboard` - Show security dashboard\n"
                      "`/securityscore` - View security score breakdown\n"
                      "`/threatlevel` - View threat level assessment\n"
                      "`/logs` - View security logs",
                inline=False
            )

        elif category == "utility":
            embed.description = "Utility and information commands"
            embed.add_field(
                name="Commands",
                value="`/userinfo` - Show user information\n"
                      "`/serverinfo` - Show server information\n"
                      "`/roleinfo` - Show role information\n"
                      "`/channelinfo` - Show channel information\n"
                      "`/avatar` - Show user avatar\n"
                      "`/ping` - Show bot latency\n"
                      "`/uptime` - Show bot uptime\n"
                      "`/botinfo` - Show bot information\n"
                      "`/afk` - Set AFK status\n"
                      "`/afk remove` - Remove AFK status\n"
                      "`/invite` - Get bot invite link\n"
                      "`/health` - Check bot health status",
                inline=False
            )

        embed.set_footer(text="Repent Security Bot | Use /help to see this menu")
        await interaction.response.edit_message(embed=embed)


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(HelpDropdown(bot))


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all bot commands in a dropdown menu")
    async def help_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Repent Bot Help",
            description="Advanced Discord security bot. Select a category below to view commands.",
            color=0x4488FF
        )
        embed.add_field(
            name="Security",
            value="Antinuke • Anti-Raid • AutoMod",
            inline=False
        )
        embed.add_field(
            name="Moderation",
            value="Ban • Kick • Timeout • Warnings",
            inline=False
        )
        embed.add_field(
            name="Features",
            value="Welcome • Leveling • Backup",
            inline=False
        )
        embed.set_footer(text="Select a category to get started")

        view = HelpView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
