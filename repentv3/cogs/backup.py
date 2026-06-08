"""Repent - Backup and Restore System

Allows administrators to manually backup server configuration (channels and roles) and selectively restore active or deleted channels/roles.
"""

from __future__ import annotations

import json
import uuid
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID
from database import (
    delete_backup,
    get_backups,
    get_backup,
    get_backup_channels,
    get_backup_roles,
    log_action,
    save_backup,
)
from utils.embeds import error_embed, info_embed, success_embed


class RestoreRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Restore Roles", style=discord.ButtonStyle.primary, emoji="🛡️", row=2)

    async def callback(self, interaction: discord.Interaction):
        view: BackupRestoreView = self.view
        guild = interaction.guild
        await interaction.response.defer(thinking=True, ephemeral=True)

        restored = 0
        existing_roles = {r.id for r in guild.roles}
        for r_data in view.all_roles:
            role_id = r_data.get("role_id")
            if role_id in existing_roles:
                continue
            if role_id == guild.default_role.id:
                continue

            try:
                await guild.create_role(
                    name=r_data.get("name", "restored-role"),
                    permissions=discord.Permissions(r_data.get("permissions", 0)),
                    color=discord.Color(r_data.get("color", 0)),
                    hoist=bool(r_data.get("hoist", 0)),
                    mentionable=bool(r_data.get("mentionable", 0)),
                    reason="[Repent Backup] Restored role",
                )
                restored += 1
            except Exception as e:
                print(f"[BACKUP] Failed to restore role {r_data.get('name')}: {e}")

        await interaction.followup.send(f"✅ Recreated {restored} missing role(s).", ephemeral=True)


class RestoreAllButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Restore All Channels", style=discord.ButtonStyle.success, emoji="⚡", row=2)

    async def callback(self, interaction: discord.Interaction):
        view: BackupRestoreView = self.view
        guild = interaction.guild
        await interaction.response.defer(thinking=True, ephemeral=True)

        recreated = 0
        reset_count = 0

        # 1. Recreate deleted channels
        for ch_data in view.deleted_channels:
            try:
                await view.recreate_channel(guild, ch_data)
                recreated += 1
            except Exception as e:
                print(f"[BACKUP] Failed to recreate {ch_data['name']}: {e}")

        # 2. Reset active channels
        for ch_data in view.active_channels:
            try:
                channel = guild.get_channel(ch_data["channel_id"])
                if channel:
                    await view.reset_channel_settings(guild, channel, ch_data)
                    reset_count += 1
            except Exception as e:
                print(f"[BACKUP] Failed to reset {ch_data['name']}: {e}")

        await interaction.followup.send(
            f"✅ Restored all: recreated {recreated} channel(s) and reset {reset_count} active channel(s).",
            ephemeral=True,
        )


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=2)

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        await interaction.response.edit_message(content="❌ Restoration cancelled.", embed=None, view=None)


