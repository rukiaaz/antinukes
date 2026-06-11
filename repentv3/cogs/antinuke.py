"""Repent - Antinuke System

Hardened Antinuke system protecting against nuke/bulk moderation actions, Webhook threats, and Permission Escalations.

Key behaviors implemented:
- Instant punish (kick/ban/strip/timeout) on first detection for critical delete actions.
- Targeted auto-restore from cache ONLY for the specific deleted channel/role IDs.
- Webhook auto-delete when unwhitelisted user creates them (immediate delete + instant punish).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Set
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
    is_bot_whitelisted,
    user_has_whitelisted_role,
    is_user_whitelisted_optimized,
)
from utils.embeds import antinuke_embed, error_embed, info_embed, success_embed
from utils.cache import snapshot_guild
from utils.logger import get_logger


class InMemoryRateTracker:
    """Fast, in-memory sliding window rate tracker."""

    def __init__(self):
        # guild_id -> user_id -> action_type -> deque[datetime]
        self._tracks: Dict[int, Dict[int, Dict[str, deque]]] = {}

    def add_event(self, guild_id: int, user_id: int, action_type: str) -> None:
        self._tracks.setdefault(guild_id, {}).setdefault(user_id, {}).setdefault(action_type, deque()).append(
            datetime.now(timezone.utc)
        )

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

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
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
        events = user_tracks.get(action_type)
        if events is not None:
            events.clear()


class Antinuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._locks: Dict[int, asyncio.Lock] = {}
        self.rate_tracker = InMemoryRateTracker()
        # Store processed entries with timestamps for memory cleanup: {entry_id: datetime}
        self._processed_entries: Dict[int, datetime] = {}
        self._cleanup_task = None
        self.logger = get_logger()
        
        # Whitelist result cache: {(guild_id, user_id): (result, timestamp)}
        self._whitelist_cache: Dict[Tuple[int, int], Tuple[bool, datetime]] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Discord object cache: {cache_key: (object, timestamp)}
        self._discord_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._discord_cache_ttl = 60  # 1 minute for Discord objects
        
        # Safe admins JSON cache: {guild_id: (parsed_list, settings_timestamp)}
        self._safe_admins_cache: Dict[int, Tuple[List[int], str, datetime]] = {}
        self._safe_admins_cache_ttl = 180  # 3 minutes for safe admins

    def _get_guild_lock(self, guild_id: int) -> asyncio.Lock:
        self._locks.setdefault(guild_id, asyncio.Lock())
        return self._locks[guild_id]

    async def cog_load(self):
        """Start the cleanup task when cog is loaded."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def cog_unload(self):
        """Stop the cleanup task when cog is unloaded."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def _get_cached_whitelist_status(self, guild_id: int, user_id: int) -> Optional[bool]:
        """Get cached whitelist status if available and not expired."""
        cache_key = (guild_id, user_id)
        if cache_key in self._whitelist_cache:
            result, timestamp = self._whitelist_cache[cache_key]
            if datetime.now(timezone.utc) - timestamp < timedelta(seconds=self._cache_ttl):
                return result
            else:
                # Expired, remove from cache
                del self._whitelist_cache[cache_key]
        return None

    def _set_cached_whitelist_status(self, guild_id: int, user_id: int, result: bool) -> None:
        """Cache whitelist status with current timestamp."""
        cache_key = (guild_id, user_id)
        self._whitelist_cache[cache_key] = (result, datetime.now(timezone.utc))

    def _get_cached_discord_object(self, cache_key: str) -> Optional[Any]:
        """Get cached Discord object if available and not expired."""
        if cache_key in self._discord_cache:
            obj, timestamp = self._discord_cache[cache_key]
            if datetime.now(timezone.utc) - timestamp < timedelta(seconds=self._discord_cache_ttl):
                return obj
            else:
                # Expired, remove from cache
                del self._discord_cache[cache_key]
        return None

    def _set_cached_discord_object(self, cache_key: str, obj: Any) -> None:
        """Cache Discord object with current timestamp."""
        self._discord_cache[cache_key] = (obj, datetime.now(timezone.utc))

    def _get_cached_safe_admins(self, guild_id: int, current_settings_json: str) -> Optional[List[int]]:
        """Get cached safe admins list if settings haven't changed."""
        if guild_id in self._safe_admins_cache:
            cached_list, cached_json, timestamp = self._safe_admins_cache[guild_id]
            if cached_json == current_settings_json and datetime.now(timezone.utc) - timestamp < timedelta(seconds=self._safe_admins_cache_ttl):
                return cached_list
            else:
                # Settings changed or expired, remove from cache
                del self._safe_admins_cache[guild_id]
        return None

    def _set_cached_safe_admins(self, guild_id: int, safe_admins_list: List[int], settings_json: str) -> None:
        """Cache safe admins list with current settings and timestamp."""
        self._safe_admins_cache[guild_id] = (safe_admins_list, settings_json, datetime.now(timezone.utc))

    async def _cleanup_loop(self):
        """Periodically clean up old processed entries to prevent memory leaks."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)  # Remove entries older than 30 minutes
                old_entries = [eid for eid, timestamp in self._processed_entries.items() if timestamp < cutoff]
                for eid in old_entries:
                    del self._processed_entries[eid]
                if old_entries:
                    self.logger.debug(f"Cleaned up {len(old_entries)} old processed entries")
                
                # Clean up whitelist cache
                cache_cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._cache_ttl)
                old_cache_keys = [key for key, (_, timestamp) in self._whitelist_cache.items() if timestamp < cache_cutoff]
                for key in old_cache_keys:
                    del self._whitelist_cache[key]
                if old_cache_keys:
                    self.logger.debug(f"Cleaned up {len(old_cache_keys)} old whitelist cache entries")
                
                # Clean up Discord object cache
                discord_cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._discord_cache_ttl)
                old_discord_keys = [key for key, (_, timestamp) in self._discord_cache.items() if timestamp < discord_cutoff]
                for key in old_discord_keys:
                    del self._discord_cache[key]
                if old_discord_keys:
                    self.logger.debug(f"Cleaned up {len(old_discord_keys)} old Discord cache entries")
                
                # Clean up safe admins cache
                safe_admins_cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._safe_admins_cache_ttl)
                old_safe_admins_keys = [key for key, (_, _, timestamp) in self._safe_admins_cache.items() if timestamp < safe_admins_cutoff]
                for key in old_safe_admins_keys:
                    del self._safe_admins_cache[key]
                if old_safe_admins_keys:
                    self.logger.debug(f"Cleaned up {len(old_safe_admins_keys)} old safe admins cache entries")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in antinuke cleanup loop", exc_info=True)

    async def _is_whitelisted(self, guild_id: int, user_id: int) -> bool:
        # Check cache first for fast lookup
        cached_result = self._get_cached_whitelist_status(guild_id, user_id)
        if cached_result is not None:
            return cached_result

        if user_id == OWNER_ID:
            self._set_cached_whitelist_status(guild_id, user_id, True)
            return True
        if self.bot.user and user_id == self.bot.user.id:
            self._set_cached_whitelist_status(guild_id, user_id, True)
            return True

        # Use Discord object cache for guild lookups
        guild_cache_key = f"guild:{guild_id}"
        guild = self._get_cached_discord_object(guild_cache_key)
        if not guild:
            guild = self.bot.get_guild(guild_id)
            if guild:
                self._set_cached_discord_object(guild_cache_key, guild)
        
        if guild and guild.owner_id == user_id:
            self._set_cached_whitelist_status(guild_id, user_id, True)
            return True

        # Check safe admin list with cached JSON parsing
        settings = await get_guild(guild_id)
        safe_admins_json = settings.get("antinuke_safe_admins", "[]")
        
        # Try to use cached safe admins list
        safe_admins = self._get_cached_safe_admins(guild_id, safe_admins_json)
        if safe_admins is None:
            # Parse and cache if not available
            try:
                safe_admins = json.loads(safe_admins_json)
                self._set_cached_safe_admins(guild_id, safe_admins, safe_admins_json)
            except json.JSONDecodeError:
                safe_admins = []
        
        if user_id in safe_admins:
            self._set_cached_whitelist_status(guild_id, user_id, True)
            return True

        # Check if user is a bot and if it's whitelisted using optimized function
        member_cache_key = f"member:{guild_id}:{user_id}"
        member = self._get_cached_discord_object(member_cache_key)
        if not member and guild:
            member = guild.get_member(user_id)
            if member:
                self._set_cached_discord_object(member_cache_key, member)
        
        is_bot = member and member.bot
        if is_bot:
            if await is_user_whitelisted_optimized(guild_id, user_id, is_bot=True):
                self._set_cached_whitelist_status(guild_id, user_id, True)
                return True

        # Check role-based whitelist (staff protection) using optimized function
        if member and member.roles:
            user_role_ids = {role.id for role in member.roles}
            if await user_has_whitelisted_role(guild_id, user_id, user_role_ids):
                self._set_cached_whitelist_status(guild_id, user_id, True)
                return True

        # Use optimized database function for user whitelist check
        if await is_user_whitelisted_optimized(guild_id, user_id, is_bot=False):
            self._set_cached_whitelist_status(guild_id, user_id, True)
            return True

        # Cache the negative result
        self._set_cached_whitelist_status(guild_id, user_id, False)
        return False

    async def _check_threshold(self, guild_id: int, user_id: int, action_type: str) -> bool:
        max_count, window = await get_antinuke_threshold(guild_id, action_type)
        self.rate_tracker.add_event(guild_id, user_id, action_type)
        count = self.rate_tracker.count_events(guild_id, user_id, action_type, window)
        return count > max_count

    async def _apply_punishment(self, guild: discord.Guild, member: discord.Member, punishment: str, reason: str) -> None:
        try:
            # Final security check: Verify whitelist status one more time
            if await self._is_whitelisted(guild.id, member.id):
                self.logger.warning(f"Aborting punishment for {member.id} - user is whitelisted")
                return
            
            # Check if bot can punish this user based on role hierarchy
            bot_member = guild.me
            
            # Cannot punish server owner
            if member.id == guild.owner_id:
                self.logger.warning(f"Cannot punish server owner {member.id}")
                await self._notify_owner(guild, self._create_permission_denied_embed(guild, member, punishment, "User is server owner"))
                return
            
            # Check role hierarchy - can only punish users with lower roles
            if member.roles:
                # Get user's highest role
                user_highest_role = max(member.roles, key=lambda r: r.position)
                
                # If user's highest role is >= bot's highest role, cannot punish
                if user_highest_role >= bot_member.top_role:
                    self.logger.warning(f"Cannot punish {member.id} - role hierarchy: user role {user_highest_role.name} >= bot role {bot_member.top_role.name}")
                    await self._notify_owner(guild, self._create_permission_denied_embed(guild, member, punishment, f"User has higher/equal role ({user_highest_role.name})"))
                    
                    # Try alternative punishment: strip permissions instead
                    if punishment in ["ban", "kick", "timeout"]:
                        self.logger.info(f"Attempting alternative punishment (strip) for {member.id}")
                        await self._apply_punishment(guild, member, "strip", reason + " (original punishment: " + punishment + " failed due to role hierarchy)")
                    return
            
            # If user has no roles or has lower roles, proceed with punishment
            if punishment == "ban":
                await guild.ban(member, reason=reason, delete_message_days=0)
            elif punishment == "kick":
                await guild.kick(member, reason=reason)
            elif punishment == "strip":
                bot_member = guild.me
                roles_to_remove = [
                    role
                    for role in member.roles
                    if role < bot_member.top_role and role != guild.default_role and not role.managed
                ]
                await member.remove_roles(*roles_to_remove, reason=reason)
                if member.voice and member.voice.channel:
                    await member.edit(deafen=True, reason=reason)
            elif punishment == "timeout":
                until = datetime.now(timezone.utc) + timedelta(days=28)
                await member.timeout(until, reason=reason)
                
        except discord.Forbidden as e:
            # Explicit permission error
            self.logger.error(f"Forbidden to punish {member.id}: {e}")
            try:
                owner = guild.get_member(guild.owner_id)
                if owner:
                    await owner.send(
                        f"⚠️ **{guild.name}**: I tried to punish **{member}** (`{member.id}`) for {punishment} but I lack permissions (Forbidden). Error: {e}"
                    )
            except Exception:
                pass
        except Exception as e:
            # Other errors
            self.logger.error(f"Failed to punish {member.id}: {e}", exc_info=True)
            try:
                owner = guild.get_member(guild.owner_id)
                if owner:
                    await owner.send(
                        f"⚠️ **{guild.name}**: I tried to punish **{member}** (`{member.id}`) for {punishment} but encountered an error: {e}"
                    )
            except Exception:
                pass

    def _create_permission_denied_embed(self, guild: discord.Guild, member: discord.Member, punishment: str, reason: str) -> discord.Embed:
        """Create an embed for permission denied situations."""
        embed = discord.Embed(
            title="🚨 Permission Denied - Cannot Punish",
            description=f"**Target:** {member.mention} (`{member.id}`)\n"
                       f"**Attempted Punishment:** {punishment}\n"
                       f"**Reason:** {reason}\n"
                       f"**Bot Role:** {guild.me.top_role.mention} (Position: {guild.me.top_role.position})\n"
                       f"**User Top Role:** {max(member.roles, key=lambda r: r.position).mention if member.roles else '@everyone'}",
            color=0xFF4444
        )
        embed.set_footer(text=f"Guild: {guild.name} | Bot: {guild.me}")
        embed.timestamp = datetime.now(timezone.utc)
        return embed

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

    async def _delete_webhook_if_unauthorized(self, guild: discord.Guild, adder_id: int, webhook_id: int) -> None:
        if await self._is_whitelisted(guild.id, adder_id):
            return
        try:
            webhooks = await guild.webhooks()
            for w in webhooks:
                if getattr(w, "id", None) == webhook_id:
                    await w.delete(reason="[Repent Antinuke] Unauthorized webhook create")
                    return
        except Exception:
            pass

    async def _delete_all_user_webhooks(self, guild: discord.Guild, user_id: int) -> None:
        try:
            webhooks = await guild.webhooks()
            deleted_count = 0
            for w in webhooks:
                creator = getattr(w, "user", None) or getattr(w, "creator", None)
                if creator and creator.id == user_id:
                    await w.delete(reason=f"[Repent Antinuke] Webhook cleanup for punished user {user_id}")
                    deleted_count += 1
            if deleted_count:
                self.logger.security("WEBHOOK_CLEANUP", f"Deleted {deleted_count} webhooks created by user {user_id}", user_id=user_id)
        except Exception:
            pass

    async def _handle_violation(self, guild: discord.Guild, user_id: int, action_type: str, target_desc: str = "") -> None:
        # Security: Check whitelist BEFORE acquiring lock to prevent TOCTOU race condition
        if await self._is_whitelisted(guild.id, user_id):
            return
        
        async with self._get_guild_lock(guild.id):
            # Double-check whitelist inside lock for absolute safety
            if await self._is_whitelisted(guild.id, user_id):
                return

            settings = await get_guild(guild.id)
            if not settings.get("antinuke_enabled", 1):
                return

            member = guild.get_member(user_id) or None
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    return

            punishment = settings.get("punishment", DEFAULT_PUNISHMENT)
            reason = f"[Repent Antinuke] {action_type} threshold exceeded"

            await self._apply_punishment(guild, member, punishment, reason)
            await add_punished_user(guild.id, user_id, reason, self.bot.user.id if self.bot.user else 0, punishment)

            await self._delete_all_user_webhooks(guild, user_id)

            await log_action(
                guild.id,
                "antinuke_trigger",
                user_id,
                {"action_type": action_type, "punishment": punishment, "target": target_desc},
            )
            
            # Log to security system
            self.logger.antinuke_trigger(action_type, guild.id, user_id, punishment)

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

    async def _handle_instant_punishment(self, guild: discord.Guild, user_id: int, action_type: str, target_desc: str = "") -> None:
        async with self._get_guild_lock(guild.id):
            if await self._is_whitelisted(guild.id, user_id):
                return

            settings = await get_guild(guild.id)
            if not settings.get("antinuke_enabled", 1):
                return

            member = guild.get_member(user_id) or None
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    return

            punishment = settings.get("punishment", DEFAULT_PUNISHMENT)
            reason = f"[Repent Antinuke] Instant Punishment: {target_desc}"

            await self._apply_punishment(guild, member, punishment, reason)
            await add_punished_user(guild.id, user_id, reason, self.bot.user.id if self.bot.user else 0, punishment)

            await self._delete_all_user_webhooks(guild, user_id)

            await log_action(
                guild.id,
                "antinuke_trigger_instant",
                user_id,
                {"action_type": action_type, "punishment": punishment, "target": target_desc},
            )

            embed = antinuke_embed(
                action=action_type,
                target=target_desc or "Server",
                responsible=f"{member.mention} (`{member.id}`)",
                punishment=punishment,
                guild=guild,
            )
            embed.title = "🚨 Instant Security Punishment"
            embed.description = (
                f"**Reason:** {target_desc}"
                f"\n**Responsible User:** {member.mention} (`{member.id}`)"
                f"\n**Punishment:** {punishment}"
            )

            await self._notify_owner(guild, embed)
            await self._log_to_channel(guild, embed)

    def _is_dangerous_role(self, role: discord.Role) -> bool:
        from config import DANGEROUS_PERMISSIONS

        for perm in DANGEROUS_PERMISSIONS:
            if getattr(role.permissions, perm, False):
                return True
        return False

    def _is_administrator_role(self, role: discord.Role) -> bool:
        """Check if role has administrator permission."""
        return role.permissions.administrator

    def _can_manage_guild(self, role: discord.Role) -> bool:
        """Check if role can manage guild settings."""
        return role.permissions.manage_guild

    def _detect_suspicious_pattern(self, attacker: discord.Member, action: discord.AuditLogAction, entry: discord.AuditLogEntry) -> bool:
        """Detect suspicious activity patterns that may indicate bypass attempts."""
        # Check for rapid successive actions
        recent_count = self.rate_tracker.count_events(
            entry.guild.id, attacker.id, "suspicious_activity", 30
        )
        
        # If user has multiple suspicious actions in 30 seconds, flag as suspicious
        if recent_count >= 3:
            return True
        
        # Check for高危 actions in short time
        high_risk_actions = [
            discord.AuditLogAction.role_update,
            discord.AuditLogAction.channel_delete,
            discord.AuditLogAction.role_delete,
            discord.AuditLogAction.guild_update,
        ]
        
        if action in high_risk_actions:
            # Track this as a potentially suspicious action
            self.rate_tracker.add_event(entry.guild.id, attacker.id, "suspicious_activity")
        
        return False

    async def _handle_suspicious_activity(self, guild: discord.Guild, attacker: discord.Member, action: discord.AuditLogAction):
        """Handle detected suspicious activity with stricter punishment."""
        # Log the suspicious activity
        await log_action(
            guild.id,
            "suspicious_activity",
            attacker.id,
            {"action": str(action), "punishment": "ban"}
        )
        
        # Apply immediate ban for suspicious patterns
        try:
            await guild.ban(
                attacker,
                reason="[Repent] Suspicious activity pattern detected - auto-ban for security",
                delete_message_days=0,
            )
            self.logger.security(
                "SUSPICIOUS_ACTIVITY_BAN",
                f"Banned user {attacker.id} for suspicious activity pattern",
                guild_id=guild.id,
                user_id=attacker.id
            )
        except Exception as e:
            self.logger.error(f"Failed to ban suspicious user {attacker.id}: {e}", exc_info=True)

    def _check_permission_escalation(self, before: discord.Role, after: discord.Role) -> bool:
        """Check if a role update represents permission escalation."""
        from config import DANGEROUS_PERMISSIONS
        
        before_dangerous = [perm for perm in DANGEROUS_PERMISSIONS if getattr(before.permissions, perm, False)]
        after_dangerous = [perm for perm in DANGEROUS_PERMISSIONS if getattr(after.permissions, perm, False)]
        
        # Check if dangerous permissions were added
        new_dangerous = set(after_dangerous) - set(before_dangerous)
        if new_dangerous:
            return True, list(new_dangerous)
        
        # Check if administrator was granted (most dangerous)
        if not before.permissions.administrator and after.permissions.administrator:
            return True, ["administrator"]
        
        # Check if manage_guild was granted
        if not before.permissions.manage_guild and after.permissions.manage_guild:
            return True, ["manage_guild"]
        
        return False, []

    async def _handle_permission_escalation(self, guild: discord.Guild, user_id: int, role: discord.Role, added_permissions: List[str]):
        """Handle permission escalation detection."""
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
        reason = f"[Repent Antinuke] Permission Escalation: Added dangerous permissions to {role.name}: {', '.join(added_permissions)}"

        await self._apply_punishment(guild, member, punishment, reason)
        await add_punished_user(guild.id, user_id, reason, self.bot.user.id if self.bot.user else 0, punishment)

        # Log the incident
        await log_action(
            guild.id,
            "permission_escalation",
            user_id,
            {"role": role.name, "permissions": added_permissions, "punishment": punishment},
        )

        embed = discord.Embed(
            title="🚨 Permission Escalation Detected",
            description=f"**User:** {member.mention} ({member.id})\n"
                       f"**Role:** {role.mention}\n"
                       f"**Added Permissions:** {', '.join(added_permissions)}\n"
                       f"**Punishment:** {punishment}",
            color=0xFF4444
        )

        await self._notify_owner(guild, embed)
        await self._log_to_channel(guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Detect permission escalation in role updates."""
        guild = after.guild
        settings = await get_guild(guild.id)
        
        # Check if permission escalation detection is enabled
        sensitivity = settings.get("antinuke_sensitivity_level", 5)
        if sensitivity < 5:  # Only check if sensitivity is medium or higher
            return
        
        # Get the audit log entry to find who made the change
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_update):
            if entry.target.id == after.id:
                is_escalation, added_perms = self._check_permission_escalation(before, after)
                if is_escalation:
                    await self._handle_permission_escalation(guild, entry.user.id, after, added_perms)
                break

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Enhanced member join with instant restore if configured."""
        # This complements the existing antinuke join check
        from database import is_hardbanned
        if await is_hardbanned(member.guild.id, member.id):
            try:
                await member.guild.ban(
                    member,
                    reason="[Repent] Hardban — auto reban on rejoin",
                    delete_message_days=0,
                )
                self.logger.security("HARDBAN_REBAN", f"Re-banned user {member.id}", guild_id=member.guild.id, user_id=member.id)
            except Exception as e:
                self.logger.error(f"Failed to reban hardbanned user {member.id}", exc_info=True)

    async def _auto_restore_channel(self, guild: discord.Guild, channel_id: int) -> bool:
        """Restore a single channel from cache with full settings including overwrites."""
        try:
            cached_channels = await get_cached_channels(guild.id)
            channel_data = next((c for c in cached_channels if int(c.get("channel_id")) == channel_id), None)
            
            if not channel_data:
                self.logger.warning(f"Channel {channel_id} not found in cache")
                return False
            
            # Check if channel already exists (might have been restored manually)
            if guild.get_channel(channel_id):
                return False
            
            channel_type = channel_data.get("type", 0)
            category_id = channel_data.get("category_id", 0) or 0
            category = guild.get_channel(category_id) if category_id else None
            
            # Parse overwrites from JSON
            overwrites = self._parse_overwrites(guild, channel_data.get("json_overwrites", "{}"))
            
            kwargs = {
                "name": channel_data.get("name", "restored"),
                "category": category,
                "position": channel_data.get("position", 0),
                "overwrites": overwrites,
                "reason": "[Repent] Auto-restore deleted channel",
            }
            
            # Type-specific settings
            if channel_type == 0:  # Text channel
                kwargs.update({
                    "topic": channel_data.get("topic", "") or None,
                    "nsfw": bool(channel_data.get("nsfw", 0)),
                    "slowmode_delay": channel_data.get("slowmode", 0) or 0,
                })
                await guild.create_text_channel(**kwargs)
            elif channel_type == 2:  # Voice channel
                await guild.create_voice_channel(**kwargs)
            elif channel_type == 4:  # Category
                kwargs.pop("category", None)  # Categories don't have categories
                await guild.create_category(**kwargs)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to auto-restore channel {channel_id}: {e}", exc_info=True)
            return False
    
    def _parse_overwrites(self, guild: discord.Guild, overwrites_json: str) -> dict:
        """Parse permission overwrites from JSON and convert to Discord objects."""
        try:
            overwrites_dict = json.loads(overwrites_json)
            overwrites = {}
            
            for target_id_str, o_data in overwrites_dict.items():
                target_id = int(target_id_str)
                target = None
                
                if o_data.get("type") == "role":
                    target = guild.get_role(target_id)
                else:  # member
                    target = guild.get_member(target_id)
                    if not target:
                        continue  # Skip if member not found
                
                if target:
                    overwrites[target] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(o_data.get("allow", 0)),
                        discord.Permissions(o_data.get("deny", 0)),
                    )
            
            return overwrites
        except Exception:
            return {}
    
    async def _auto_restore_from_cache(
        self,
        guild: discord.Guild,
        only_channel_ids: Optional[Set[int]] = None,
        only_role_ids: Optional[Set[int]] = None,
    ) -> None:
        """Best-effort restore channels + roles from cache.

        If only_channel_ids / only_role_ids are provided, restore ONLY those missing.
        """
        try:
            # Restore roles if specified
            if only_role_ids:
                await self._restore_roles(guild, only_role_ids)
            
            # Restore channels if specified
            if only_channel_ids:
                for channel_id in only_channel_ids:
                    await self._auto_restore_channel(guild, channel_id)
        except Exception as e:
            self.logger.error(f"Auto-restore from cache failed: {e}", exc_info=True)
    
    async def _restore_roles(self, guild: discord.Guild, role_ids: Set[int]) -> None:
        """Restore specific roles from cache."""
        try:
            cached_roles = await get_cached_roles(guild.id)
            existing_roles = {r.id for r in guild.roles}
            
            for cr in cached_roles:
                role_id = cr.get("role_id")
                if role_id not in role_ids or role_id in existing_roles or role_id == guild.default_role.id:
                    continue
                
                await guild.create_role(
                    name=cr.get("name", "restored-role"),
                    permissions=discord.Permissions(cr.get("permissions", 0)),
                    color=discord.Color(cr.get("color", 0)),
                    hoist=bool(cr.get("hoist", 0)),
                    mentionable=bool(cr.get("mentionable", 0)),
                    position=cr.get("position", 0),
                    reason="[Repent] Auto-restore after antinuke trigger",
                )
        except Exception as e:
            self.logger.error(f"Failed to restore roles: {e}", exc_info=True)
    
    async def _auto_restore_role(self, guild: discord.Guild, role_id: int) -> bool:
        """Restore a single role from cache."""
        try:
            return await self._restore_roles(guild, {role_id}) is not None
        except Exception as e:
            self.logger.error(f"Failed to auto-restore role {role_id}: {e}", exc_info=True)
            return False
    
    async def _process_audit_log_event(self, guild: discord.Guild, target_id: int, action: discord.AuditLogAction) -> Optional[discord.AuditLogEntry]:
        """Helper method to process audit log events with error handling."""
        try:
            settings = await get_guild(guild.id)
            if not settings.get("antinuke_enabled", 1):
                return None
                
            await asyncio.sleep(0.3)
            async for entry in guild.audit_logs(limit=3, action=action):
                if entry.target and entry.target.id == target_id:
                    await self.process_audit_entry(entry)
                    return entry
        except Exception as e:
            self.logger.error(f"Failed to process audit log event: {e}", exc_info=True)
        return None

    async def process_audit_entry(self, entry: discord.AuditLogEntry) -> None:
        if not entry.guild or not entry.user:
            return

        if entry.id in self._processed_entries:
            return
        # Store entry with timestamp for cleanup
        self._processed_entries[entry.id] = datetime.now(timezone.utc)

        guild = entry.guild
        attacker = entry.user
        action = entry.action

        if await self._is_whitelisted(guild.id, attacker.id):
            return

        # Additional security: Check for suspicious patterns
        if self._detect_suspicious_pattern(attacker, action, entry):
            self.logger.security(
                "SUSPICIOUS_PATTERN",
                f"Suspicious activity pattern detected from user {attacker.id}",
                guild_id=guild.id,
                user_id=attacker.id
            )
            # Apply stricter punishment for suspicious patterns
            await self._handle_suspicious_activity(guild, attacker, action)

        action_type: str | None = None
        target_desc = ""
        extra_webhook_id: Optional[int] = None
        extra_bot_id: Optional[int] = None

        restore_channel_ids: Optional[Set[int]] = None
        restore_role_ids: Optional[Set[int]] = None

        instant_punish = False
        instant_reason = ""

        if action == discord.AuditLogAction.bot_add:
            action_type = "bot_add"
            if entry.target and hasattr(entry.target, "id"):
                extra_bot_id = int(entry.target.id)
            target_desc = f"Bot: {getattr(entry.target, 'name', 'Unknown')} (`{getattr(entry.target, 'id', '0')}`)"

        elif action == discord.AuditLogAction.webhook_create:
            action_type = "webhook_create"
            if entry.target and hasattr(entry.target, "id"):
                extra_webhook_id = int(entry.target.id)
            target_desc = f"Webhook: {getattr(entry.target, 'name', 'Unknown')}"

        elif action == discord.AuditLogAction.webhook_delete:
            action_type = "webhook_delete"

        elif action == discord.AuditLogAction.role_update:
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
                    instant_reason = (
                        "Permission escalation: granted dangerous permissions "
                        f"{', '.join(dangerous_added)}"
                    )

            if not instant_punish:
                action_type = "role_update"
                target_desc = f"@{getattr(entry.target, 'name', 'Role')}"

        elif action == discord.AuditLogAction.member_role_update:
            added_roles = getattr(entry.changes.after, "roles", [])
            for r in added_roles:
                if self._is_dangerous_role(r):
                    instant_punish = True
                    instant_reason = (
                        f"Permission escalation: assigned dangerous role @{r.name}"
                    )
                    break

        elif action == discord.AuditLogAction.ban:
            action_type = "ban"

        elif action == discord.AuditLogAction.unban:
            action_type = "unban"

        elif action == discord.AuditLogAction.kick:
            action_type = "kick"

        elif action == discord.AuditLogAction.channel_delete:
            action_type = "channel_delete"
            if entry.target and hasattr(entry.target, "id"):
                restore_channel_ids = {int(entry.target.id)}
            instant_punish = True
            instant_reason = "Unauthorized channel delete"

        elif action == discord.AuditLogAction.channel_create:
            action_type = "channel_create"

        elif action == discord.AuditLogAction.role_delete:
            action_type = "role_delete"
            if entry.target and hasattr(entry.target, "id"):
                restore_role_ids = {int(entry.target.id)}
            instant_punish = True
            instant_reason = "Unauthorized role delete"

        elif action == discord.AuditLogAction.role_create:
            action_type = "role_create"

        elif action == discord.AuditLogAction.guild_update:
            before_vanity = getattr(entry.changes.before, "vanity_url_code", None)
            after_vanity = getattr(entry.changes.after, "vanity_url_code", None)
            if before_vanity != after_vanity:
                instant_punish = True
                instant_reason = (
                    f"Vanity URL modification: changed from '{before_vanity}' to '{after_vanity}'"
                )
            else:
                action_type = "server_update"

        elif action == discord.AuditLogAction.guild_owner_transfer:
            action_type = "owner_transfer"

        elif action == discord.AuditLogAction.emoji_delete:
            action_type = "emoji_delete"

        elif action == discord.AuditLogAction.sticker_delete:
            action_type = "sticker_delete"

        if instant_punish:
            await self._handle_instant_punishment(guild, attacker.id, action_type or "permission_escalation", instant_reason)
            # Targeted restore for deletes
            if action in (discord.AuditLogAction.channel_delete, discord.AuditLogAction.role_delete):
                await self._auto_restore_from_cache(
                    guild,
                    only_channel_ids=restore_channel_ids,
                    only_role_ids=restore_role_ids,
                )
            return

        if not action_type:
            return

        # Webhook auto-delete for unwhitelisted creators
        if action == discord.AuditLogAction.webhook_create and extra_webhook_id is not None:
            await self._delete_webhook_if_unauthorized(guild, attacker.id, extra_webhook_id)
            await self._handle_instant_punishment(
                guild,
                attacker.id,
                "webhook_create",
                "Unauthorized webhook create",
            )
            return

        # Threshold-based flow
        try:
            violated = await self._check_threshold(guild.id, attacker.id, action_type)
        except Exception:
            return

        if violated and action_type in ("webhook_create", "webhook_delete"):
            await self._delete_all_user_webhooks(guild, attacker.id)

        if action == discord.AuditLogAction.bot_add and extra_bot_id is not None and not violated:
            await self._kick_bot_if_unauthorized(guild, attacker.id, extra_bot_id)

        if not violated:
            return

        await self._handle_violation(guild, attacker.id, action_type, target_desc)

        # Targeted restore if violation is deletes (rare because we instant punish above)
        if action in (discord.AuditLogAction.channel_delete, discord.AuditLogAction.role_delete):
            await self._auto_restore_from_cache(
                guild,
                only_channel_ids=restore_channel_ids,
                only_role_ids=restore_role_ids,
            )

        if action == discord.AuditLogAction.bot_add and extra_bot_id is not None:
            await self._kick_bot_if_unauthorized(guild, attacker.id, extra_bot_id)

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

    # Primary detection source: audit log only.
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        await self.process_audit_entry(entry)

    # Fast-path listeners removed to avoid duplicate audit processing.
    # (They were causing unstable behavior and duplicate incidents.)


    # ── Commands ──
    @discord.app_commands.command(name="antinuke_restore", description="Restore deleted channels and roles from antinuke cache (Admin only)")
    async def restore(self, interaction: discord.Interaction):
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
            return await interaction.response.send_message(embed=info_embed("Punished Users", "No punished users in this server."), ephemeral=False)

        lines = []
        for u in users[:20]:
            member = interaction.guild.get_member(u["user_id"])
            name = member.mention if member else f"<@{u['user_id']}>"
            lines.append(f"{name} — `{u.get('punishment_type','')}` — {u.get('reason','')[:50]}")

        await interaction.response.send_message(embed=info_embed("Punished Users", "\n".join(lines)), ephemeral=False)

    @discord.app_commands.command(name="pardon", description="Remove a user from the punished list (Admin only)")
    @discord.app_commands.describe(user="User to pardon")
    async def pardon(self, interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            return
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        await remove_punished_user(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=success_embed("Pardoned", f"{user.mention} has been removed from the punished list."), ephemeral=False)

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
            await interaction.followup.send(embed=success_embed("Webhooks Nuked", f"Successfully deleted {deleted} webhook(s)."), ephemeral=False)
        except Exception as e:
            await interaction.followup.send(embed=error_embed(f"Failed to delete webhooks: {e}"), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Antinuke(bot))

