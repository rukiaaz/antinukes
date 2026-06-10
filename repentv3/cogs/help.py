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
                label="⚙️ Setup & Configuration",
                description="Setup wizard, config, whitelist",
                emoji="⚙️",
                value="setup"
            ),
            discord.SelectOption(
                label="🛡️ Antinuke & Security",
                description="Antinuke, restore, punished users",
                emoji="🛡️",
                value="antinuke"
            ),
            discord.SelectOption(
                label="🚨 Anti-Raid System",
                description="Raid protection, verification",
                emoji="🚨",
                value="antiraid"
            ),
            discord.SelectOption(
                label="👮 Advanced Moderation",
                description="Mass actions, notes, strikes",
                emoji="👮",
                value="advanced_mod"
            ),
            discord.SelectOption(
                label="📦 Backup & Restore",
                description="Server backups and restoration",
                emoji="📦",
                value="backup"
            ),
            discord.SelectOption(
                label="🤖 AutoMod & Filters",
                description="Spam protection, bad words",
                emoji="🤖",
                value="automod"
            ),
            discord.SelectOption(
                label="👥 Trust Levels & Whitelists",
                description="User and bot whitelisting",
                emoji="👥",
                value="whitelist"
            ),
            discord.SelectOption(
                label="🎉 Welcome & Events",
                description="Welcome, farewell, boost messages",
                emoji="🎉",
                value="welcome"
            ),
            discord.SelectOption(
                label="🔐 Verification System",
                description="Custom verification with embeds",
                emoji="🔐",
                value="verification"
            ),
            discord.SelectOption(
                label="📊 Security Dashboard",
                description="Security scoring and threat levels",
                emoji="📊",
                value="dashboard"
            ),
            discord.SelectOption(
                label="🎮 Leveling & XP",
                description="XP system, ranks, leaderboards",
                emoji="🎮",
                value="leveling"
            ),
            discord.SelectOption(
                label="🔧 Utility Commands",
                description="Userinfo, serverinfo, ping, etc.",
                emoji="🔧",
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
            title=f"🛡️ Repent Bot Commands - {category}",
            color=0x4488FF
        )

        if category == "setup":
            embed.description = "Setup and configuration commands for the bot."
            embed.add_field(
                name="Commands",
                value="`/setup` - Interactive dropdown setup wizard\n"
                      "`/quicksetup` - One-command fast setup (logs, punishment, whitelist)\n"
                      "`/config view` - View current configuration\n"
                      "`/config logchannel <channel>` - Set log channel\n"
                      "`/config modchannel <channel>` - Set mod channel\n"
                      "`/config punishment <ban|kick|strip|timeout>` - Set punishment type\n"
                      "`/config threshold <action> <count> <seconds>` - Set antinuke threshold\n"
                      "`/antinuke enable` - Enable antinuke system\n"
                      "`/antinuke disable` - Disable antinuke system\n"
                      "`/antinuke status` - View antinuke status\n"
                      "`/antinukeconfig sensitivity <level>` - Set antinuke sensitivity\n"
                      "`/antinukeconfig lockdown <true/false>` - Set lockdown mode\n"
                      "`/antinukeconfig instantrestore <true/false>` - Toggle instant restore",
                inline=False
            )

        elif category == "antinuke":
            embed.description = "Antinuke and security commands for server protection."
            embed.add_field(
                name="Commands",
                value="`/antinuke enable` - Enable antinuke system\n"
                      "`/antinuke disable` - Disable antinuke system\n"
                      "`/antinuke status` - View antinuke status\n"
                      "`/antinukeconfig sensitivity <level>` - Set antinuke sensitivity\n"
                      "`/antinukeconfig lockdown <true/false>` - Set lockdown mode\n"
                      "`/antinukeconfig instantrestore <true/false>` - Toggle instant restore\n"
                      "`/antinukeconfig logging <true/false>` - Toggle detailed logging\n"
                      "`/safeadmin add <user>` - Add safe admin (immune to antinuke)\n"
                      "`/safeadmin remove <user>` - Remove safe admin\n"
                      "`/safeadmin list` - View safe admins\n"
                      "`/restore` - Restore deleted roles/channels from cache\n"
                      "`/punished` - List currently punished users\n"
                      "`/pardon <user>` - Remove user from punished list\n"
                      "`/nuke-webhooks` - Delete ALL webhooks in the guild",
                inline=False
            )

        elif category == "antiraid":
            embed.description = "Anti-raid system and verification commands."
            embed.add_field(
                name="Commands",
                value="`/raid status` - View anti-raid configuration & status\n"
                      "`/raid toggle <true|false>` - Manually toggle server lockdown\n"
                      "`/raid unlock` - Manually lift lockdown\n"
                      "`/raid sensitivity <level>` - Set raid detection sensitivity (1-10)\n"
                      "`/raid maxjoins <count>` - Set max joins before lockdown\n"
                      "`/raid minage <days>` - Set minimum account age\n"
                      "`/raid quarantine <channel>` - Set quarantine channel\n"
                      "`/raid webhook <url>` - Set webhook for raid alerts\n"
                      "`/raid auto <true|false>` - Toggle automatic raid mode\n"
                      "`/raidscore <user>` - Check raid score for a user",
                inline=False
            )

        elif category == "backup":
            embed.description = "Server backup and restoration commands."
            embed.add_field(
                name="Commands",
                value="`/backup create <name>` - Create manual backup snapshot\n"
                      "`/backup list` - List all backups created in this server\n"
                      "`/backup delete <backup_id>` - Delete a backup snapshot\n"
                      "`/backup restore <backup_id>` - Selective restoration wizard",
                inline=False
            )

        elif category == "automod":
            embed.description = "AutoMod and content filter commands."
            embed.add_field(
                name="Commands",
                value="`/automod enable` - Enable message automod\n"
                      "`/automod disable` - Disable message automod\n"
                      "`/badword add <word>` - Add word to bad words list\n"
                      "`/badword remove <word>` - Remove word from bad words list\n"
                      "`/badword list` - List all bad words\n"
                      "`/ignore <channel> <module>` - Bypass channel for automod\n"
                      "`/unignore <channel>` - Remove channel bypass",
                inline=False
            )

        elif category == "moderation":
            embed.description = "Moderation commands for managing users."
            embed.add_field(
                name="Commands",
                value="`/ban <user> [reason] [delete_days]` - Ban a user\n"
                      "`/unban <user_id> [reason]` - Unban a user by ID\n"
                      "`/kick <user> [reason]` - Kick a user\n"
                      "`/timeout <user> <duration> [reason]` - Timeout a user\n"
                      "`/warn <user> <reason>` - Warn a user\n"
                      "`/warnings <user>` - View user warnings\n"
                      "`/clearwarnings <user>` - Clear user warnings\n"
                      "`/hardban <user> [reason]` - Hardban a user (auto-reban on rejoin)\n"
                      "`/unhardban <user_id>` - Remove hardban\n"
                      "`/purge <count>` - Purge messages\n"
                      "`/lock <channel>` - Lock a channel\n"
                      "`/unlock <channel>` - Unlock a channel\n"
                      "`/slowmode <channel> <seconds>` - Set slowmode",
                inline=False
            )

        elif category == "whitelist":
            embed.description = "User and bot whitelist management commands."
            embed.add_field(
                name="Commands",
                value="`/whitelist add <user> <level>` - Whitelist a user\n"
                      "`/whitelist remove <user>` - Remove user from whitelist\n"
                      "`/whitelist list` - View whitelisted users\n"
                      "`/botwhitelist add <bot> [reason]` - Whitelist a bot\n"
                      "`/botwhitelist remove <bot>` - Remove bot from whitelist\n"
                      "`/botwhitelist list` - View whitelisted bots\n"
                      "`/safeadmin add <user>` - Add safe admin (immune to antinuke)\n"
                      "`/safeadmin remove <user>` - Remove safe admin\n"
                      "`/safeadmin list` - View safe admins\n\n"
                      "**Trust Level 1 (Partial):** Bypasses AutoMod checks.\n"
                      "**Trust Level 2 (Full):** Bypasses AutoMod + Antinuke checks.\n"
                      "**Bot Whitelist:** Bots won't be punished by antinuke.\n"
                      "**Safe Admins:** Immune to all antinuke punishments.",
                inline=False
            )

        elif category == "welcome":
            embed.description = "Welcome, farewell, and boost event configuration."
            embed.add_field(
                name="Commands",
                value="`/welcome set <channel>` - Set welcome channel\n"
                      "`/welcome message [text]` - Set/view welcome message\n"
                      "`/welcome autorole <role>` - Set autorole\n"
                      "`/farewell set <channel>` - Set farewell channel\n"
                      "`/farewell message [text]` - Set/view farewell message\n"
                      "`/boost set <channel>` - Set boost channel\n"
                      "`/boost message [text]` - Set/view boost message",
                inline=False
            )

        elif category == "leveling":
            embed.description = "XP and leveling system commands."
            embed.add_field(
                name="Commands",
                value="`/rank [user]` - View user rank and XP\n"
                      "`/leaderboard` - View server leaderboard\n"
                      "`/levelroles` - View level reward roles\n"
                      "`/addlevelrole <level> <role>` - Add level reward role\n"
                      "`/removelevelrole <level>` - Remove level reward role\n"
                      "`/setlevelchannel <channel>` - Set level-up notification channel\n"
                      "`/enablelevelmessages` - Enable DM level-up messages\n"
                      "`/disablelevelmessages` - Disable DM level-up messages",
                inline=False
            )

        elif category == "advanced_mod":
            embed.description = "Advanced moderation commands for mass actions and user management."
            embed.add_field(
                name="Commands",
                value="`/massban <users> <reason>` - Ban multiple users at once\n"
                      "`/masskick <users> <reason>` - Kick multiple users at once\n"
                      "`/softban <user> <reason>` - Ban and unban (deletes messages)\n"
                      "`/tempban <user> <duration> <reason>` - Temporary ban\n"
                      "`/note <user> <note>` - Add private moderation note\n"
                      "`/notes <user>` - View user notes\n"
                      "`/strike <user> <reason>` - Add strike (3+ = auto punishment)\n"
                      "`/strikes <user>` - View user strikes\n"
                      "`/forgive <user>` - Remove a strike\n"
                      "`/clearstrikes <user>` - Clear all user strikes\n"
                      "`/channellock <channel> <reason>` - Lock channel\n"
                      "`/channelunlock <channel>` - Unlock channel\n"
                      "`/setslowmode <channel> <seconds>` - Set slowmode\n"
                      "`/nsfw <channel>` - Mark channel as NSFW\n"
                      "`/nsfwremove <channel>` - Remove NSFW marking",
                inline=False
            )

        elif category == "verification":
            embed.description = "Custom verification system with embeds and roles."
            embed.add_field(
                name="Commands",
                value="`/verification set <channel>` - Set verification channel\n"
                      "`/verification role <role>` - Set verification role\n"
                      "`/verification message <text>` - Set verification message\n"
                      "`/verification embed title <text>` - Set embed title\n"
                      "`/verification embed color <hex>` - Set embed color\n"
                      "`/verification embed button <text>` - Set button text\n"
                      "`/verification send` - Send verification message\n"
                      "`/verification disable` - Disable verification\n"
                      "`/verification status` - View verification status",
                inline=False
            )

        elif category == "dashboard":
            embed.description = "Security monitoring dashboard and threat assessment."
            embed.add_field(
                name="Commands",
                value="`/dashboard` - Show comprehensive security dashboard\n"
                      "`/securityscore` - View detailed security score breakdown\n"
                      "`/threatlevel` - View current threat level assessment\n"
                      "`/logs <action> <limit>` - View security logs",
                inline=False
            )

        elif category == "utility":
            embed.description = "Utility and information commands."
            embed.add_field(
                name="Commands",
                value="`/userinfo [user]` - Show information about a user\n"
                      "`/serverinfo` - Show server information\n"
                      "`/roleinfo <role>` - Show role information\n"
                      "`/channelinfo [channel]` - Show channel information\n"
                      "`/avatar [user]` - Show user avatar\n"
                      "`/ping` - Show bot latency\n"
                      "`/uptime` - Show bot uptime\n"
                      "`/botinfo` - Show bot information\n"
                      "`/afk [reason]` - Set AFK status\n"
                      "`/afk remove` - Remove AFK status",
                inline=False
            )

        embed.set_footer(text="Repent Security Bot | Use /help to see this menu again")
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
            title="🛡️ Repent Bot Help",
            description="Repent is an advanced Discord security bot protecting against nukes, raids, and spam.\n\n**Select a category below to view available commands:**",
            color=0x4488FF
        )
        embed.add_field(
            name="🔒 Security Features",
            value="Antinuke • Anti-Raid • AutoMod • Webhook Protection",
            inline=False
        )
        embed.add_field(
            name="👮 Moderation Tools",
            value="Ban • Kick • Timeout • Warnings • Hardban",
            inline=False
        )
        embed.add_field(
            name="🎉 Engagement Features",
            value="Welcome • Farewell • Boost Messages • Leveling System",
            inline=False
        )
        embed.set_footer(text="Made easy - Select a category below to get started!")

        view = HelpView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
