"""
Repent - Multi-Layer Defense System

Advanced multi-layered security architecture that processes events through
independent security layers, each providing different detection capabilities.
Each layer operates independently and results are aggregated for final decision.

Architecture:
Layer 0: Pre-Flight Validation (Basic sanitization, rate limiting)
Layer 1: Behavioral Analysis (User profiling, anomaly detection)
Layer 2: Contextual Analysis (Temporal, social, permission context)
Layer 3: Pattern Recognition (Attack patterns, sequence analysis)
Layer 4: Decision Engine (Risk scoring, response selection)
Layer 5: Response Execution (Multi-stage response execution)
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import secrets
import uuid

from config import OWNER_ID


class ThreatLevel(Enum):
    """Threat level classification."""
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    
    def __lt__(self, other):
        if isinstance(other, ThreatLevel):
            return self.value < other.value
        return NotImplemented
    
    def __le__(self, other):
        if isinstance(other, ThreatLevel):
            return self.value <= other.value
        return NotImplemented
    
    def __gt__(self, other):
        if isinstance(other, ThreatLevel):
            return self.value > other.value
        return NotImplemented
    
    def __ge__(self, other):
        if isinstance(other, ThreatLevel):
            return self.value >= other.value
        return NotImplemented


class ResponseAction(Enum):
    """Response action types."""
    NONE = "none"
    MONITOR = "monitor"
    WARN = "warn"
    TIMEOUT = "timeout"
    STRIP_PERMISSIONS = "strip"
    KICK = "kick"
    BAN = "ban"
    HARD_BAN = "hard_ban"
    LOCKDOWN = "lockdown"


@dataclass
class SecurityContext:
    """Context information for security analysis."""
    guild_id: int
    user_id: int
    action_type: str
    target_id: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerResult:
    """Result from a single security layer."""
    layer_name: str
    threat_level: ThreatLevel
    confidence: float  # 0.0 to 1.0
    reasons: List[str]
    additional_data: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


@dataclass
class DefenseDecision:
    """Final defense decision after all layers."""
    overall_threat_level: ThreatLevel
    confidence: float
    recommended_action: ResponseAction
    layer_results: List[LayerResult]
    decision_reasons: List[str]
    requires_escalation: bool = False
    processing_time_ms: float = 0.0
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class Layer0_PreflightValidation:
    """Layer 0: Pre-Flight Validation
    
    Basic sanitization, input validation, and preliminary checks.
    This layer runs first and can reject obviously invalid requests.
    """

    def __init__(self):
        self._request_signatures: Dict[str, float] = {}
        self._signature_cleanup_interval = 300  # 5 minutes

    async def analyze(self, context: SecurityContext) -> LayerResult:
        """Analyze context for basic validation issues."""
        start_time = time.time()
        threat_level = ThreatLevel.SAFE
        confidence = 0.0
        reasons = []
        additional_data = {}

        # Check for obviously invalid data
        if context.user_id <= 0:
            threat_level = ThreatLevel.CRITICAL
            confidence = 1.0
            reasons.append("Invalid user ID")
            return LayerResult(
                layer_name="Layer0_PreflightValidation",
                threat_level=threat_level,
                confidence=confidence,
                reasons=reasons,
                additional_data=additional_data,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # Check for owner (always safe at this layer)
        if context.user_id == OWNER_ID:
            threat_level = ThreatLevel.SAFE
            confidence = 1.0
            reasons.append("Bot owner")
            return LayerResult(
                layer_name="Layer0_PreflightValidation",
                threat_level=threat_level,
                confidence=confidence,
                reasons=reasons,
                additional_data=additional_data,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # Check for suspicious patterns in additional_data
        if context.additional_data:
            for key, value in context.additional_data.items():
                if isinstance(value, str):
                    # Check for potential injection attempts
                    if len(value) > 10000:  # Unusually long string
                        threat_level = max(threat_level, ThreatLevel.MEDIUM)
                        confidence = max(confidence, 0.5)
                        reasons.append(f"Unusually long {key}")

                    # Check for suspicious characters
                    if any(char in value for char in ['\x00', '\x01', '\x02']):
                        threat_level = max(threat_level, ThreatLevel.HIGH)
                        confidence = max(confidence, 0.8)
                        reasons.append(f"Suspicious characters in {key}")

        # Create request signature for replay detection
        signature = self._create_signature(context)
        current_time = time.time()
        
        # Check for replay attacks
        if signature in self._request_signatures:
            time_diff = current_time - self._request_signatures[signature]
            if time_diff < 1.0:  # Less than 1 second since same signature
                threat_level = max(threat_level, ThreatLevel.HIGH)
                confidence = max(confidence, 0.9)
                reasons.append("Potential replay attack detected")
        
        self._request_signatures[signature] = current_time
        
        # Cleanup old signatures periodically
        if len(self._request_signatures) > 10000:
            cutoff = current_time - self._signature_cleanup_interval
            self._request_signatures = {
                k: v for k, v in self._request_signatures.items() 
                if v > cutoff
            }

        return LayerResult(
            layer_name="Layer0_PreflightValidation",
            threat_level=threat_level,
            confidence=confidence,
            reasons=reasons,
            additional_data=additional_data,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    def _create_signature(self, context: SecurityContext) -> str:
        """Create a unique signature for this request."""
        data = f"{context.guild_id}:{context.user_id}:{context.action_type}:{context.timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()


class Layer1_BehavioralAnalysis:
    """Layer 1: Behavioral Analysis
    
    Analyzes user behavior patterns and detects anomalies based on
    historical behavior and established baselines.
    """

    def __init__(self):
        self._user_profiles: Dict[int, Dict] = {}
        self._action_history: Dict[Tuple[int, int], List[datetime]] = {}  # (guild_id, user_id) -> [timestamps]
        self._velocity_windows: Dict[Tuple[int, int], deque] = {}  # For sliding window analysis

    async def analyze(self, context: SecurityContext) -> LayerResult:
        """Analyze user behavior for anomalies."""
        start_time = time.time()
        threat_level = ThreatLevel.SAFE
        confidence = 0.0
        reasons = []
        additional_data = {}

        user_key = (context.guild_id, context.user_id)
        current_time = datetime.now(timezone.utc)

        # Get or create user profile
        profile = self._get_user_profile(context.user_id)
        
        # Track this action
        self._track_action(context.guild_id, context.user_id, context.action_type, current_time)

        # Analyze action velocity
        velocity_data = self._analyze_velocity(user_key, context.action_type, current_time)
        if velocity_data['is_anomalous']:
            threat_level = max(threat_level, ThreatLevel.MEDIUM)
            confidence = max(confidence, 0.7)
            reasons.append(f"High action velocity: {velocity_data['actions_per_minute']:.1f} actions/min")
            additional_data['velocity'] = velocity_data

        # Analyze action patterns
        pattern_data = self._analyze_patterns(user_key, context.action_type)
        if pattern_data['is_suspicious']:
            threat_level = max(threat_level, ThreatLevel.HIGH)
            confidence = max(confidence, 0.8)
            reasons.append(f"Suspicious action pattern detected")
            additional_data['pattern'] = pattern_data

        # Analyze temporal patterns
        temporal_data = self._analyze_temporal(profile, current_time)
        if temporal_data['is_anomalous']:
            threat_level = max(threat_level, ThreatLevel.LOW)
            confidence = max(confidence, 0.5)
            reasons.append(f"Anomalous temporal pattern: activity at unusual time")
            additional_data['temporal'] = temporal_data

        # Update profile with this action
        self._update_profile(profile, context.action_type, current_time)

        return LayerResult(
            layer_name="Layer1_BehavioralAnalysis",
            threat_level=threat_level,
            confidence=confidence,
            reasons=reasons,
            additional_data=additional_data,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    def _get_user_profile(self, user_id: int) -> Dict:
        """Get or create user behavior profile."""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = {
                'first_seen': datetime.now(timezone.utc),
                'action_counts': {},
                'last_actions': [],
                'typical_hours': set(),
                'total_actions': 0
            }
        return self._user_profiles[user_id]

    def _track_action(self, guild_id: int, user_id: int, action_type: str, timestamp: datetime):
        """Track an action for historical analysis."""
        user_key = (guild_id, user_id)
        if user_key not in self._action_history:
            self._action_history[user_key] = []
        
        self._action_history[user_key].append(timestamp)
        
        # Keep only last 1000 actions per user
        if len(self._action_history[user_key]) > 1000:
            self._action_history[user_key] = self._action_history[user_key][-1000:]

    def _analyze_velocity(self, user_key: Tuple[int, int], action_type: str, current_time: datetime) -> Dict:
        """Analyze action velocity for anomalies."""
        if user_key not in self._action_history:
            return {'is_anomalous': False, 'actions_per_minute': 0.0}
        
        actions = self._action_history[user_key]
        # Count actions in last minute
        one_minute_ago = current_time - timedelta(minutes=1)
        recent_actions = [a for a in actions if a > one_minute_ago]
        
        actions_per_minute = len(recent_actions)
        
        # High velocity threshold
        if actions_per_minute > 30:  # More than 30 actions per minute
            return {
                'is_anomalous': True,
                'actions_per_minute': actions_per_minute,
                'threshold': 30
            }
        
        return {'is_anomalous': False, 'actions_per_minute': actions_per_minute}

    def _analyze_patterns(self, user_key: Tuple[int, int], action_type: str) -> Dict:
        """Analyze action patterns for suspicious sequences."""
        if user_key not in self._action_history:
            return {'is_suspicious': False}
        
        actions = self._action_history[user_key]
        if len(actions) < 5:
            return {'is_suspicious': False}
        
        # Check for rapid sequence of different action types
        recent_actions = actions[-10:]
        action_types = set()
        # In a real implementation, we'd track action types
        # For now, just check frequency
        
        # Suspicious: very rapid actions
        if len(recent_actions) >= 10:
            time_span = (recent_actions[-1] - recent_actions[0]).total_seconds()
            if time_span < 5:  # 10 actions in 5 seconds
                return {
                    'is_suspicious': True,
                    'reason': 'rapid_action_sequence',
                    'actions': len(recent_actions),
                    'time_span': time_span
                }
        
        return {'is_suspicious': False}

    def _analyze_temporal(self, profile: Dict, current_time: datetime) -> Dict:
        """Analyze temporal patterns for anomalies."""
        hour = current_time.hour
        
        # If user has history, check if this hour is unusual
        if profile['total_actions'] > 10:
            if hour not in profile['typical_hours'] and len(profile['typical_hours']) > 0:
                # First time at this hour
                return {
                    'is_anomalous': True,
                    'hour': hour,
                    'typical_hours': sorted(profile['typical_hours'])
                }
        
        return {'is_anomalous': False}

    def _update_profile(self, profile: Dict, action_type: str, timestamp: datetime):
        """Update user profile with new action."""
        profile['action_counts'][action_type] = profile['action_counts'].get(action_type, 0) + 1
        profile['last_actions'].append(timestamp)
        profile['typical_hours'].add(timestamp.hour)
        profile['total_actions'] += 1
        
        # Keep only last 100 actions in profile
        if len(profile['last_actions']) > 100:
            profile['last_actions'] = profile['last_actions'][-100:]


class Layer2_ContextualAnalysis:
    """Layer 2: Contextual Analysis
    
    Analyzes the context surrounding the action including temporal,
    social, permission, and historical context.
    """

    def __init__(self):
        self._recent_guild_events: Dict[int, List[Dict]] = {}
        self._permission_cache: Dict[Tuple[int, int], Set[str]] = {}

    async def analyze(self, context: SecurityContext) -> LayerResult:
        """Analyze context for security implications."""
        start_time = time.time()
        threat_level = ThreatLevel.SAFE
        confidence = 0.0
        reasons = []
        additional_data = {}

        # Analyze guild-wide context
        guild_context = await self._analyze_guild_context(context.guild_id)
        if guild_context['under_attack']:
            threat_level = max(threat_level, ThreatLevel.HIGH)
            confidence = max(confidence, 0.9)
            reasons.append("Guild currently under attack - heightened sensitivity")
            additional_data['guild_context'] = guild_context

        # Analyze recent similar actions
        similar_actions = self._analyze_recent_similar_actions(context)
        if similar_actions['suspicious_count'] > 5:
            threat_level = max(threat_level, ThreatLevel.MEDIUM)
            confidence = max(confidence, 0.7)
            reasons.append(f"High frequency of similar actions: {similar_actions['suspicious_count']}")
            additional_data['similar_actions'] = similar_actions

        # Analyze time context
        time_context = self._analyze_time_context(context)
        if time_context['is_suspicious']:
            threat_level = max(threat_level, ThreatLevel.LOW)
            confidence = max(confidence, 0.4)
            reasons.append("Action at unusual time")
            additional_data['time_context'] = time_context

        return LayerResult(
            layer_name="Layer2_ContextualAnalysis",
            threat_level=threat_level,
            confidence=confidence,
            reasons=reasons,
            additional_data=additional_data,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    async def _analyze_guild_context(self, guild_id: int) -> Dict:
        """Analyze guild-wide security context."""
        if guild_id not in self._recent_guild_events:
            return {'under_attack': False, 'recent_events': []}
        
        recent_events = self._recent_guild_events[guild_id]
        # Keep only last 5 minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        recent_events = [e for e in recent_events if e['timestamp'] > cutoff]
        self._recent_guild_events[guild_id] = recent_events
        
        # Check for high event rate
        if len(recent_events) > 50:  # More than 50 security events in 5 minutes
            return {
                'under_attack': True,
                'recent_events': len(recent_events),
                'event_rate': len(recent_events) / 5  # events per minute
            }
        
        return {'under_attack': False, 'recent_events': len(recent_events)}

    def _analyze_recent_similar_actions(self, context: SecurityContext) -> Dict:
        """Analyze recent similar actions in the guild."""
        guild_events = self._recent_guild_events.get(context.guild_id, [])
        
        similar_count = 0
        for event in guild_events:
            if event.get('action_type') == context.action_type:
                similar_count += 1
        
        return {'suspicious_count': similar_count}

    def _analyze_time_context(self, context: SecurityContext) -> Dict:
        """Analyze if the action time is suspicious."""
        hour = context.timestamp.hour
        
        # Unusual hours: 2 AM - 6 AM server time
        if 2 <= hour <= 6:
            return {'is_suspicious': True, 'hour': hour, 'reason': 'unusual_hours'}
        
        return {'is_suspicious': False}

    def record_guild_event(self, guild_id: int, event_type: str, threat_level: ThreatLevel):
        """Record a security event for guild context analysis."""
        if guild_id not in self._recent_guild_events:
            self._recent_guild_events[guild_id] = []
        
        self._recent_guild_events[guild_id].append({
            'timestamp': datetime.now(timezone.utc),
            'event_type': event_type,
            'threat_level': threat_level,
            'action_type': event_type
        })


class Layer3_PatternRecognition:
    """Layer 3: Pattern Recognition
    
    Recognizes known attack patterns, sequences, and multi-vector attacks.
    """

    def __init__(self):
        self._attack_patterns = self._initialize_attack_patterns()
        self._sequence_tracker: Dict[int, List[Dict]] = {}  # guild_id -> [events]

    def _initialize_attack_patterns(self) -> Dict[str, Dict]:
        """Initialize known attack patterns."""
        return {
            'mass_ban': {
                'description': 'Mass banning of users',
                'threshold': 5,
                'window_seconds': 10,
                'severity': ThreatLevel.CRITICAL
            },
            'mass_kick': {
                'description': 'Mass kicking of users',
                'threshold': 5,
                'window_seconds': 10,
                'severity': ThreatLevel.CRITICAL
            },
            'mass_channel_delete': {
                'description': 'Mass deletion of channels',
                'threshold': 3,
                'window_seconds': 10,
                'severity': ThreatLevel.CRITICAL
            },
            'role_escalation': {
                'description': 'Rapid role permission escalation',
                'threshold': 3,
                'window_seconds': 30,
                'severity': ThreatLevel.HIGH
            },
            'webhook_spam': {
                'description': 'Mass webhook creation',
                'threshold': 5,
                'window_seconds': 10,
                'severity': ThreatLevel.HIGH
            },
            'bot_add_spam': {
                'description': 'Mass bot addition',
                'threshold': 3,
                'window_seconds': 60,
                'severity': ThreatLevel.HIGH
            }
        }

    async def analyze(self, context: SecurityContext) -> LayerResult:
        """Analyze for known attack patterns."""
        start_time = time.time()
        threat_level = ThreatLevel.SAFE
        confidence = 0.0
        reasons = []
        additional_data = {}

        # Track this event in sequence
        self._track_sequence(context)

        # Check against known attack patterns
        matched_patterns = self._check_attack_patterns(context.guild_id)
        
        if matched_patterns:
            for pattern_name, pattern_data in matched_patterns:
                threat_level = max(threat_level, pattern_data['severity'])
                confidence = max(confidence, 0.9)
                reasons.append(f"Matched attack pattern: {pattern_name}")
            
            additional_data['matched_patterns'] = matched_patterns

        # Check for multi-vector attacks
        multi_vector = self._check_multi_vector(context.guild_id)
        if multi_vector['is_multi_vector']:
            threat_level = max(threat_level, ThreatLevel.CRITICAL)
            confidence = max(confidence, 0.95)
            reasons.append(f"Multi-vector attack detected: {multi_vector['vectors']}")
            additional_data['multi_vector'] = multi_vector

        return LayerResult(
            layer_name="Layer3_PatternRecognition",
            threat_level=threat_level,
            confidence=confidence,
            reasons=reasons,
            additional_data=additional_data,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    def _track_sequence(self, context: SecurityContext):
        """Track event sequence for pattern recognition."""
        if context.guild_id not in self._sequence_tracker:
            self._sequence_tracker[context.guild_id] = []
        
        self._sequence_tracker[context.guild_id].append({
            'timestamp': context.timestamp,
            'user_id': context.user_id,
            'action_type': context.action_type,
            'target_id': context.target_id
        })
        
        # Keep only last 100 events
        if len(self._sequence_tracker[context.guild_id]) > 100:
            self._sequence_tracker[context.guild_id] = self._sequence_tracker[context.guild_id][-100:]

    def _check_attack_patterns(self, guild_id: int) -> Dict[str, Dict]:
        """Check if current events match known attack patterns."""
        if guild_id not in self._sequence_tracker:
            return {}
        
        events = self._sequence_tracker[guild_id]
        matched_patterns = {}
        current_time = datetime.now(timezone.utc)
        
        for pattern_name, pattern in self._attack_patterns.items():
            # Count matching actions in the time window
            window_start = current_time - timedelta(seconds=pattern['window_seconds'])
            matching_events = [
                e for e in events 
                if e['timestamp'] > window_start and 
                pattern_name in e['action_type']
            ]
            
            if len(matching_events) >= pattern['threshold']:
                matched_patterns[pattern_name] = {
                    **pattern,
                    'event_count': len(matching_events)
                }
        
        return matched_patterns

    def _check_multi_vector(self, guild_id: int) -> Dict:
        """Check for multi-vector attacks (different attack types simultaneously)."""
        if guild_id not in self._sequence_tracker:
            return {'is_multi_vector': False}
        
        events = self._sequence_tracker[guild_id]
        current_time = datetime.now(timezone.utc)
        window_start = current_time - timedelta(seconds=30)  # 30 second window
        
        recent_events = [e for e in events if e['timestamp'] > window_start]
        
        # Count different attack types
        attack_types = set(e['action_type'] for e in recent_events)
        
        if len(attack_types) >= 3:  # 3 or more different attack types
            return {
                'is_multi_vector': True,
                'vectors': list(attack_types),
                'event_count': len(recent_events)
            }
        
        return {'is_multi_vector': False}


class Layer4_DecisionEngine:
    """Layer 4: Decision Engine
    
    Aggregates results from all layers and makes final security decision.
    Uses weighted scoring and confidence aggregation.
    """

    def __init__(self):
        # Weights for each layer (higher = more important)
        self._layer_weights = {
            'Layer0_PreflightValidation': 0.5,
            'Layer1_BehavioralAnalysis': 0.9,
            'Layer2_ContextualAnalysis': 0.7,
            'Layer3_PatternRecognition': 1.0
        }
        
        # Thresholds for threat levels
        self._threat_thresholds = {
            ThreatLevel.SAFE: 0.0,
            ThreatLevel.LOW: 0.2,
            ThreatLevel.MEDIUM: 0.4,
            ThreatLevel.HIGH: 0.7,
            ThreatLevel.CRITICAL: 0.9
        }

    async def decide(self, layer_results: List[LayerResult]) -> DefenseDecision:
        """Make final defense decision based on all layer results."""
        start_time = time.time()
        
        # Calculate weighted threat score
        weighted_score = 0.0
        total_weight = 0.0
        all_reasons = []
        
        for result in layer_results:
            weight = self._layer_weights.get(result.layer_name, 0.5)
            threat_value = self._threat_thresholds.get(result.threat_level, 0.0)
            
            # Weight the threat value by the layer's confidence
            weighted_score += threat_value * result.confidence * weight
            total_weight += weight
            
            all_reasons.extend([f"[{result.layer_name}] {r}" for r in result.reasons])
        
        # Normalize the score
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 0.0
        
        # Determine threat level from score
        overall_threat_level = self._score_to_threat_level(final_score)
        
        # Calculate overall confidence
        confidences = [r.confidence for r in layer_results if r.confidence > 0]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Determine recommended action
        recommended_action = self._determine_action(overall_threat_level, overall_confidence)
        
        # Check if escalation is needed
        requires_escalation = overall_threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return DefenseDecision(
            overall_threat_level=overall_threat_level,
            confidence=overall_confidence,
            recommended_action=recommended_action,
            layer_results=layer_results,
            decision_reasons=all_reasons,
            requires_escalation=requires_escalation,
            processing_time_ms=processing_time_ms
        )

    def _score_to_threat_level(self, score: float) -> ThreatLevel:
        """Convert numerical score to threat level."""
        if score >= 0.9:
            return ThreatLevel.CRITICAL
        elif score >= 0.7:
            return ThreatLevel.HIGH
        elif score >= 0.4:
            return ThreatLevel.MEDIUM
        elif score >= 0.2:
            return ThreatLevel.LOW
        else:
            return ThreatLevel.SAFE

    def _determine_action(self, threat_level: ThreatLevel, confidence: float) -> ResponseAction:
        """Determine recommended action based on threat level and confidence."""
        if confidence < 0.5:
            # Low confidence - be conservative
            return ResponseAction.MONITOR
        
        action_map = {
            ThreatLevel.SAFE: ResponseAction.NONE,
            ThreatLevel.LOW: ResponseAction.MONITOR,
            ThreatLevel.MEDIUM: ResponseAction.WARN,
            ThreatLevel.HIGH: ResponseAction.TIMEOUT,
            ThreatLevel.CRITICAL: ResponseAction.BAN
        }
        
        return action_map.get(threat_level, ResponseAction.MONITOR)


class Layer5_ResponseExecution:
    """Layer 5: Response Execution
    
    Executes the security response with multi-stage escalation
    and proper error handling.
    """

    def __init__(self):
        self._response_history: Dict[str, List[Dict]] = {}
        self._escalation_timers: Dict[str, asyncio.Task] = {}

    async def execute(self, decision: DefenseDecision, guild, member, reason: str) -> bool:
        """Execute the security response."""
        from database import log_action
        from utils.logger import get_logger
        
        logger = get_logger()
        
        try:
            # Log the decision
            await log_action(
                guild.id,
                "defense_decision",
                member.id,
                {
                    "decision_id": decision.decision_id,
                    "threat_level": decision.overall_threat_level.value,
                    "action": decision.recommended_action.value,
                    "confidence": decision.confidence,
                    "reasons": decision.decision_reasons[:5]  # First 5 reasons
                }
            )
            
            # Execute the action
            success = await self._execute_action(
                decision.recommended_action,
                guild,
                member,
                reason
            )
            
            # Record in history
            self._record_response(decision.decision_id, decision, success)
            
            # Schedule escalation if needed
            if decision.requires_escalation and success:
                await self._schedule_escalation(decision, guild, member, reason)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to execute defense response: {e}", exc_info=True)
            return False

    async def _execute_action(self, action: ResponseAction, guild, member, reason: str) -> bool:
        """Execute a specific response action."""
        try:
            # Check role hierarchy before attempting punishment
            bot_member = guild.me
            
            # Cannot punish server owner
            if member.id == guild.owner_id:
                from utils.logger import get_logger
                logger = get_logger()
                logger.warning(f"Cannot punish server owner {member.id}")
                return False
            
            # Check role hierarchy for punitive actions
            if action in [ResponseAction.TIMEOUT, ResponseAction.STRIP_PERMISSIONS, ResponseAction.KICK, ResponseAction.BAN, ResponseAction.HARD_BAN]:
                if member.roles:
                    user_highest_role = max(member.roles, key=lambda r: r.position)
                    if user_highest_role >= bot_member.top_role:
                        from utils.logger import get_logger
                        logger = get_logger()
                        logger.warning(f"Cannot punish {member.id} - user has higher/equal role {user_highest_role.name}")
                        return False
            
            if action == ResponseAction.NONE:
                return True
            
            elif action == ResponseAction.MONITOR:
                # Just log, no action
                return True
            
            elif action == ResponseAction.WARN:
                try:
                    await member.send(f"⚠️ Security Warning: {reason}")
                except Exception:
                    pass
                return True
            
            elif action == ResponseAction.TIMEOUT:
                until = datetime.now(timezone.utc) + timedelta(minutes=30)
                await member.timeout(until, reason=reason)
                return True
            
            elif action == ResponseAction.STRIP_PERMISSIONS:
                bot_member = guild.me
                roles_to_remove = [
                    role for role in member.roles
                    if role < bot_member.top_role and 
                    role != guild.default_role and 
                    not role.managed
                ]
                await member.remove_roles(*roles_to_remove, reason=reason)
                return True
            
            elif action == ResponseAction.KICK:
                await member.kick(reason=reason)
                return True
            
            elif action == ResponseAction.BAN:
                await guild.ban(member, reason=reason, delete_message_days=0)
                return True
            
            elif action == ResponseAction.HARD_BAN:
                from database import add_hardban
                await guild.ban(member, reason=reason, delete_message_days=0)
                await add_hardban(guild.id, member.id, reason, 0)  # 0 = bot
                return True
            
            elif action == ResponseAction.LOCKDOWN:
                # Trigger guild lockdown
                # This would need to be implemented in the anti-raid system
                pass
            
            return False
            
        except Exception:
            return False

    def _record_response(self, decision_id: str, decision: DefenseDecision, success: bool):
        """Record response execution for audit trail."""
        if decision_id not in self._response_history:
            self._response_history[decision_id] = []
        
        self._response_history[decision_id].append({
            'timestamp': datetime.now(timezone.utc),
            'success': success,
            'action': decision.recommended_action.value
        })

    async def _schedule_escalation(self, decision: DefenseDecision, guild, member, reason: str):
        """Schedule escalation if initial response is insufficient."""
        # In a real implementation, this would monitor the situation
        # and escalate if threats continue
        pass


class MultiLayerDefenseSystem:
    """Main Multi-Layer Defense System Coordinator.
    
    Coordinates all security layers and manages the defense pipeline.
    """

    def __init__(self):
        # Initialize all layers
        self.layer0 = Layer0_PreflightValidation()
        self.layer1 = Layer1_BehavioralAnalysis()
        self.layer2 = Layer2_ContextualAnalysis()
        self.layer3 = Layer3_PatternRecognition()
        self.layer4 = Layer4_DecisionEngine()
        self.layer5 = Layer5_ResponseExecution()
        
        # Statistics
        self._total_analyses = 0
        self._total_threats_detected = 0
        self._layer_execution_times: Dict[str, List[float]] = {}

    async def analyze_event(self, context: SecurityContext) -> DefenseDecision:
        """Analyze a security event through all layers."""
        self._total_analyses += 1
        
        # Execute layers in parallel where possible
        layer_results = await asyncio.gather(
            self.layer0.analyze(context),
            self.layer1.analyze(context),
            self.layer2.analyze(context),
            self.layer3.analyze(context),
            return_exceptions=True
        )
        
        # Filter out exceptions and ensure valid results
        valid_results = []
        for i, result in enumerate(layer_results):
            if isinstance(result, Exception):
                # Log error but continue with other layers
                from utils.logger import get_logger
                logger = get_logger()
                logger.error(f"Layer {i} failed: {result}", exc_info=True)
            elif isinstance(result, LayerResult):
                valid_results.append(result)
                # Track execution time
                layer_name = result.layer_name
                if layer_name not in self._layer_execution_times:
                    self._layer_execution_times[layer_name] = []
                self._layer_execution_times[layer_name].append(result.processing_time_ms)
        
        # Make final decision
        decision = await self.layer4.decide(valid_results)
        
        # Track threats
        if decision.overall_threat_level != ThreatLevel.SAFE:
            self._total_threats_detected += 1
        
        # Record guild event for contextual analysis
        self.layer2.record_guild_event(
            context.guild_id,
            context.action_type,
            decision.overall_threat_level
        )
        
        return decision

    async def handle_security_event(
        self,
        guild,
        member,
        action_type: str,
        target_id: Optional[int] = None,
        additional_data: Optional[Dict] = None
    ) -> DefenseDecision:
        """Handle a security event with full analysis and response."""
        context = SecurityContext(
            guild_id=guild.id,
            user_id=member.id,
            action_type=action_type,
            target_id=target_id,
            additional_data=additional_data or {}
        )
        
        # Analyze through all layers
        decision = await self.analyze_event(context)
        
        # Execute response if action is recommended
        if decision.recommended_action != ResponseAction.NONE:
            reason = f"[Multi-Layer Defense] {decision.overall_threat_level.name}: {', '.join(decision.decision_reasons[:3])}"
            await self.layer5.execute(decision, guild, member, reason)
        
        return decision

    def get_statistics(self) -> Dict:
        """Get system statistics."""
        avg_times = {}
        for layer_name, times in self._layer_execution_times.items():
            if times:
                avg_times[layer_name] = sum(times) / len(times)
        
        return {
            'total_analyses': self._total_analyses,
            'threats_detected': self._total_threats_detected,
            'detection_rate': (self._total_threats_detected / self._total_analyses) if self._total_analyses > 0 else 0,
            'average_layer_times_ms': avg_times
        }


# Global instance
_defense_system: Optional[MultiLayerDefenseSystem] = None

def get_defense_system() -> MultiLayerDefenseSystem:
    """Get the global defense system instance."""
    global _defense_system
    if _defense_system is None:
        _defense_system = MultiLayerDefenseSystem()
    return _defense_system