class BackupRestoreView(discord.ui.View):
    """View presenting backup restoration options."""

    def __init__(
        self,
        bot: commands.Bot,
        user: discord.Member,
        backup_id: str,
        deleted_channels: list,
        active_channels: list,
        all_roles: list,
        all_channels: list,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user = user
        self.backup_id = backup_id
        self.deleted_channels = deleted_channels
        self.active_channels = active_channels
        self.all_roles = all_roles
        self.all_channels = all_channels

        # Add select menu for recreating deleted channels
        if self.deleted_channels:
            options = []
            for ch in self.deleted_channels[:25]:
                emoji = "📝" if ch["type"] == 0 else "🔊" if ch["type"] == 2 else "📁"
                options.append(
                    discord.SelectOption(
                        label=ch["name"],
                        value=str(ch["channel_id"]),
                        emoji=emoji,
                        description=f"Recreate deleted channel (ID: {ch['channel_id']})",
                    )
                )

            select_del = discord.ui.Select(
                placeholder="Recreate Specific Deleted Channels...",
                options=options,
                min_values=1,
                max_values=len(options),
                custom_id="backup_recreate_channels",
                row=0,
            )
            select_del.callback = self.on_recreate_select
            self.add_item(select_del)

        # Add select menu for resetting active channels
        if self.active_channels:
            options = []
            for ch in self.active_channels[:25]:
                emoji = "📝" if ch["type"] == 0 else "🔊" if ch["type"] == 2 else "📁"
                options.append(
                    discord.SelectOption(
                        label=ch["name"],
                        value=str(ch["channel_id"]),
                        emoji=emoji,
                        description="Reset active channel overwrites/settings",
                    )
                )

            select_act = discord.ui.Select(
                placeholder="Reset Specific Active Channels...",
                options=options,
                min_values=1,
                max_values=len(options),
                custom_id="backup_reset_channels",
                row=1,
            )
            select_act.callback = self.on_reset_select
            self.add_item(select_act)

        # Add control buttons
        self.add_item(RestoreRolesButton())
        self.add_item(RestoreAllButton())
        self.add_item(CancelButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Only the command invoker can use this menu.", ephemeral=True)
            return False
        return True

    async def on_recreate_select(self, interaction: discord.Interaction):
        channel_ids = [int(v) for v in interaction.data["values"]]
        guild = interaction.guild
        await interaction.response.defer(thinking=True, ephemeral=True)

        recreated = 0
        for ch_data in self.deleted_channels:
            if ch_data["channel_id"] in channel_ids:
                try:
                    await self.recreate_channel(guild, ch_data)
                    recreated += 1
                except Exception as e:
                    print(f"[BACKUP] Failed to recreate {ch_data['name']}: {e}")

        await interaction.followup.send(f"✅ Successfully recreated {recreated} channel(s).", ephemeral=True)

    async def on_reset_select(self, interaction: discord.Interaction):
        channel_ids = [int(v) for v in interaction.data["values"]]
        guild = interaction.guild
        await interaction.response.defer(thinking=True, ephemeral=True)

        reset_count = 0
        for ch_data in self.active_channels:
            if ch_data["channel_id"] in channel_ids:
                try:
                    channel = guild.get_channel(ch_data["channel_id"])
                    if channel:
                        await self.reset_channel_settings(guild, channel, ch_data)
                        reset_count += 1
                except Exception as e:
                    print(f"[BACKUP] Failed to reset {ch_data['name']}: {e}")

        await interaction.followup.send(f"✅ Successfully reset settings for {reset_count} active channel(s).", ephemeral=True)

    async def recreate_channel(self, guild: discord.Guild, ch_data: dict):
        category_id = ch_data.get("category_id", 0)
        category = guild.get_channel(category_id) if category_id else None

        payload_name = ch_data.get("name", "restored")
        topic = ch_data.get("topic", "") or None
        nsfw = bool(ch_data.get("nsfw", 0))
        slowmode_delay = ch_data.get("slowmode", 0) or 0
        position = ch_data.get("position", 0)
        channel_type = ch_data.get("type", 0)

        overwrites_dict = json.loads(ch_data.get("json_overwrites", "{}"))
        overwrites = {}
        for target_id_str, o_data in overwrites_dict.items():
            target_id = int(target_id_str)
            target = None
            if o_data["type"] == "role":
                target = guild.get_role(target_id)
            else:
                target = guild.get_member(target_id)
                if not target:
                    try:
                        target = await guild.fetch_member(target_id)
                    except Exception:
                        pass
            if target:
                overwrites[target] = discord.PermissionOverwrite.from_pair(
                    discord.Permissions(o_data["allow"]),
                    discord.Permissions(o_data["deny"]),
                )

        if channel_type == 0:
            await guild.create_text_channel(
                name=payload_name,
                category=category,
                position=position,
                topic=topic,
                nsfw=nsfw,
                slowmode_delay=slowmode_delay,
                overwrites=overwrites,
                reason="[Repent Backup] Recreated from backup",
            )
        elif channel_type == 2:
            await guild.create_voice_channel(
                name=payload_name,
                category=category,
                position=position,
                overwrites=overwrites,
                reason="[Repent Backup] Recreated from backup",
            )
        elif channel_type == 4:
            await guild.create_category(
                name=payload_name,
                position=position,
                overwrites=overwrites,
                reason="[Repent Backup] Recreated from backup",
            )

    async def reset_channel_settings(
        self, guild: discord.Guild, channel: discord.abc.GuildChannel, ch_data: dict
    ):
        payload_name = ch_data.get("name")
        topic = ch_data.get("topic", "") or None
        nsfw = bool(ch_data.get("nsfw", 0))
        slowmode_delay = ch_data.get("slowmode", 0) or 0
        position = ch_data.get("position", 0)

        overwrites_dict = json.loads(ch_data.get("json_overwrites", "{}"))
        overwrites = {}
        for target_id_str, o_data in overwrites_dict.items():
            target_id = int(target_id_str)
            target = None
            if o_data["type"] == "role":
                target = guild.get_role(target_id)
            else:
                target = guild.get_member(target_id)
                if not target:
                    try:
                        target = await guild.fetch_member(target_id)
                    except Exception:
                        pass
            if target:
                overwrites[target] = discord.PermissionOverwrite.from_pair(
                    discord.Permissions(o_data["allow"]),
                    discord.Permissions(o_data["deny"]),
                )

        edit_kwargs = {
            "name": payload_name,
            "position": position,
            "overwrites": overwrites,
            "reason": "[Repent Backup] Reset channel from backup",
        }
        if isinstance(channel, discord.TextChannel):
            edit_kwargs["topic"] = topic
            edit_kwargs["nsfw"] = nsfw
            edit_kwargs["slowmode_delay"] = slowmode_delay

        await channel.edit(**edit_kwargs)


class Backup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator or interaction.user.id == OWNER_ID

    @app_commands.default_permissions(administrator=True)
    class BackupGroup(app_commands.Group):
        def __init__(self, bot: commands.Bot, cog: "Backup"):
            super().__init__(name="backup", description="Server config backups and restoration")
            self.bot = bot
            self.cog = cog

        @app_commands.command(name="create", description="Create a manual backup snapshot of server roles and channels (Admin only)")
        @app_commands.describe(name="Description name for this backup")
        async def create(self, interaction: discord.Interaction, name: str):
            if not await self.cog._is_admin(interaction):
                return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

            guild = interaction.guild
            await interaction.response.defer(thinking=True, ephemeral=True)

            backup_id = f"bk_{uuid.uuid4().hex[:8]}"

            try:
                roles = list(guild.roles)
                channels = list(guild.channels)
                await save_backup(guild.id, backup_id, name, roles, channels)
                await log_action(guild.id, "backup_create", interaction.user.id, {"backup_id": backup_id, "name": name})

                embed = success_embed(
                    "Backup Created Successfully",
                    f"Server backup has been saved!\n\n"
                    f"**Backup Name:** {name}\n"
                    f"**Backup ID:** `{backup_id}`\n"
                    f"**Roles Saved:** {len(roles)}\n"
                    f"**Channels Saved:** {len(channels)}",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.followup.send(embed=error_embed(f"Failed to create backup: {e}"), ephemeral=True)

        @app_commands.command(name="list", description="List all created backups for this server (Admin only)")
        async def list_backups(self, interaction: discord.Interaction):
            if not await self.cog._is_admin(interaction):
                return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

            guild = interaction.guild
            await interaction.response.defer(thinking=True, ephemeral=True)

            backups = await get_backups(guild.id)
            if not backups:
                return await interaction.followup.send(embed=info_embed("Backups", "No manual backups found in this server."), ephemeral=True)

            lines = []
            for b in backups[:15]:
                lines.append(
                    f"**{b['name']}** — ID: `{b['backup_id']}` — *{b['created_at'][:19].replace('T', ' ')}*"
                )

            embed = info_embed("Server Backups List", "\n".join(lines))
            await interaction.followup.send(embed=embed, ephemeral=True)

        @app_commands.command(name="delete", description="Delete a server backup snapshot (Admin only)")
        @app_commands.describe(backup_id="The ID of the backup snapshot to delete")
        async def delete(self, interaction: discord.Interaction, backup_id: str):
            if not await self.cog._is_admin(interaction):
                return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

            guild = interaction.guild
            await interaction.response.defer(thinking=True, ephemeral=True)

            backup = await get_backup(guild.id, backup_id)
            if not backup:
                return await interaction.followup.send(embed=error_embed(f"Backup with ID `{backup_id}` not found."), ephemeral=True)

            await delete_backup(guild.id, backup_id)
            await log_action(guild.id, "backup_delete", interaction.user.id, {"backup_id": backup_id})
            await interaction.followup.send(embed=success_embed("Backup Deleted", f"Backup snapshot `{backup_id}` has been deleted."), ephemeral=True)

        @app_commands.command(
            name="restore",
            description="Restore channels and roles from backup (Admin only)",
        )
        @app_commands.describe(backup_id="Backup ID (e.g. bk_...) OR exact backup name to restore")
        async def restore(self, interaction: discord.Interaction, backup_id: str):
            if not await self.cog._is_admin(interaction):
                return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

            guild = interaction.guild
            await interaction.response.defer(thinking=True)

            resolved_backup_id = backup_id
            backup = await get_backup(guild.id, backup_id)
            if not backup:
                # Treat input as exact backup name
                backups = await get_backups(guild.id)
                matches = [b for b in backups if b.get("name") == backup_id]
                if not matches:
                    return await interaction.followup.send(embed=error_embed(f"Backup `{backup_id}` not found by ID or exact name."), ephemeral=True)
                backup = matches[0]
                resolved_backup_id = backup["backup_id"]

            roles = await get_backup_roles(resolved_backup_id)
            channels = await get_backup_channels(resolved_backup_id)

            existing_channel_ids = {c.id for c in guild.channels}
            deleted_channels = []
            active_channels = []

            for ch in channels:
                if ch["channel_id"] not in existing_channel_ids:
                    deleted_channels.append(ch)
                else:
                    active_channels.append(ch)

            embed = discord.Embed(
                title=f"📦 Restore Backup: {backup['name']}",
                description=(
                    "Use the menus and buttons below to selectively recreate missing channels, "
                    "reset active channels' permissions and settings, or restore missing roles."
                ),
                color=0x4488FF,
            )
            embed.add_field(name="Backup ID", value=f"`{resolved_backup_id}`", inline=True)
            embed.add_field(name="Saved At", value=f"*{backup['created_at'][:19].replace('T', ' ')}*", inline=True)
            embed.add_field(name="Channels in Backup", value=str(len(channels)), inline=True)
            embed.add_field(name="Active Channels (in guild)", value=str(len(active_channels)), inline=True)
            embed.add_field(name="Deleted Channels (missing)", value=str(len(deleted_channels)), inline=True)
            embed.add_field(name="Roles in Backup", value=str(len(roles)), inline=True)
            embed.set_footer(text="Repent Security System")

            view = BackupRestoreView(
                bot=self.bot,
                user=interaction.user,
                backup_id=resolved_backup_id,
                deleted_channels=deleted_channels,
                active_channels=active_channels,
                all_roles=roles,
                all_channels=channels,
            )

            await interaction.followup.send(embed=embed, view=view)

        async def cog_load(self):
            try:
                self.bot.tree.add_command(self.BackupGroup(self.bot, self))
            except Exception:
                pass

    async def cog_load(self):
        try:
            self.bot.tree.add_command(self.BackupGroup(self.bot, self))
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Backup(bot))

