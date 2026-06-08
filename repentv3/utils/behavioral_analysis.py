"""
Repent - Behavioral Analysis and Anomaly Detection System

Advanced behavioral profiling and anomaly detection that learns normal
user behavior patterns and detects deviations that may indicate compromise
or attack.

Features:
- User behavior profiling (action patterns, timing, sequences)
- Server baseline modeling (normal activity patterns)
- Anomaly scoring with multiple factors
- Machine learning integration for pattern detection
- Continuous learning and adaptation
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import numpy as np
from enum import Enum

from database import get_guild, log_action
from utils.logger import get_logger


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    VELOCITY = "velocity"           # Unusually fast actions
    TEMPORAL = "temporal"           # Unusual timing
    SEQUENTIAL = "sequential"       # Unusual action sequences
    PERMISSION = "permission"       # Unexpected permission usage
    SOCIAL = "social"              # Unusual social interactions
    NEW_ACCOUNT = "new_account"    # New account with unusual behavior
    CROSS_GUILD = "cross_guild"    # Correlated anomalies across guilds


@dataclass
class UserProfile:
    """Behavioral profile for a user."""
    user_id: int
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_actions: int = 0
    action_counts: Dict[str, int] = field(default_factory=dict)
    action_timestamps: Dict[str, List[datetime]] = field(default_factory=lambda: defaultdict(list))
    typical_hours: Set[int] = field(default_factory=set)
    typical_days: Set[int] = field(default_factory=set)
    action_sequences: List[List[str]] = field(default_factory=list)
    peak_activity_hour: Optional[int] = None
    average_actions_per_hour: float = 0.0
    trust_score: float = 1.0  # 0.0 to 1.0
    risk_score: float = 0.0   # 0.0 to 1.0
    last_anomaly_score: float = 0.0
    anomaly_count: int = 0


@dataclass
class ServerBaseline:
    """Baseline model for server behavior."""
    guild_id: int
    established: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_members: int = 0
    typical_join_rate: float = 0.0  # joins per hour
    typical_message_rate: float = 0.0  # messages per hour
    peak_hours: Set[int] = field(default_factory=set)
    quiet_hours: Set[int] = field(default_factory=set)
    action_distribution: Dict[str, float] = field(default_factory=dict)
    member_activity_pattern: Dict[int, float] = field(default_factory=dict)  # hour -> activity level


@dataclass
class AnomalyDetection:
    """Result of anomaly detection."""
    anomaly_type: AnomalyType
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    details: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[int] = None
    guild_id: Optional[int] = None


@dataclass
class AnomalyReport:
    """Comprehensive anomaly report."""
    overall_score: float
    individual_anomalies: List[AnomalyDetection]
    recommended_action: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StatisticalAnomalyDetector:
    """Statistical methods for anomaly detection."""

    @staticmethod
    def z_score(value: float, mean: float, std: float) -> float:
        """Calculate Z-score for anomaly detection."""
        if std == 0:
            return 0.0
        return abs((value - mean) / std)

    @staticmethod
    def iqr_outlier(values: List[float], multiplier: float = 1.5) -> Tuple[float, float, List[float]]:
        """Detect outliers using IQR method."""
        if len(values) < 4:
            return 0.0, 0.0, []
        
        sorted_values = sorted(values)
        q1 = sorted_values[len(sorted_values) // 4]
        q3 = sorted_values[3 * len(sorted_values) // 4]
        iqr = q3 - q1
        
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr
        
        outliers = [v for v in values if v < lower_bound or v > upper_bound]
        
        return lower_bound, upper_bound, outliers

    @staticmethod
    def moving_average(values: List[float], window: int) -> List[float]:
        """Calculate moving average."""
        if len(values) < window:
            return values
        
        result = []
        for i in range(len(values) - window + 1):
            window_values = values[i:i + window]
            result.append(sum(window_values) / window)
        
        return result

    @staticmethod
    def detect_velocity_anomaly(timestamps: List[datetime], window_seconds: int = 60) -> Dict[str, Any]:
        """Detect velocity anomalies in a series of timestamps."""
        if len(timestamps) < 3:
            return {'is_anomalous': False, 'velocity': 0.0}
        
        # Calculate time deltas
        deltas = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i-1]).total_seconds()
            deltas.append(delta)
        
        if not deltas:
            return {'is_anomalous': False, 'velocity': 0.0}
        
        # Calculate average velocity (actions per second)
        avg_delta = sum(deltas) / len(deltas)
        velocity = 1.0 / avg_delta if avg_delta > 0 else 0.0
        
        # Check for unusually high velocity
        recent_timestamps = [t for t in timestamps if t > datetime.now(timezone.utc) - timedelta(seconds=window_seconds)]
        recent_velocity = len(recent_timestamps) / window_seconds
        
        # Anomaly if recent velocity is 3x higher than historical average
        is_anomalous = recent_velocity > (velocity * 3) and recent_velocity > 1.0
        
        return {
            'is_anomalous': is_anomalous,
            'velocity': recent_velocity,
            'historical_velocity': velocity,
            'ratio': recent_velocity / velocity if velocity > 0 else 0.0
        }


class BehavioralAnalysisEngine:
    """Main behavioral analysis engine."""

    def __init__(self):
        self.user_profiles: Dict[int, UserProfile] = {}
        self.server_baselines: Dict[int, ServerBaseline] = {}
        self.detector = StatisticalAnomalyDetector()
        self.logger = get_logger()
        
        # Action tracking for real-time analysis
        self.recent_actions: Dict[Tuple[int, int], deque] = {}  # (guild_id, user_id) -> deque of actions
        self.guild_recent_actions: Dict[int, deque] = {}  # guild_id -> deque of actions
        
        # Anomaly history
        self.anomaly_history: Dict[int, List[AnomalyDetection]] = {}  # user_id -> [anomalies]
        
        # Configuration
        self.analysis_window_minutes = 30
        self.min_profile_actions = 10  # Minimum actions before profile is considered reliable
        self.velocity_threshold = 10.0  # actions per minute
        self.anomaly_threshold = 0.7  # score above this is considered anomalous

    async def analyze_user_action(
        self,
        guild_id: int,
        user_id: int,
        action_type: str,
        timestamp: Optional[datetime] = None,
        additional_context: Optional[Dict] = None
    ) -> AnomalyReport:
        """Analyze a user action for anomalies."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Get or create user profile
        profile = self._get_or_create_profile(user_id)
        
        # Update profile with this action
        self._update_profile(profile, guild_id, action_type, timestamp)
        
        # Track recent actions
        self._track_action(guild_id, user_id, action_type, timestamp)
        
        # Get or create server baseline
        baseline = self._get_or_create_baseline(guild_id)
        self._update_baseline(baseline, guild_id)
        
        # Perform anomaly detection
        anomalies = []
        
        # Velocity anomaly
        velocity_anomaly = self._detect_velocity_anomaly(profile, guild_id, user_id)
        if velocity_anomaly:
            anomalies.append(velocity_anomaly)
        
        # Temporal anomaly
        temporal_anomaly = self._detect_temporal_anomaly(profile, baseline, timestamp)
        if temporal_anomaly:
            anomalies.append(temporal_anomaly)
        
        # Sequential anomaly
        sequential_anomaly = self._detect_sequential_anomaly(profile, action_type)
        if sequential_anomaly:
            anomalies.append(sequential_anomaly)
        
        # New account anomaly
        if profile.total_actions < 20:
            new_account_anomaly = self._detect_new_account_anomaly(profile, action_type)
            if new_account_anomaly:
                anomalies.append(new_account_anomaly)
        
        # Calculate overall anomaly score
        overall_score = self._calculate_overall_score(anomalies)
        
        # Determine recommended action
        recommended_action = self._determine_action(overall_score, anomalies)
        
        # Update user risk score
        profile.risk_score = max(profile.risk_score, overall_score)
        profile.last_anomaly_score = overall_score
        if overall_score > self.anomaly_threshold:
            profile.anomaly_count += 1
        
        # Store anomalies in history
        if anomalies:
            if user_id not in self.anomaly_history:
                self.anomaly_history[user_id] = []
            self.anomaly_history[user_id].extend(anomalies)
            
            # Keep only last 100 anomalies
            if len(self.anomaly_history[user_id]) > 100:
                self.anomaly_history[user_id] = self.anomaly_history[user_id][-100:]
            
            # Log significant anomalies
            if overall_score > self.anomaly_threshold:
                await log_action(
                    guild_id,
                    "anomaly_detected",
                    user_id,
                    {
                        "overall_score": overall_score,
                        "anomaly_types": [a.anomaly_type.value for a in anomalies],
                        "action_type": action_type,
                        "recommended_action": recommended_action
                    }
                )
                self.logger.anomaly_detected(
                    guild_id,
                    user_id,
                    overall_score,
                    [a.anomaly_type.value for a in anomalies]
                )
        
        return AnomalyReport(
            overall_score=overall_score,
            individual_anomalies=anomalies,
            recommended_action=recommended_action,
            context={
                'user_id': user_id,
                'guild_id': guild_id,
                'action_type': action_type,
                'profile_reliability': min(profile.total_actions / self.min_profile_actions, 1.0),
                'user_risk_score': profile.risk_score
            },
            timestamp=timestamp
        )

    def _get_or_create_profile(self, user_id: int) -> UserProfile:
        """Get or create user profile."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)
        return self.user_profiles[user_id]

    def _get_or_create_baseline(self, guild_id: int) -> ServerBaseline:
        """Get or create server baseline."""
        if guild_id not in self.server_baselines:
            self.server_baselines[guild_id] = ServerBaseline(guild_id=guild_id)
        return self.server_baselines[guild_id]

    def _update_profile(self, profile: UserProfile, guild_id: int, action_type: str, timestamp: datetime):
        """Update user profile with new action."""
        profile.last_seen = timestamp
        profile.total_actions += 1
        profile.action_counts[action_type] = profile.action_counts.get(action_type, 0) + 1
        profile.action_timestamps[action_type].append(timestamp)
        
        # Update temporal patterns
        profile.typical_hours.add(timestamp.hour)
        profile.typical_days.add(timestamp.weekday())
        
        # Update peak activity hour
        if len(profile.action_timestamps[action_type]) > 10:
            hour_counts = defaultdict(int)
            for ts in profile.action_timestamps[action_type]:
                hour_counts[ts.hour] += 1
            profile.peak_activity_hour = max(hour_counts.items(), key=lambda x: x[1])[0]
        
        # Calculate average actions per hour
        time_span = (timestamp - profile.first_seen).total_seconds() / 3600  # hours
        if time_span > 0:
            profile.average_actions_per_hour = profile.total_actions / time_span
        
        # Track action sequence (last 10 actions)
        profile.action_sequences.append([action_type])
        if len(profile.action_sequences) > 10:
            profile.action_sequences = profile.action_sequences[-10:]

    def _update_baseline(self, baseline: ServerBaseline, guild_id: int):
        """Update server baseline with current data."""
        # This would typically be updated from periodic analysis
        # For now, just update timestamp
        pass

    def _track_action(self, guild_id: int, user_id: int, action_type: str, timestamp: datetime):
        """Track action for real-time analysis."""
        user_key = (guild_id, user_id)
        
        if user_key not in self.recent_actions:
            self.recent_actions[user_key] = deque(maxlen=100)
        
        self.recent_actions[user_key].append({
            'action_type': action_type,
            'timestamp': timestamp
        })
        
        if guild_id not in self.guild_recent_actions:
            self.guild_recent_actions[guild_id] = deque(maxlen=1000)
        
        self.guild_recent_actions[guild_id].append({
            'user_id': user_id,
            'action_type': action_type,
            'timestamp': timestamp
        })

    def _detect_velocity_anomaly(self, profile: UserProfile, guild_id: int, user_id: int) -> Optional[AnomalyDetection]:
        """Detect velocity anomalies (unusually fast actions)."""
        user_key = (guild_id, user_id)
        if user_key not in self.recent_actions or len(self.recent_actions[user_key]) < 5:
            return None
        
        # Get recent timestamps
        recent_actions = list(self.recent_actions[user_key])
        timestamps = [a['timestamp'] for a in recent_actions]
        
        # Use statistical detector
        velocity_data = self.detector.detect_velocity_anomaly(timestamps)
        
        if velocity_data['is_anomalous']:
            # Calculate score based on how far above threshold
            score = min(velocity_data['velocity'] / self.velocity_threshold, 1.0)
            confidence = min(velocity_data['ratio'] / 3.0, 1.0)  # 3x historical = full confidence
            
            return AnomalyDetection(
                anomaly_type=AnomalyType.VELOCITY,
                score=score,
                confidence=confidence,
                details={
                    'current_velocity': velocity_data['velocity'],
                    'historical_velocity': velocity_data['historical_velocity'],
                    'ratio': velocity_data['ratio']
                },
                user_id=user_id,
                guild_id=guild_id
            )
        
        return None

    def _detect_temporal_anomaly(
        self,
        profile: UserProfile,
        baseline: ServerBaseline,
        timestamp: datetime
    ) -> Optional[AnomalyDetection]:
        """Detect temporal anomalies (unusual timing)."""
        # Check if user is active at unusual time
        if len(profile.typical_hours) < 3:
            return None  # Not enough data
        
        current_hour = timestamp.hour
        
        # If this hour is not in typical hours and user has history
        if current_hour not in profile.typical_hours:
            # Calculate how unusual this is
            typical_hours_list = list(profile.typical_hours)
            hour_spread = max(typical_hours_list) - min(typical_hours_list)
            
            if hour_spread < 12:  # User typically active within 12-hour window
                # Find closest typical hour
                closest_hour = min(typical_hours_list, key=lambda h: abs(h - current_hour))
                hour_diff = abs(closest_hour - current_hour)
                
                # Wrap around for 24-hour clock
                hour_diff = min(hour_diff, 24 - hour_diff)
                
                score = min(hour_diff / 12.0, 1.0)  # 12 hours = max anomaly
                confidence = 0.5  # Temporal anomalies have lower confidence
                
                return AnomalyDetection(
                    anomaly_type=AnomalyType.TEMPORAL,
                    score=score,
                    confidence=confidence,
                    details={
                        'current_hour': current_hour,
                        'typical_hours': sorted(typical_hours_list),
                        'hour_diff': hour_diff
                    },
                    user_id=profile.user_id
                )
        
        return None

    def _detect_sequential_anomaly(self, profile: UserProfile, action_type: str) -> Optional[AnomalyDetection]:
        """Detect sequential anomalies (unusual action sequences)."""
        if len(profile.action_sequences) < 3:
            return None
        
        # Check for repeated same action
        recent_sequences = profile.action_sequences[-5:]
        same_action_count = sum(1 for seq in recent_sequences if seq and seq[0] == action_type)
        
        if same_action_count >= 4:  # 4 out of last 5 actions are the same
            score = 0.8
            confidence = 0.7
            
            return AnomalyDetection(
                anomaly_type=AnomalyType.SEQUENTIAL,
                score=score,
                confidence=confidence,
                details={
                    'action_type': action_type,
                    'repeat_count': same_action_count,
                    'sequence_length': len(recent_sequences)
                },
                user_id=profile.user_id
            )
        
        return None

    def _detect_new_account_anomaly(self, profile: UserProfile, action_type: str) -> Optional[AnomalyDetection]:
        """Detect anomalies from new accounts."""
        # Check if new account is performing sensitive actions
        sensitive_actions = {
            'ban', 'kick', 'channel_delete', 'role_delete', 
            'role_update', 'webhook_create', 'bot_add'
        }
        
        if action_type in sensitive_actions:
            # Calculate account age
            account_age_hours = (profile.first_seen - profile.first_seen).total_seconds() / 3600
            
            if account_age_hours < 1:  # Less than 1 hour old
                score = 0.9
                confidence = 0.95
                
                return AnomalyDetection(
                    anomaly_type=AnomalyType.NEW_ACCOUNT,
                    score=score,
                    confidence=confidence,
                    details={
                        'account_age_hours': account_age_hours,
                        'sensitive_action': action_type,
                        'total_actions': profile.total_actions
                    },
                    user_id=profile.user_id
                )
        
        return None

    def _calculate_overall_score(self, anomalies: List[AnomalyDetection]) -> float:
        """Calculate overall anomaly score from individual anomalies."""
        if not anomalies:
            return 0.0
        
        # Weighted sum based on confidence
        weighted_sum = 0.0
        total_weight = 0.0
        
        for anomaly in anomalies:
            weight = anomaly.confidence
            weighted_sum += anomaly.score * weight
            total_weight += weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        return 0.0

    def _determine_action(self, overall_score: float, anomalies: List[AnomalyDetection]) -> str:
        """Determine recommended action based on anomaly score."""
        if overall_score < 0.3:
            return "monitor"
        elif overall_score < 0.5:
            return "increased_monitoring"
        elif overall_score < 0.7:
            return "warning"
        elif overall_score < 0.9:
            return "restrict"
        else:
            return "block"

    def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Get user behavioral profile."""
        return self.user_profiles.get(user_id)

    def get_user_risk_score(self, user_id: int) -> float:
        """Get user's current risk score."""
        profile = self.user_profiles.get(user_id)
        return profile.risk_score if profile else 0.0

    def get_user_anomaly_history(self, user_id: int) -> List[AnomalyDetection]:
        """Get user's anomaly history."""
        return self.anomaly_history.get(user_id, [])

    async def periodic_baseline_update(self):
        """Periodically update server baselines."""
        for guild_id, baseline in self.server_baselines.items():
            if guild_id in self.guild_recent_actions:
                actions = list(self.guild_recent_actions[guild_id])
                
                if actions:
                    # Calculate join rate
                    join_actions = [a for a in actions if a['action_type'] == 'member_join']
                    time_span = (actions[-1]['timestamp'] - actions[0]['timestamp']).total_seconds() / 3600
                    if time_span > 0:
                        baseline.typical_join_rate = len(join_actions) / time_span
                    
                    # Calculate action distribution
                    action_counts = defaultdict(int)
                    for action in actions:
                        action_counts[action['action_type']] += 1
                    
                    total = sum(action_counts.values())
                    if total > 0:
                        baseline.action_distribution = {
                            k: v / total for k, v in action_counts.items()
                        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get analysis engine statistics."""
        return {
            'total_profiles': len(self.user_profiles),
            'total_baselines': len(self.server_baselines),
            'total_anomalies_detected': sum(len(h) for h in self.anomaly_history.values()),
            'users_with_high_risk': len([p for p in self.user_profiles.values() if p.risk_score > 0.7]),
            'average_profile_actions': sum(p.total_actions for p in self.user_profiles.values()) / len(self.user_profiles.values()) if self.user_profiles else 0
        }


# Global instance
_analysis_engine: Optional[BehavioralAnalysisEngine] = None

def get_behavioral_engine() -> BehavioralAnalysisEngine:
    """Get the global behavioral analysis engine instance."""
    global _analysis_engine
    if _analysis_engine is None:
        _analysis_engine = BehavioralAnalysisEngine()
    return _analysis_engine