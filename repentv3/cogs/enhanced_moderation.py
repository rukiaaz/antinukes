"""Repent - Enhanced Moderation System

Advanced moderation tools including mass actions, notes, strikes, and channel management.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID
from database import (
    get_guild, update_guild,
    add_user_note, get_user_notes, delete_user_note,
    add_user_strike, get_user_strikes, get_user_strike_log, clear_user_strikes, remove_user_strike,
    log_action,
)
from utils.embeds import success_embed, error_embed, info_embed, mod_action_embed
from utils.validation import ValidationUtils, ValidationError


class EnhancedModeration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator or interaction.user.id == OWNER_ID

    async def _is_mod(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.ban_members or interaction.user.id == OWNER_ID

    # ── Mass Moderation Commands ──
    @app_commands.command(name="massban", description="Ban multiple users at once (Admin only)")
    @app_commands.describe(users="Users to ban (comma separated)", reason="Reason for ban")
    async def massban(self, interaction: discord.Interaction, users: str, reason: str = "Mass ban"):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        user_mentions = users.replace(',', ' ').split()
        
        if not user_mentions:
            return await interaction.response.send_message(embed=error_embed("No users provided."), ephemeral=True)

        banned_count = 0
        failed_count = 0
        results = []

        for user_str in user_mentions:
            try:
                # Parse user from mention, ID, or name
                user_id = None
                if user_str.startswith("<@") and user_str.endswith(">"):
                    user_id = int(user_str.strip("<@!>"))
                else:
                    try:
                        user_id = int(user_str)
                    except ValueError:
                        # Try to find by name
                        member = guild.get_member_named(user_str)
                        if member:
                            user_id = member.id
                
                if user_id:
                    try:
                        user = guild.get_member(user_id)
                        if user:
                            await guild.ban(user, reason=f"{interaction.user}: {reason}")
                            await log_action(guild.id, "massban", user.id, {"reason": reason, "moderator": interaction.user.id})
                            banned_count += 1
                            results.append(f"✅ {user.name} ({user.id})")
                        else:
                            # Try to ban by ID even if not in server
                            await guild.ban(discord.Object(id=user_id), reason=f"{interaction.user}: {reason}")
                            await log_action(guild.id, "massban", user_id, {"reason": reason, "moderator": interaction.user.id})
                            banned_count += 1
                            results.append(f"✅ {user_id}")
                    except Exception as e:
                        failed_count += 1
                        results.append(f"❌ {user_str}: {str(e)}")
                else:
                    failed_count += 1
                    results.append(f"❌ {user_str}: Invalid user")
            except Exception as e:
                failed_count += 1
                results.append(f"❌ {user_str}: {str(e)}")

        embed = discord.Embed(
            title="🔨 Mass Ban Results",
            description=f"**Banned:** {banned_count} | **Failed:** {failed_count}",
            color=0xFF4444
        )
        if results:
            # Show first 10 results
            results_text = "\n".join(results[:10])
            if len(results) > 10:
                results_text += f"\n... and {len(results) - 10} more"
            embed.add_field(name="Details", value=results_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="masskick", description="Kick multiple users at once (Admin only)")
    @app_commands.describe(users="Users to kick (comma separated)", reason="Reason for kick")
    async def masskick(self, interaction: discord.Interaction, users: str, reason: str = "Mass kick"):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        guild = interaction.guild
        user_mentions = users.replace(',', ' ').split()
        
        if not user_mentions:
            return await interaction.response.send_message(embed=error_embed("No users provided."), ephemeral=True)

        kicked_count = 0
        failed_count = 0
        results = []

        for user_str in user_mentions:
            try:
                user = None
                if user_str.startswith("<@") and user_str.endswith(">"):
                    user_id = int(user_str.strip("<@!>"))
                    user = guild.get_member(user_id)
                else:
                    try:
                        user_id = int(user_str)
                        user = guild.get_member(user_id)
                    except ValueError:
                        user = guild.get_member_named(user_str)
                
                if user:
                    try:
                        await user.kick(reason=f"{interaction.user}: {reason}")
                        await log_action(guild.id, "masskick", user.id, {"reason": reason, "moderator": interaction.user.id})
                        kicked_count += 1
                        results.append(f"✅ {user.name} ({user.id})")
                    except Exception as e:
                        failed_count += 1
                        results.append(f"❌ {user.name}: {str(e)}")
                else:
                    failed_count += 1
                    results.append(f"❌ {user_str}: User not found")
            except Exception as e:
                failed_count += 1
                results.append(f"❌ {user_str}: {str(e)}")

        embed = discord.Embed(
            title="👢 Mass Kick Results",
            description=f"**Kicked:** {kicked_count} | **Failed:** {failed_count}",
            color=0xFFAA00
        )
        if results:
            results_text = "\n".join(results[:10])
            if len(results) > 10:
                results_text += f"\n... and {len(results) - 10} more"
            embed.add_field(name="Details", value=results_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="softban", description="Ban and immediately unban (deletes messages)")
    @app_commands.describe(user="User to softban", reason="Reason for softban")
    async def softban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Ban Members permission required."), ephemeral=True)

        try:
            await interaction.guild.ban(user, reason=f"Softban: {interaction.user}: {reason}")
            await interaction.guild.unban(user, reason=f"Softban: {interaction.user}: {reason}")
            await log_action(interaction.guild.id, "softban", user.id, {"reason": reason, "moderator": interaction.user.id})
            await interaction.response.send_message(
                embed=mod_action_embed("Softban", interaction.user, user, reason, 0xFFAA00),
                ephemeral=False,
            )
        except Exception as e:
            await interaction.response.send_message(embed=error_embed(f"Failed to softban: {str(e)}"), ephemeral=True)

    @app_commands.command(name="tempban", description="Temporarily ban a user")
    @app_commands.describe(
        user="User to tempban",
        duration="Duration (e.g., 1d, 12h, 30m)",
        reason="Reason for tempban"
    )
    async def tempban(self, interaction: discord.Interaction, user: discord.Member, duration: str, reason: str = "No reason"):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Ban Members permission required."), ephemeral=True)

        try:
            # Parse duration
            duration_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            time_unit = duration[-1].lower()
            if time_unit not in duration_map:
                return await interaction.response.send_message(embed=error_embed("Invalid duration format. Use: 1d, 12h, 30m, etc."), ephemeral=True)
            
            time_value = int(duration[:-1])
            seconds = time_value * duration_map[time_unit]
            
            # Ban the user
            await interaction.guild.ban(user, reason=f"Tempban ({duration}): {interaction.user}: {reason}")
            await log_action(interaction.guild.id, "tempban", user.id, {"reason": reason, "duration": duration, "moderator": interaction.user.id})
            
            # Schedule unban
            async def unban_task():
                try:
                    await asyncio.sleep(seconds)
                    await interaction.guild.unban(user, reason="Tempban expired")
                    await log_action(interaction.guild.id, "tempban_expire", user.id, {"original_reason": reason})
                except Exception:
                    pass
            
            asyncio.create_task(unban_task())
            
            embed = mod_action_embed(f"Tempban ({duration})", interaction.user, user, reason, 0xFF4444)
            embed.add_field(name="Duration", value=duration, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Invalid duration format. Use: 1d, 12h, 30m, etc."), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=error_embed(f"Failed to tempban: {str(e)}"), ephemeral=True)

    # ── User Management (Notes & Strikes) ──
    @app_commands.command(name="note", description="Add a private moderation note for a user (Mod only)")
    @app_commands.describe(user="User to add note for", note="Note content")
    async def note(self, interaction: discord.Interaction, user: discord.Member, note: str):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Moderator permission required."), ephemeral=True)

        await add_user_note(interaction.guild.id, user.id, note, interaction.user.id)
        await log_action(interaction.guild.id, "note_added", user.id, {"note": note, "added_by": interaction.user.id})
        
        await interaction.response.send_message(
            embed=success_embed("Note Added", f"Added note for {user.mention}:\n`{note[:100]}{'...' if len(note) > 100 else ''}`"),
            ephemeral=True,
        )

    @app_commands.command(name="notes", description="View moderation notes for a user (Mod only)")
    @app_commands.describe(user="User to view notes for")
    async def notes(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Moderator permission required."), ephemeral=True)

        notes = await get_user_notes(interaction.guild.id, user.id)
        
        if not notes:
            return await interaction.response.send_message(
                embed=info_embed("User Notes", f"No notes found for {user.mention}"),
                ephemeral=True,
            )

        embed = discord.Embed(
            title=f"📝 Notes for {user.name}",
            color=0x4488FF
        )
        
        # Show first 10 notes
        for i, note_data in enumerate(notes[:10], 1):
            added_by = interaction.guild.get_member(note_data["added_by"])
            added_by_name = added_by.name if added_by else f"<@{note_data['added_by']}>"
            timestamp = note_data["timestamp"]
            
            embed.add_field(
                name=f"Note #{i} - {added_by_name}",
                value=f"{note_data['note'][:200]}{'...' if len(note_data['note']) > 200 else ''}\n*{timestamp}*",
                inline=False
            )
        
        if len(notes) > 10:
            embed.set_footer(text=f"Showing 10 of {len(notes)} notes")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="strike", description="Add a strike to a user (Mod only)")
    @app_commands.describe(user="User to strike", reason="Reason for strike")
    async def strike(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Moderator permission required."), ephemeral=True)

        await add_user_strike(interaction.guild.id, user.id, reason, interaction.user.id)
        strike_info = await get_user_strikes(interaction.guild.id, user.id)
        strike_count = strike_info.get("strikes", 0)
        
        await log_action(interaction.guild.id, "strike_added", user.id, {"reason": reason, "strike_count": strike_count, "added_by": interaction.user.id})
        
        embed = discord.Embed(
            title="⚠️ Strike Added",
            description=f"Strike added to {user.mention}\n**Total Strikes:** {strike_count}",
            color=0xFF4444
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        
        # Auto-punishment if 3+ strikes
        if strike_count >= 3:
            settings = await get_guild(interaction.guild.id)
            punishment = settings.get("punishment", "ban")
            embed.add_field(
                name="⚠️ Auto-Punishment",
                value=f"User has reached {strike_count} strikes. Consider issuing a {punishment}.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="strikes", description="View strikes for a user (Mod only)")
    @app_commands.describe(user="User to view strikes for")
    async def strikes(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Moderator permission required."), ephemeral=True)

        strike_info = await get_user_strikes(interaction.guild.id, user.id)
        strike_log = await get_user_strike_log(interaction.guild.id, user.id)
        strike_count = strike_info.get("strikes", 0)
        
        embed = discord.Embed(
            title=f"⚠️ Strikes for {user.name}",
            description=f"**Total Strikes:** {strike_count}",
            color=0xFF4444
        )
        
        if strike_log:
            for log_data in strike_log[:5]:
                added_by = interaction.guild.get_member(log_data["added_by"])
                added_by_name = added_by.name if added_by else f"<@{log_data['added_by']}>"
                embed.add_field(
                    name=f"Strike by {added_by_name}",
                    value=f"{log_data['reason']}\n*{log_data['timestamp']}*",
                    inline=False
                )
        
        if len(strike_log) > 5:
            embed.set_footer(text=f"Showing 5 of {len(strike_log)} strikes")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="forgive", description="Remove a strike from a user (Mod only)")
    @app_commands.describe(user="User to forgive")
    async def forgive(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Moderator permission required."), ephemeral=True)

        await remove_user_strike(interaction.guild.id, user.id)
        strike_info = await get_user_strikes(interaction.guild.id, user.id)
        strike_count = strike_info.get("strikes", 0)
        
        await log_action(interaction.guild.id, "strike_removed", user.id, {"strike_count": strike_count, "removed_by": interaction.user.id})
        
        await interaction.response.send_message(
            embed=success_embed("Strike Removed", f"Strike removed from {user.mention}\n**Remaining Strikes:** {strike_count}"),
            ephemeral=False,
        )

    @app_commands.command(name="clearstrikes", description="Clear all strikes for a user (Admin only)")
    @app_commands.describe(user="User to clear strikes for")
    async def clearstrikes(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("Administrator required."), ephemeral=True)

        await clear_user_strikes(interaction.guild.id, user.id)
        await log_action(interaction.guild.id, "strikes_cleared", user.id, {"cleared_by": interaction.user.id})
        
        await interaction.response.send_message(
            embed=success_embed("Strikes Cleared", f"All strikes cleared for {user.mention}"),
            ephemeral=False,
        )

    # ── Channel Management ──
    @app_commands.command(name="channellock", description="Lock a channel (no one can send)")
    @app_commands.describe(channel="Channel to lock (default: current)", reason="Reason for lock")
    async def channellock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "Channel locked"):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Manage Channels permission required."), ephemeral=True)

        channel = channel or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=False, reason=f"{interaction.user}: {reason}")
        await log_action(interaction.guild.id, "channel_lock", channel.id, {"reason": reason, "moderator": interaction.user.id})
        
        await interaction.response.send_message(
            embed=success_embed("Channel Locked", f"{channel.mention} has been locked."),
            ephemeral=False,
        )

    @app_commands.command(name="channelunlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock (default: current)", reason="Reason for unlock")
    async def channelunlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "Channel unlocked"):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Manage Channels permission required."), ephemeral=True)

        channel = channel or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=None, reason=f"{interaction.user}: {reason}")
        await log_action(interaction.guild.id, "channel_unlock", channel.id, {"reason": reason, "moderator": interaction.user.id})
        
        await interaction.response.send_message(
            embed=success_embed("Channel Unlocked", f"{channel.mention} has been unlocked."),
            ephemeral=False,
        )

    @app_commands.command(name="setslowmode", description="Set slowmode for a channel")
    @app_commands.describe(
        channel="Channel to set slowmode for (default: current)",
        seconds="Slowmode delay in seconds (0 to disable)"
    )
    async def setslowmode(self, interaction: discord.Interaction, channel: discord.TextChannel = None, seconds: int = 0):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Manage Channels permission required."), ephemeral=True)

        channel = channel or interaction.channel
        await channel.edit(slowmode_delay=seconds, reason=f"{interaction.user}: Set slowmode")
        await log_action(interaction.guild.id, "slowmode_set", channel.id, {"seconds": seconds, "moderator": interaction.user.id})
        
        if seconds > 0:
            await interaction.response.send_message(
                embed=success_embed("Slowmode Set", f"{channel.mention} slowmode set to {seconds} seconds."),
                ephemeral=False,
            )
        else:
            await interaction.response.send_message(
                embed=success_embed("Slowmode Disabled", f"{channel.mention} slowmode disabled."),
                ephemeral=False,
            )

    @app_commands.command(name="nsfw", description="Mark a channel as NSFW")
    @app_commands.describe(channel="Channel to mark (default: current)")
    async def nsfw(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Manage Channels permission required."), ephemeral=True)

        channel = channel or interaction.channel
        await channel.edit(nsfw=True, reason=f"{interaction.user}: Marked as NSFW")
        await log_action(interaction.guild.id, "nsfw_marked", channel.id, {"moderator": interaction.user.id})
        
        await interaction.response.send_message(
            embed=success_embed("NSFW Enabled", f"{channel.mention} is now marked as NSFW."),
            ephemeral=False,
        )

    @app_commands.command(name="nsfwremove", description="Remove NSFW marking from a channel")
    @app_commands.describe(channel="Channel to unmark (default: current)")
    async def nsfwremove(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not await self._is_mod(interaction):
            return await interaction.response.send_message(embed=error_embed("Manage Channels permission required."), ephemeral=True)

        channel = channel or interaction.channel
        await channel.edit(nsfw=False, reason=f"{interaction.user}: Removed NSFW marking")
        await log_action(interaction.guild.id, "nsfw_removed", channel.id, {"moderator": interaction.user.id})
        
        await interaction.response.send_message(
            embed=success_embed("NSFW Disabled", f"{channel.mention} is no longer marked as NSFW."),
            ephemeral=False,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EnhancedModeration(bot))
