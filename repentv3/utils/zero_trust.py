"""
Repent - Zero-Trust Architecture Implementation

Implements a zero-trust security model where no user is implicitly trusted,
even whitelisted users. All actions are continuously verified, and trust
must be explicitly established and maintained.

Core Principles:
- Never trust, always verify
- Least privilege access
- Assume compromise
- Continuous validation
- Explicit authorization
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import secrets
import hashlib

from config import OWNER_ID
from database import get_whitelist_entry, get_guild, log_action
from utils.logger import get_logger
from utils.behavioral_analysis import get_behavioral_engine


class TrustLevel(Enum):
    """Trust levels for users."""
    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AccessDecision(Enum):
    """Access control decisions."""
    DENY = "deny"
    ALLOW_WITH_MONITORING = "allow_monitor"
    ALLOW_WITH_VERIFICATION = "allow_verify"
    ALLOW = "allow"


@dataclass
class TrustScore:
    """Comprehensive trust score for a user."""
    user_id: int
    guild_id: int
    overall_score: float  # 0.0 to 1.0
    behavioral_score: float  # Based on behavior analysis
    temporal_score: float  # Based on temporal patterns
    social_score: float  # Based on social interactions
    privilege_score: float  # Based on privilege usage
    historical_score: float  # Based on historical actions
    whitelist_override: float = 0.0  # Whitelist boost (0.0 to 0.3)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trust_level: TrustLevel = TrustLevel.UNTRUSTED


@dataclass
class AccessRequest:
    """Access request for zero-trust evaluation."""
    user_id: int
    guild_id: int
    action_type: str
    resource_id: Optional[int] = None
    permissions_required: Set[str] = field(default_factory=set)
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str = field(default_factory=lambda: secrets.token_hex(16))


@dataclass
class AccessResponse:
    """Response to access request."""
    request_id: str
    decision: AccessDecision
    trust_score: TrustScore
    reasons: List[str]
    additional_requirements: List[str] = field(default_factory=list)
    monitoring_level: str = "standard"
    valid_until: Optional[datetime] = None
    decision_time_ms: float = 0.0


class ZeroTrustEngine:
    """Main zero-trust security engine."""

    def __init__(self):
        self.trust_scores: Dict[Tuple[int, int], TrustScore] = {}  # (guild_id, user_id) -> TrustScore
        self.access_history: Dict[str, AccessRequest] = {}  # request_id -> AccessRequest
        self.decision_cache: Dict[Tuple[int, int, str], AccessResponse] = {}  # Cache for recent decisions
        self.session_tokens: Dict[str, Dict] = {}  # Session tokens for just-in-time access
        self.logger = get_logger()
        self.behavioral_engine = get_behavioral_engine()
        
        # Configuration
        self.trust_decay_hours = 24  # Trust decays over 24 hours
        self.min_trust_for_critical = 0.8  # Minimum trust for critical actions
        self.min_trust_for_sensitive = 0.5  # Minimum trust for sensitive actions
        self.cache_duration_seconds = 60  # Cache decisions for 60 seconds
        self.session_duration_minutes = 30  # Session tokens valid for 30 minutes

    async def evaluate_access(self, request: AccessRequest) -> AccessResponse:
        """Evaluate an access request using zero-trust principles."""
        start_time = datetime.now(timezone.utc)
        
        # Store request
        self.access_history[request.request_id] = request
        
        # Check cache first
        cache_key = (request.guild_id, request.user_id, request.action_type)
        if cache_key in self.decision_cache:
            cached = self.decision_cache[cache_key]
            if datetime.now(timezone.utc) < cached.valid_until:
                return cached
        
        # Calculate trust score
        trust_score = await self._calculate_trust_score(request)
        
        # Determine access decision
        decision, reasons, additional_requirements = await self._make_access_decision(
            request, trust_score
        )
        
        # Determine monitoring level
        monitoring_level = self._determine_monitoring_level(trust_score, decision)
        
        # Set validity period
        valid_until = datetime.now(timezone.utc) + timedelta(seconds=self.cache_duration_seconds)
        
        # Create response
        response = AccessResponse(
            request_id=request.request_id,
            decision=decision,
            trust_score=trust_score,
            reasons=reasons,
            additional_requirements=additional_requirements,
            monitoring_level=monitoring_level,
            valid_until=valid_until,
            decision_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        
        # Cache decision
        self.decision_cache[cache_key] = response
        
        # Log access evaluation
        await log_action(
            request.guild_id,
            "zero_trust_evaluation",
            request.user_id,
            {
                "action_type": request.action_type,
                "decision": decision.value,
                "trust_score": trust_score.overall_score,
                "reasons": reasons[:3]
            }
        )
        
        return response

    async def _calculate_trust_score(self, request: AccessRequest) -> TrustScore:
        """Calculate comprehensive trust score for user."""
        user_key = (request.guild_id, request.user_id)
        
        # Get or create trust score
        if user_key not in self.trust_scores:
            self.trust_scores[user_key] = TrustScore(
                user_id=request.user_id,
                guild_id=request.guild_id,
                overall_score=0.5,  # Start neutral
                behavioral_score=0.5,
                temporal_score=0.5,
                social_score=0.5,
                privilege_score=0.5,
                historical_score=0.5
            )
        
        trust_score = self.trust_scores[user_key]
        
        # Update behavioral score from behavioral analysis engine
        user_profile = self.behavioral_engine.get_user_profile(request.user_id)
        if user_profile:
            trust_score.behavioral_score = max(0.0, 1.0 - user_profile.risk_score)
        else:
            trust_score.behavioral_score = 0.5
        
        # Calculate temporal score (account age, typical activity times)
        trust_score.temporal_score = await self._calculate_temporal_score(request)
        
        # Calculate social score (guild membership duration, roles)
        trust_score.social_score = await self._calculate_social_score(request)
        
        # Calculate privilege score (responsible privilege usage)
        trust_score.privilege_score = await self._calculate_privilege_score(request)
        
        # Calculate historical score (past actions, violations)
        trust_score.historical_score = await self._calculate_historical_score(request)
        
        # Calculate whitelist override
        trust_score.whitelist_override = await self._calculate_whitelist_override(request)
        
        # Calculate overall score (weighted average)
        weights = {
            'behavioral': 0.30,
            'temporal': 0.15,
            'social': 0.15,
            'privilege': 0.20,
            'historical': 0.20
        }
        
        overall = (
            trust_score.behavioral_score * weights['behavioral'] +
            trust_score.temporal_score * weights['temporal'] +
            trust_score.social_score * weights['social'] +
            trust_score.privilege_score * weights['privilege'] +
            trust_score.historical_score * weights['historical']
        )
        
        # Apply whitelist override (can increase but not decrease trust)
        overall = min(1.0, overall + trust_score.whitelist_override)
        
        trust_score.overall_score = overall
        
        # Determine trust level
        trust_score.trust_level = self._score_to_trust_level(overall)
        
        # Update timestamp
        trust_score.last_updated = datetime.now(timezone.utc)
        
        # Apply trust decay
        await self._apply_trust_decay(trust_score)
        
        return trust_score

    async def _calculate_temporal_score(self, request: AccessRequest) -> float:
        """Calculate temporal trust score."""
        # In a real implementation, this would consider:
        # - Account age
        # - Guild membership duration
        # - Typical activity times
        # - Time since last action
        
        # For now, return neutral score
        return 0.5

    async def _calculate_social_score(self, request: AccessRequest) -> float:
        """Calculate social trust score."""
        # In a real implementation, this would consider:
        # - Guild membership duration
        # - Number of roles
        # - Role hierarchy
        # - Social connections
        
        # For now, return neutral score
        return 0.5

    async def _calculate_privilege_score(self, request: AccessRequest) -> float:
        """Calculate privilege usage score."""
        # In a real implementation, this would consider:
        # - Responsible privilege usage
        # - Permission escalation patterns
        # - Privilege abuse history
        
        # For now, return neutral score
        return 0.5

    async def _calculate_historical_score(self, request: AccessRequest) -> float:
        """Calculate historical trust score."""
        # In a real implementation, this would consider:
        # - Past security violations
        # - Past positive contributions
        # - Warning history
        # - Punishment history
        
        # For now, return neutral score
        return 0.5

    async def _calculate_whitelist_override(self, request: AccessRequest) -> float:
        """Calculate whitelist trust override."""
        # Check if user is whitelisted
        whitelist_entry = await get_whitelist_entry(request.guild_id, request.user_id)
        
        if whitelist_entry:
            trust_level = whitelist_entry.get('trust_level', 0)
            # Trust level 2 = high trust, boost by 0.3
            # Trust level 1 = medium trust, boost by 0.15
            if trust_level >= 2:
                return 0.3
            elif trust_level >= 1:
                return 0.15
        
        return 0.0

    def _score_to_trust_level(self, score: float) -> TrustLevel:
        """Convert score to trust level."""
        if score >= 0.9:
            return TrustLevel.CRITICAL
        elif score >= 0.7:
            return TrustLevel.HIGH
        elif score >= 0.5:
            return TrustLevel.MEDIUM
        elif score >= 0.3:
            return TrustLevel.LOW
        else:
            return TrustLevel.UNTRUSTED

    async def _make_access_decision(
        self,
        request: AccessRequest,
        trust_score: TrustScore
    ) -> Tuple[AccessDecision, List[str], List[str]]:
        """Make access decision based on trust score and action type."""
        reasons = []
        additional_requirements = []
        
        # Always allow bot owner
        if request.user_id == OWNER_ID:
            return AccessDecision.ALLOW, ["Bot owner"], []
        
        # Determine action sensitivity
        action_sensitivity = self._determine_action_sensitivity(request.action_type)
        
        # Check minimum trust requirements
        if action_sensitivity == "critical" and trust_score.overall_score < self.min_trust_for_critical:
            reasons.append(f"Insufficient trust for critical action: {trust_score.overall_score:.2f} < {self.min_trust_for_critical}")
            return AccessDecision.DENY, reasons, []
        
        if action_sensitivity == "sensitive" and trust_score.overall_score < self.min_trust_for_sensitive:
            reasons.append(f"Insufficient trust for sensitive action: {trust_score.overall_score:.2f} < {self.min_trust_for_sensitive}")
            additional_requirements.append("additional_verification")
            return AccessDecision.ALLOW_WITH_VERIFICATION, reasons, additional_requirements
        
        # Make decision based on trust level
        if trust_score.trust_level == TrustLevel.CRITICAL:
            return AccessDecision.ALLOW, ["High trust established"], []
        
        elif trust_score.trust_level == TrustLevel.HIGH:
            if action_sensitivity == "critical":
                return AccessDecision.ALLOW_WITH_MONITORING, ["High trust action with monitoring"], []
            return AccessDecision.ALLOW, ["High trust"], []
        
        elif trust_score.trust_level == TrustLevel.MEDIUM:
            if action_sensitivity in ["critical", "sensitive"]:
                additional_requirements.append("justification")
                return AccessDecision.ALLOW_WITH_VERIFICATION, ["Medium trust for sensitive action"], additional_requirements
            return AccessDecision.ALLOW_WITH_MONITORING, ["Medium trust requires monitoring"], []
        
        elif trust_score.trust_level == TrustLevel.LOW:
            if action_sensitivity != "normal":
                reasons.append(f"Low trust for {action_sensitivity} action")
                return AccessDecision.DENY, reasons, []
            additional_requirements.extend(["justification", "logging"])
            return AccessDecision.ALLOW_WITH_MONITORING, ["Low trust with restrictions"], additional_requirements
        
        else:  # UNTRUSTED
            reasons.append("User not trusted")
            return AccessDecision.DENY, reasons, []

    def _determine_action_sensitivity(self, action_type: str) -> str:
        """Determine sensitivity level of action type."""
        critical_actions = {
            'ban', 'kick', 'channel_delete', 'role_delete', 'server_update',
            'owner_transfer', 'bot_add', 'webhook_create'
        }
        
        sensitive_actions = {
            'role_update', 'role_create', 'channel_create', 'channel_update',
            'permission_change', 'integration_add'
        }
        
        if action_type in critical_actions:
            return "critical"
        elif action_type in sensitive_actions:
            return "sensitive"
        else:
            return "normal"

    def _determine_monitoring_level(self, trust_score: TrustScore, decision: AccessDecision) -> str:
        """Determine monitoring level based on trust and decision."""
        if decision == AccessDecision.DENY:
            return "none"
        elif decision == AccessDecision.ALLOW_WITH_MONITORING:
            return "high"
        elif trust_score.trust_level in [TrustLevel.LOW, TrustLevel.UNTRUSTED]:
            return "high"
        elif trust_score.trust_level == TrustLevel.MEDIUM:
            return "medium"
        else:
            return "standard"

    async def _apply_trust_decay(self, trust_score: TrustScore):
        """Apply trust decay over time."""
        time_since_update = (datetime.now(timezone.utc) - trust_score.last_updated).total_seconds()
        
        if time_since_update > self.trust_decay_hours * 3600:
            # Decay trust by 10% for each decay period past threshold
            decay_periods = time_since_update / (self.trust_decay_hours * 3600)
            decay_factor = 0.9 ** decay_periods
            
            trust_score.overall_score *= decay_factor
            trust_score.behavioral_score *= decay_factor
            trust_score.historical_score *= decay_factor
            
            # Recalculate trust level
            trust_score.trust_level = self._score_to_trust_level(trust_score.overall_score)

    async def verify_session(self, session_token: str) -> bool:
        """Verify a session token for just-in-time access."""
        if session_token not in self.session_tokens:
            return False
        
        session = self.session_tokens[session_token]
        
        # Check if expired
        if datetime.now(timezone.utc) > session['expires']:
            del self.session_tokens[session_token]
            return False
        
        # Check if revoked
        if session.get('revoked', False):
            return False
        
        return True

    async def create_session_token(
        self,
        user_id: int,
        guild_id: int,
        duration_minutes: Optional[int] = None
    ) -> str:
        """Create a session token for just-in-time access."""
        duration = duration_minutes or self.session_duration_minutes
        token = secrets.token_urlsafe(32)
        
        self.session_tokens[token] = {
            'user_id': user_id,
            'guild_id': guild_id,
            'created': datetime.now(timezone.utc),
            'expires': datetime.now(timezone.utc) + timedelta(minutes=duration),
            'revoked': False
        }
        
        return token

    async def revoke_session(self, session_token: str):
        """Revoke a session token."""
        if session_token in self.session_tokens:
            self.session_tokens[session_token]['revoked'] = True

    def update_trust_score(self, user_id: int, guild_id: int, delta: float):
        """Manually adjust trust score (for positive/negative feedback)."""
        user_key = (guild_id, user_id)
        if user_key not in self.trust_scores:
            return
        
        trust_score = self.trust_scores[user_key]
        trust_score.overall_score = max(0.0, min(1.0, trust_score.overall_score + delta))
        trust_score.trust_level = self._score_to_trust_level(trust_score.overall_score)
        trust_score.last_updated = datetime.now(timezone.utc)

    def get_trust_score(self, user_id: int, guild_id: int) -> Optional[TrustScore]:
        """Get current trust score for user."""
        return self.trust_scores.get((guild_id, user_id))

    async def cleanup_expired_sessions(self):
        """Clean up expired session tokens."""
        current_time = datetime.now(timezone.utc)
        expired_tokens = [
            token for token, session in self.session_tokens.items()
            if current_time > session['expires']
        ]
        
        for token in expired_tokens:
            del self.session_tokens[token]

    async def cleanup_old_decisions(self):
        """Clean up old cached decisions."""
        current_time = datetime.now(timezone.utc)
        expired_keys = [
            key for key, response in self.decision_cache.items()
            if response.valid_until < current_time
        ]
        
        for key in expired_keys:
            del self.decision_cache[key]

    def get_statistics(self) -> Dict[str, Any]:
        """Get zero-trust engine statistics."""
        total_trust_scores = len(self.trust_scores)
        trust_level_distribution = {
            level.value: sum(1 for ts in self.trust_scores.values() if ts.trust_level == level)
            for level in TrustLevel
        }
        
        return {
            'total_trust_scores': total_trust_scores,
            'trust_level_distribution': trust_level_distribution,
            'active_sessions': len(self.session_tokens),
            'cached_decisions': len(self.decision_cache),
            'average_trust_score': sum(ts.overall_score for ts in self.trust_scores.values()) / total_trust_scores if total_trust_scores > 0 else 0.0
        }


# Global instance
_zero_trust_engine: Optional[ZeroTrustEngine] = None

def get_zero_trust_engine() -> ZeroTrustEngine:
    """Get the global zero-trust engine instance."""
    global _zero_trust_engine
    if _zero_trust_engine is None:
        _zero_trust_engine = ZeroTrustEngine()
    return _zero_trust_engine