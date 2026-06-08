"""
Repent - Advanced Antinuke System with Multi-Layer Defense

Enhanced antinuke system that integrates:
- Multi-layer defense architecture
- Behavioral analysis and anomaly detection
- Zero-trust security model
- Advanced threat detection

This module extends the base antinuke with enterprise-grade security features.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Set
import discord
from discord.ext import commands

from cogs.antinuke import Antinuke as BaseAntinuke
from config import OWNER_ID, DEFAULT_PUNISHMENT
from database import get_guild, log_action
from utils.multi_layer_defense import (
    get_defense_system,
    SecurityContext,
    ThreatLevel,
    ResponseAction
)
from utils.behavioral_analysis import (
    get_behavioral_engine,
    AnomalyType
)
from utils.zero_trust import (
    get_zero_trust_engine,
    AccessRequest,
    AccessDecision
)
from utils.logger import get_logger


class AdvancedAntinuke(BaseAntinuke):
    """Advanced antinuke with multi-layer defense and behavioral analysis."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.defense_system = get_defense_system()
        self.behavioral_engine = get_behavioral_engine()
        self.zero_trust_engine = get_zero_trust_engine()
        self.logger = get_logger()
        
        # Track which security systems are enabled
        self.multi_layer_enabled = True
        self.behavioral_analysis_enabled = True
        self.zero_trust_enabled = True

    async def process_audit_entry(self, entry: discord.AuditLogEntry) -> None:
        """Process audit log entry with advanced security analysis."""
        if not entry.guild or not entry.user:
            return

        if entry.id in self._processed_entries:
            return
        self._processed_entries[entry.id] = datetime.now(timezone.utc)

        guild = entry.guild
        attacker = entry.user
        action = entry.action

        # Determine action type
        action_type = self._determine_action_type(entry)
        if not action_type:
            return

        target_id = getattr(entry.target, 'id', None) if entry.target else None

        # ── ZERO-TRUST VERIFICATION ──
        if self.zero_trust_enabled:
            zero_trust_decision = await self._verify_zero_trust(
                guild, attacker, action_type, target_id
            )
            
            if zero_trust_decision.decision == AccessDecision.DENY:
                await self._handle_zero_trust_deny(
                    guild, attacker, action_type, zero_trust_decision
                )
                return

        # ── BEHAVIORAL ANALYSIS ──
        if self.behavioral_analysis_enabled:
            anomaly_report = await self.behavioral_engine.analyze_user_action(
                guild.id, attacker.id, action_type
            )
            
            if anomaly_report.overall_score > 0.7:  # High anomaly
                await self._handle_high_anomaly(
                    guild, attacker, action_type, anomaly_report
                )
                # Continue to multi-layer defense for comprehensive analysis

        # ── MULTI-LAYER DEFENSE ──
        if self.multi_layer_enabled:
            security_context = SecurityContext(
                guild_id=guild.id,
                user_id=attacker.id,
                action_type=action_type,
                target_id=target_id,
                additional_data={
                    'audit_log_action': str(action),
                    'target_name': getattr(entry.target, 'name', None) if entry.target else None
                }
            )
            
            defense_decision = await self.defense_system.analyze_event(security_context)
            
            if defense_decision.overall_threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                await self._handle_defense_decision(
                    guild, attacker, defense_decision, action_type
                )
                return

        # ── FALLBACK TO BASE ANTINUKE ──
        # If advanced systems don't trigger, use base antinuke logic
        await super().process_audit_entry(entry)

    def _determine_action_type(self, entry: discord.AuditLogEntry) -> Optional[str]:
        """Determine action type from audit log entry."""
        action = entry.action
        
        action_map = {
            discord.AuditLogAction.bot_add: "bot_add",
            discord.AuditLogAction.webhook_create: "webhook_create",
            discord.AuditLogAction.webhook_delete: "webhook_delete",
            discord.AuditLogAction.role_update: "role_update",
            discord.AuditLogAction.member_role_update: "member_role_update",
            discord.AuditLogAction.ban: "ban",
            discord.AuditLogAction.unban: "unban",
            discord.AuditLogAction.kick: "kick",
            discord.AuditLogAction.channel_delete: "channel_delete",
            discord.AuditLogAction.channel_create: "channel_create",
            discord.AuditLogAction.role_delete: "role_delete",
            discord.AuditLogAction.role_create: "role_create",
            discord.AuditLogAction.emoji_delete: "emoji_delete",
            discord.AuditLogAction.sticker_delete: "sticker_delete",
            discord.AuditLogAction.guild_update: "server_update",
        }
        
        return action_map.get(action)

    async def _verify_zero_trust(
        self,
        guild: discord.Guild,
        attacker: discord.Member,
        action_type: str,
        target_id: Optional[int]
    ) -> AccessDecision:
        """Verify action using zero-trust principles."""
        access_request = AccessRequest(
            user_id=attacker.id,
            guild_id=guild.id,
            action_type=action_type,
            resource_id=target_id,
            context={
                'audit_log': True
            }
        )
        
        decision = await self.zero_trust_engine.evaluate_access(access_request)
        
        # Log zero-trust evaluation
        await log_action(
            guild.id,
            "zero_trust_check",
            attacker.id,
            {
                "action_type": action_type,
                "decision": decision.decision.value,
                "trust_score": decision.trust_score.overall_score,
                "reasons": decision.reasons
            }
        )
        
        return decision

    async def _handle_zero_trust_deny(
        self,
        guild: discord.Guild,
        attacker: discord.Member,
        action_type: str,
        decision
    ):
        """Handle zero-trust access denial."""
        reason = f"[Zero-Trust Denied] {', '.join(decision.reasons[:3])}"
        
        self.logger.security(
            "ZERO_TRUST_DENY",
            f"Action {action_type} denied for user {attacker.id}",
            guild_id=guild.id,
            user_id=attacker.id
        )
        
        # Apply punishment based on sensitivity
        if decision.trust_score.overall_score < 0.3:
            # Very low trust - immediate ban
            await self._apply_punishment(guild, attacker, "ban", reason)
        elif decision.trust_score.overall_score < 0.5:
            # Low trust - timeout
            await self._apply_punishment(guild, attacker, "timeout", reason)
        else:
            # Medium trust - strip permissions
            await self._apply_punishment(guild, attacker, "strip", reason)

    async def _handle_high_anomaly(
        self,
        guild: discord.Guild,
        attacker: discord.Member,
        action_type: str,
        anomaly_report
    ):
        """Handle high anomaly scores from behavioral analysis."""
        reason = f"[Behavioral Anomaly] Score: {anomaly_report.overall_score:.2f}, Types: {', '.join([a.anomaly_type.value for a in anomaly_report.individual_anomalies])}"
        
        self.logger.anomaly_detected(
            guild.id,
            attacker.id,
            anomaly_report.overall_score,
            [a.anomaly_type.value for a in anomaly_report.individual_anomalies]
        )
        
        # Take action based on anomaly score
        if anomaly_report.overall_score > 0.9:
            await self._apply_punishment(guild, attacker, "ban", reason)
        elif anomaly_report.overall_score > 0.8:
            await self._apply_punishment(guild, attacker, "timeout", reason)
        elif anomaly_report.recommended_action in ["restrict", "block"]:
            await self._apply_punishment(guild, attacker, "strip", reason)

    async def _handle_defense_decision(
        self,
        guild: discord.Guild,
        attacker: discord.Member,
        defense_decision,
        action_type: str
    ):
        """Handle defense decision from multi-layer system."""
        reason = f"[Multi-Layer Defense] Threat: {defense_decision.overall_threat_level.name}, Reasons: {', '.join(defense_decision.decision_reasons[:3])}"
        
        # Execute the recommended response
        member = guild.get_member(attacker.id)
        if not member:
            try:
                member = await guild.fetch_member(attacker.id)
            except Exception:
                return
        
        await self.defense_system.layer5.execute(
            defense_decision,
            guild,
            member,
            reason
        )

    async def get_security_status(self, guild_id: int) -> dict:
        """Get comprehensive security status for a guild."""
        defense_stats = self.defense_system.get_statistics()
        behavioral_stats = self.behavioral_engine.get_statistics()
        zero_trust_stats = self.zero_trust_engine.get_statistics()
        
        return {
            'multi_layer_defense': {
                'enabled': self.multi_layer_enabled,
                'total_analyses': defense_stats['total_analyses'],
                'threats_detected': defense_stats['threats_detected'],
                'detection_rate': defense_stats['detection_rate']
            },
            'behavioral_analysis': {
                'enabled': self.behavioral_analysis_enabled,
                'total_profiles': behavioral_stats['total_profiles'],
                'high_risk_users': behavioral_stats['users_with_high_risk']
            },
            'zero_trust': {
                'enabled': self.zero_trust_enabled,
                'total_trust_scores': zero_trust_stats['total_trust_scores'],
                'average_trust_score': zero_trust_stats['average_trust_score'],
                'active_sessions': zero_trust_stats['active_sessions']
            }
        }

    def toggle_multi_layer(self, enabled: bool):
        """Toggle multi-layer defense."""
        self.multi_layer_enabled = enabled

    def toggle_behavioral_analysis(self, enabled: bool):
        """Toggle behavioral analysis."""
        self.behavioral_analysis_enabled = enabled

    def toggle_zero_trust(self, enabled: bool):
        """Toggle zero-trust verification."""
        self.zero_trust_enabled = enabled


async def setup(bot: commands.Bot):
    """Setup the advanced antinuke cog."""
    # Remove base antinuke if loaded
    if "Antinuke" in bot.cogs:
        await bot.remove_cog("Antinuke")
    
    await bot.add_cog(AdvancedAntinuke(bot))