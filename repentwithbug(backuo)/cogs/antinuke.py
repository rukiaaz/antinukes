"""Repent - Antinuke System

Hardened Antinuke system protecting against nuke/bulk moderation actions, Webhook threats, and Permission Escalations.
Features:
- Fast in-memory sliding window rate tracker.
- Fast-path listeners for member bans/kicks, channel modifications, role modifications, emojis/stickers.
- Automated webhook scan/delete upon unauthorized creation.
- Instant punishment for permission escalation (giving self/others dangerous perms).
- Instant punishment for unauthorized vanity URL changes.
- Webhook cleanup: deletes all webhooks created by a punished attacker.
- Auto-restore deleted roles/channels from database snapshot cache.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from collections import deque

import discord
from discord.ext import commands

from config import DEFAULT_PUNISHMENT, OWNER_ID
from database import (
    add_punished_user,
    get_whitelist_entry,
    get_guild,
    get_cached_roles,
    get_cached_channels,
    remove_punished_user,
    get_punished_users,
    log_action,
    get_antinuke_threshold,
)
from utils.embeds import antinuke_embed, error_embed, info_embed, success_embed
from utils.cache import snapshot_guild


class InMemoryRateTracker:
    """Fast, in-memory sliding window rate tracker to replace DB calls."""
    def __init__(self):
        # guild_id -> user_id -> action_type -> deque of datetime
        self._tracks: Dict[int, Dict[int, Dict[str, deque]]] = {}

    def add_event(self, guild_id: int, user_id: int, action_type: str) -> None:
        if guild_id not in self._tracks:
            self._tracks[guild_id] = {}
        if user_id not in self._tracks[guild_id]:
            self._tracks[guild_id][user_id] = {}
        if action_type not in self._tracks[guild_id][user_id]:
            self._tracks[guild_id][user_id][action_type] = deque()
        self._tracks[guild_id][user_id][action_type].append(datetime.utcnow())

    def count_events(self, guild_id: int, user_id: int, action_type: str, window_seconds: int) -> int:
        guild_tracks = self._tracks.get(guild_id)
        if not guild_tracks:
            return 0
        user_tracks = guild_tracks.get(user_id)
        if not user_tracks:
            return 0
        events = user_tracks.get(action_type)
        if not events:
            return 0

        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        while events and events[0] <= cutoff:
            events.popleft()

        return len(events)

    def clear_events(self, guild_id: int, user_id: int, action_type: str) -> None:
        guild_tracks = self._tracks.get(guild_id)
        if not guild_tracks:
            return
        user_tracks = guild_tracks.get(user_id)
        if not user_tracks:
            return
        if action_type in user_tracks:
            user_tracks[action_type].clear()


class Antinuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._locks: Dict[int, asyncio.Lock] = {}
        self.rate_tracker = InMemoryRateTracker()
        self._processed_entries: Set[int] = set()

    def _get_guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    async def _is_whitelisted(self, guild_id: int, user_id: int) -> bool:
        if user_id == OWNER_ID:
            return True
        if self.bot.user and user_id == self.bot.user.id:
            return True
        # Auto-whitelist the server owner
        guild = self.bot.get_guild(guild_id)
        if guild and guild.owner_id == user_id:
            return True
        entry = await get_whitelist_entry(guild_id, user_id)
        return bool(entry and entry.get("trust_level", 0) >= 2)

    async def _check_threshold(self, guild_id: int, user_id: int, action_type: str) -> bool:
        max_count, window = await get_antinuke_threshold(guild_id, action_type)
        self.rate_tracker.add_event(guild_id, user_id, action_type)
        count = self.rate_tracker.count_events(guild_id, user_id, action_type, window)
        return count > max_count

    async def _apply_punishment(
        self,
        guild: discord.Guild,
        member: discord.Member,
        punishment: str,
        reason: str,
    ) -> None:
        try:
            if punishment == "ban":
                await guild.ban(member, reason=reason, delete_message_days=0)
            elif punishment == "kick":
                await guild.kick(member, reason=reason)
            elif punishment == "strip":
                # Remove all roles that are lower than bot's highest role
                bot_member = guild.me
                roles_to_remove = [
                    role for role in member.roles 
                    if role < bot_member.top_role and role != guild.default_role and not role.managed
                ]
                await member.remove_roles(*roles_to_remove, reason=reason)
                if member.voice and member.voice.channel:
                    await member.edit(deafen=True, reason=reason)
            elif punishment == "timeout":
                until = datetime.utcnow() + timedelta(days=28)
                await member.timeout(until, reason=reason)
        except discord.Forbidden:
            try:
                owner = guild.get_member(guild.owner_id)
                if owner:
                    await owner.send(
                        f"⚠️ **{guild.name}**: I tried to punish **{member}** (`{member.id}`) "
                        f"for antinuke trigger (`{punishment}`) but I lack permissions."
                    )
            except Exception:
                pass
        except Exception:
            pass

    async def _notify_owner(self, guild: discord.Guild, embed: discord.Embed) -> None:
        try:
            owner = guild.get_member(guild.owner_id)
            if owner:
                await owner.send(embed=embed)
        except Exception:
            pass

    async def _log_to_channel(self, guild: discord.Guild, embed: discord.Embed) -> None:
        try:
            settings = await get_guild(guild.id)
            log_ch_id = settings.get("log_channel", 0)
            if not log_ch_id:
                return
            ch = guild.get_channel(log_ch_id)
            if not ch:
                return
            await ch.send(embed=embed)
        except Exception:
            pass

    async def _handle_violation(
        self,
        guild: discord.Guild,
        user_id: int,
        action_type: str,
        target_desc: str = "",
    ) -> None:
        async with self._get_guild_lock(guild.id):
            if await self._is_whitelisted(guild.id, user_id):
                return

            settings = await get_guild(guild.id)
            if not settings.get("antinuke_enabled", 1):
                return

            member = guild.get_member(user_id)
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    return

            punishment = settings.get("punishment", DEFAULT_PUNISHMENT)
            reason = f"[Repent Antinuke] {action_type} threshold exceeded"

            await self._apply_punishment(guild, member, punishment, reason)
            await add_punished_user(
                guild.id,
                user_id,
                reason,
                self.bot.user.id if self.bot.user else 0,
                punishment,
            )

            # Cleanup all webhooks created by the violator
            await self._delete_all_user_webhooks(guild, user_id)

            await log_action(
                guild.id,
                "antinuke_trigger",
                user_id,
                {
                    "action_type": action_type,
                    "punishment": punishment,
                    "target": target_desc,
                },
            )

            embed = antinuke_embed(
                action=action_type,
                target=target_desc or "Server",
                responsible=f"{member.mention} (`{member.id}`)",
                punishment=punishment,
                guild=guild,
            )

            await self._notify_owner(guild, embed)
            await self._log_to_channel(guild, embed)

            self.rate_tracker.clear_events(guild.id, user_id, action_type)

    async def _handle_instant_punishment(
        self,
        guild: discord.Guild,
        user_id: int,
        action_type: str,
        target_desc: str = "",
    ) -> None:
        """Instantly punish a user for critical security actions (no threshold checks)."""
        async with self._get_guild_lock(guild.id):
            if await self._is_whitelisted(guild.id, user_id):
                return

            settings = await get_guild(guild.id)
            if not settings.get("antinuke_enabled", 1):
                return

            member = guild.get_member(user_id)
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    return

            punishment = settings.get("punishment", DEFAULT_PUNISHMENT)
            reason = f"[Repent Antinuke] Instant Punishment: {target_desc}"

            await self._apply_punishment(guild, member, punishment, reason)
            await add_punished_user(
                guild.id,
                user_id,
                reason,
                self.bot.user.id if self.bot.user else 0,
                punishment,
            )

            # Cleanup all webhooks created by the violator
            await self._delete_all_user_webhooks(guild, user_id)

            await log_action(
                guild.id,
                "antinuke_trigger_instant",
                user_id,
                {
                    "action_type": action_type,
                    "punishment": punishment,
                    "target": target_desc,
                },
            )

            embed = antinuke_embed(
                action=action_type,
                target=target_desc or "Server",
                responsible=f"{member.mention} (`{member.id}`)",
                punishment=punishment,
                guild=guild,
            )
            embed.title = "🚨 Instant Security Punishment"
            embed.description = f"**Reason:** {target_desc}\n**Responsible User:** {member.mention} (`{member.id}`)\n**Punishment:** {punishment}"

            await self._notify_owner(guild, embed)
            await self._log_to_channel(guild, embed)

    async def _kick_bot_if_unauthorized(self, guild: discord.Guild, adder_id: int, bot_id: int) -> None:
        if await self._is_whitelisted(guild.id, adder_id):
            return

        bot_member = guild.get_member(bot_id)
        if not bot_member:
            try:
                bot_member = await guild.fetch_member(bot_id)
            except Exception:
                return

        if not bot_member or not getattr(bot_member, "bot", False):
            return

        try:
            await bot_member.kick(reason="[Repent Antinuke] Unauthorized bot add")
        except Exception:
            pass

    async def _delete_webhook_if_unauthorized(
        self,
        guild: discord.Guild,
        adder_id: int,
        webhook_id: int,
    ) -> None:
        """Scan all webhooks and delete newly created webhook if adder is not trusted."""
        if await self._is_whitelisted(guild.id, adder_id):
            return

        try:
            webhooks = await guild.webhooks()
            for w in webhooks:
                if getattr(w, "id", None) == webhook_id:
                    await w.delete(reason="[Repent Antinuke] Unauthorized webhook create")
                    print(f"[ANTINUKE] Deleted unauthorized webhook {w.name} (ID: {webhook_id})")
                    return
        except Exception as e:
            print(f"[ANTINUKE] Failed to delete unauthorized webhook: {e}")

    async def _delete_all_user_webhooks(self, guild: discord.Guild, user_id: int) -> None:
        """Scan and delete all webhooks created by the target user."""
        try:
            webhooks = await guild.webhooks()
            deleted_count = 0
            for w in webhooks:
                creator = getattr(w, "user", None) or getattr(w, "creator", None)
                if creator and creator.id == user_id:
                    await w.delete(reason=f"[Repent Antinuke] Webhook cleanup for punished user {user_id}")
                    deleted_count += 1
            if deleted_count > 0:
                print(f"[ANTINUKE] Deleted {deleted_count} webhooks created by user {user_id}")
        except Exception as e:
            print(f"[ANTINUKE] Failed to clean up user webhooks: {e}")

    async def _auto_restore_from_cache(self, guild: discord.Guild) -> None:
        """Best-effort restore channels + roles from cache."""
        try:
            cached_roles = await get_cached_roles(guild.id)
            cached_channels = await get_cached_channels(guild.id)

            existing_roles = {r.id for r in guild.roles}
            for cr in cached_roles:
                role_id = cr.get("role_id")
                if role_id in existing_roles:
                    continue
                if role_id == guild.default_role.id:
                    continue

                perms = cr.get("permissions", 0)
                await guild.create_role(
                    name=cr.get("name", "restored-role"),
                    permissions=discord.Permissions(perms),
                    color=discord.Color(cr.get("color", 0)),
                    hoist=bool(cr.get("hoist", 0)),
                    mentionable=bool(cr.get("mentionable", 0)),
                    reason="[Repent] Auto-restore after antinuke trigger",
                )

            existing_channels = {c.id for c in guild.channels}
            for cc in cached_channels:
                ch_id = cc.get("channel_id")
                if ch_id in existing_channels:
                    continue

                channel_type = cc.get("type", 0)
                category_id = cc.get("category_id", 0) or 0
                category = guild.get_channel(category_id) if category_id else None

                payload_name = cc.get("name", "restored")
                topic = cc.get("topic", "") or None
                nsfw = bool(cc.get("nsfw", 0))
                slowmode_delay = cc.get("slowmode", 0) or 0
                position = cc.get("position", 0)

                if channel_type == 0:
                    await guild.create_text_channel(
                        name=payload_name,
                        category=category,
                        position=position,
                        topic=topic,
                        nsfw=nsfw,
                        slowmode_delay=slowmode_delay,
                        reason="[Repent] Auto-restore after antinuke trigger",
                    )
                elif channel_type == 2:
                    await guild.create_voice_channel(
                        name=payload_name,
                        category=category,
                        position=position,
                        reason="[Repent] Auto-restore after antinuke trigger",
                    )
                elif channel_type == 4:
                    await guild.create_category(
                        name=payload_name,
                        position=position,
                        reason="[Repent] Auto-restore after antinuke trigger",
                    )
        except Exception:
            pass

    def _is_dangerous_role(self, role: discord.Role) -> bool:
        from config import DANGEROUS_PERMISSIONS
        for perm in DANGEROUS_PERMISSIONS:
            if getattr(role.permissions, perm, False):
                return True
        return False

    async def process_audit_entry(self, entry: discord.AuditLogEntry) -> None:
        if not entry.guild or not entry.user:
            return

        if entry.id in self._processed_entries:
            return
        self._processed_entries.add(entry.id)
        if len(self._processed_entries) > 1000:
            self._processed_entries.clear()

        guild = entry.guild
        attacker = entry.user
        action = entry.action

        if await self._is_whitelisted(guild.id, attacker.id):
            return

        action_type: str | None = None
        target_desc = ""
        extra_webhook_id: Optional[int] = None
        extra_bot_id: Optional[int] = None
        instant_punish = False
        instant_reason = ""

        if action == discord.AuditLogAction.bot_add:
            action_type = "bot_add"
            target = entry.target
            target_desc = f"Bot: {target.name} (`{target.id}`)" if target and hasattr(target, "name") else "Unknown bot"
            if target and hasattr(target, "id"):
                extra_bot_id = int(target.id)

        elif action == discord.AuditLogAction.webhook_create:
            action_type = "webhook_create"
            target = entry.target
            target_desc = f"Webhook: {target.name}" if target and hasattr(target, "name") else "Unknown webhook"
            if target and hasattr(target, "id"):
                extra_webhook_id = int(target.id)

        elif action == discord.AuditLogAction.webhook_delete:
            action_type = "webhook_delete"
            target = entry.target
            target_desc = f"Webhook: {target.name}" if target and hasattr(target, "name") else "Unknown webhook"
            if target and hasattr(target, "id"):
                extra_webhook_id = int(target.id)

        elif action == discord.AuditLogAction.role_update:
            # Check for permission escalation
            before_perms = getattr(entry.changes.before, "permissions", None)
            after_perms = getattr(entry.changes.after, "permissions", None)
            if before_perms is not None and after_perms is not None:
                from config import DANGEROUS_PERMISSIONS
                added_perms = []
                for perm_name, value in after_perms:
                    if value and not getattr(before_perms, perm_name, False):
                        added_perms.append(perm_name)
                dangerous_added = [p for p in added_perms if p in DANGEROUS_PERMISSIONS]
                if dangerous_added:
                    instant_punish = True
                    instant_reason = f"Permission escalation: granted dangerous permissions {', '.join(dangerous_added)} to role @{entry.target.name}"

            if not instant_punish:
                action_type = "role_update"
                target = entry.target
                target_desc = f"@{target.name}" if target and hasattr(target, "name") else "Role update"

        elif action == discord.AuditLogAction.member_role_update:
            # Check for permission escalation (giving someone a dangerous role)
            added_roles = getattr(entry.changes.after, "roles", [])
            for r in added_roles:
                if self._is_dangerous_role(r):
                    instant_punish = True
                    instant_reason = f"Permission escalation: assigned dangerous role @{r.name} to {entry.target.mention if hasattr(entry.target, 'mention') else entry.target}"
                    break

        elif action == discord.AuditLogAction.ban:
            action_type = "ban"
            target = entry.target
            target_desc = f"{target} (`{target.id}`)" if target else "Unknown"

        elif action == discord.AuditLogAction.unban:
            action_type = "unban"
            target = entry.target
            target_desc = f"{target} (`{target.id}`)" if target else "Unknown"

        elif action == discord.AuditLogAction.kick:
            action_type = "kick"
            target = entry.target
            target_desc = f"{target} (`{target.id}`)" if target else "Unknown"

        elif action == discord.AuditLogAction.channel_delete:
            action_type = "channel_delete"
            target = entry.target
            target_desc = f"#{target.name}" if target and hasattr(target, "name") else "Unknown channel"

        elif action == discord.AuditLogAction.channel_create:
            action_type = "channel_create"
            target = entry.target
            target_desc = f"#{target.name}" if target and hasattr(target, "name") else "Unknown channel"

        elif action == discord.AuditLogAction.role_delete:
            action_type = "role_delete"
            target = entry.target
            target_desc = f"@{target.name}" if target and hasattr(target, "name") else "Unknown role"

        elif action == discord.AuditLogAction.role_create:
            action_type = "role_create"
            target = entry.target
            target_desc = f"@{target.name}" if target and hasattr(target, "name") else "Unknown role"

        elif action == discord.AuditLogAction.guild_update:
            # Check vanity URL change
            before_vanity = getattr(entry.changes.before, "vanity_url_code", None)
            after_vanity = getattr(entry.changes.after, "vanity_url_code", None)
            if before_vanity != after_vanity:
                instant_punish = True
                instant_reason = f"Vanity URL modification: changed from '{before_vanity}' to '{after_vanity}'"
            else:
                action_type = "server_update"
                target_desc = "Server settings modified"

        elif action == discord.AuditLogAction.guild_owner_transfer:
            action_type = "owner_transfer"
            target = entry.target
            target_desc = f"Transfer to {target} (`{target.id}`)" if target else "Unknown"

        elif action == discord.AuditLogAction.emoji_delete:
            action_type = "emoji_delete"
            target = entry.target
            target_desc = f"Emoji: {target.name}" if target and hasattr(target, "name") else "Unknown emoji"

        elif action == discord.AuditLogAction.sticker_delete:
            action_type = "sticker_delete"
            target = entry.target
            target_desc = f"Sticker: {target.name}" if target and hasattr(target, "name") else "Unknown sticker"

        if instant_punish:
            await self._handle_instant_punishment(guild, attacker.id, "permission_escalation", instant_reason)
            return

        if not action_type:
            return

        if action_type == "owner_transfer":
            await self._handle_violation(guild, attacker.id, action_type, target_desc)
            return

        # Threshold check using in-memory tracker
        try:
            violated = await self._check_threshold(guild.id, attacker.id, action_type)
        except Exception:
            return

        # Delete webhook if unauthorized
        if action == discord.AuditLogAction.webhook_create and extra_webhook_id is not None:
            await self._delete_webhook_if_unauthorized(
                guild=guild,
                adder_id=attacker.id,
                webhook_id=extra_webhook_id,
            )

        # Cleanup all webhooks if threshold for webhook actions exceeded
        if violated and action_type in ("webhook_create", "webhook_delete"):
            await self._delete_all_user_webhooks(guild, attacker.id)

        # Kick unauthorized bot
        if not violated and action == discord.AuditLogAction.bot_add and extra_bot_id is not None:
            await self._kick_bot_if_unauthorized(guild, attacker.id, extra_bot_id)

        if not violated:
            return

        # Threshold exceeded => punish + auto-restore
        await self._handle_violation(guild, attacker.id, action_type, target_desc)
        await self._auto_restore_from_cache(guild)

        if action == discord.AuditLogAction.bot_add and extra_bot_id is not None:
            await self._kick_bot_if_unauthorized(guild, attacker.id, extra_bot_id)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        await self.process_audit_entry(entry)

    # ── Fast Path Listeners ──
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        await asyncio.sleep(0.3)
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            if entry.target and entry.target.id == user.id:
                await self.process_audit_entry(entry)
                break

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        await asyncio.sleep(0.3)
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
            if entry.target and entry.target.id == member.id:
                await self.process_audit_entry(entry)
                break

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        await asyncio.sleep(0.3)
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_delete):
            if entry.target and entry.target.id == channel.id:
                await self.process_audit_entry(entry)
                break

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        await asyncio.sleep(0.3)
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_create):
            if entry.target and entry.target.id == channel.id:
                await self.process_audit_entry(entry)
                break

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        await asyncio.sleep(0.3)
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_delete):
            if entry.target and entry.target.id == role.id:
                await self.process_audit_entry(entry)
                break

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        guild = role.guild
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        await asyncio.sleep(0.3)
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_create):
            if entry.target and entry.target.id == role.id:
                await self.process_audit_entry(entry)
                break

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]):
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        deleted = [e for e in before if e not in after]
        if deleted:
            await asyncio.sleep(0.3)
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.emoji_delete):
                await self.process_audit_entry(entry)
                break

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before: list[discord.GuildSticker], after: list[discord.GuildSticker]):
        settings = await get_guild(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        deleted = [s for s in before if s not in after]
        if deleted:
            await asyncio.sleep(0.3)
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.sticker_delete):
                await self.process_audit_entry(entry)
                break

    # ── Commands ──
    @discord.app_commands.command(name="restore", description="Restore deleted channels and roles from cache (Admin only)")
    async def restore(
        self,
        interaction: discord.Interaction,
    ):
        if not interaction.guild:
            return
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        await interaction.response.defer(thinking=True)
        try:
            await self._auto_restore_from_cache(interaction.guild)
        except Exception:
            pass

        await interaction.followup.send(
            embed=success_embed("Restore Complete", "Auto-restore from cache has been attempted."),
            ephemeral=False,
        )

    @discord.app_commands.command(name="punished", description="List punished users (Admin only)")
    async def punished(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        users = await get_punished_users(interaction.guild.id)
        if not users:
            return await interaction.response.send_message(
                embed=info_embed("Punished Users", "No punished users in this server."),
                ephemeral=False,
            )

        lines = []
        for u in users[:20]:
            member = interaction.guild.get_member(u["user_id"])
            name = member.mention if member else f"<@{u['user_id']}>"
            lines.append(f"{name} — `{u.get('punishment_type','')}` — {u.get('reason','')[:50]}")

        await interaction.response.send_message(
            embed=info_embed("Punished Users", "\n".join(lines)),
            ephemeral=False,
        )

    @discord.app_commands.command(name="pardon", description="Remove a user from the punished list (Admin only)")
    @discord.app_commands.describe(user="User to pardon")
    async def pardon(self, interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            return
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        await remove_punished_user(interaction.guild.id, user.id)
        await interaction.response.send_message(
            embed=success_embed("Pardoned", f"{user.mention} has been removed from the punished list."),
            ephemeral=False,
        )

    @discord.app_commands.command(name="nuke-webhooks", description="Delete ALL webhooks across all channels in the guild (Admin only)")
    async def nuke_webhooks(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        await interaction.response.defer(thinking=True)
        try:
            webhooks = await interaction.guild.webhooks()
            deleted = 0
            for w in webhooks:
                try:
                    await w.delete(reason=f"[Repent Antinuke] Webhooks nuked by {interaction.user}")
                    deleted += 1
                except Exception:
                    pass
            await interaction.followup.send(
                embed=success_embed("Webhooks Nuked", f"Successfully deleted {deleted} webhook(s)."),
                ephemeral=False,
            )
        except Exception as e:
            await interaction.followup.send(
                embed=error_embed(f"Failed to delete webhooks: {e}"),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Antinuke(bot))
