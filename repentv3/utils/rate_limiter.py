"""
Repent - Rate Limiting System
Prevents command spam and API abuse with configurable rate limits.
"""

import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple
from datetime import datetime, timedelta
from discord import app_commands
from utils.logger import get_logger


class RateLimiter:
    """Token bucket rate limiter for command spam protection with cache layer integration."""
    
    def __init__(self, default_rate: int = 10, default_per: float = 60.0, cache_layer=None):
        """
        Initialize rate limiter.
        
        Args:
            default_rate: Default number of requests allowed
            default_per: Default time window in seconds
            cache_layer: Optional cache layer for persistence
        """
        self.default_rate = default_rate
        self.default_per = default_per
        # Track user requests: {user_id: {command_name: [(timestamp, count)]}}
        self._user_commands: Dict[int, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        # Whitelisted users bypass rate limits: {user_id: bool}
        self._whitelisted_users: Set[int] = set()
        self._lock = asyncio.Lock()
        self.cache_layer = cache_layer
        self.logger = get_logger()
    
    def add_whitelisted_user(self, user_id: int):
        """Add a user to rate limit whitelist."""
        self._whitelisted_users.add(user_id)
        # Also cache in cache layer if available
        if self.cache_layer:
            try:
                import asyncio
                asyncio.create_task(self.cache_layer.set("ratelimit_whitelist", user_id, True, ttl=3600))
            except Exception:
                pass
    
    def remove_whitelisted_user(self, user_id: int):
        """Remove a user from rate limit whitelist."""
        self._whitelisted_users.discard(user_id)
        # Also remove from cache layer if available
        if self.cache_layer:
            try:
                import asyncio
                asyncio.create_task(self.cache_layer.set("ratelimit_whitelist", user_id, False, ttl=3600))
            except Exception:
                pass
    
    def is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted from rate limits."""
        if user_id in self._whitelisted_users:
            return True
        
        # Check cache layer if available
        if self.cache_layer:
            try:
                import asyncio
                cached = asyncio.run(self.cache_layer.get("ratelimit_whitelist", user_id))
                if cached:
                    self._whitelisted_users.add(user_id)
                    return True
            except Exception:
                pass
        
        return False
    
    async def check_rate_limit(
        self, 
        user_id: int, 
        command_name: str, 
        rate: int = None, 
        per: float = None
    ) -> Tuple[bool, int]:
        """
        Check if user is within rate limits.
        
        Args:
            user_id: User ID to check
            command_name: Command being used
            rate: Custom rate limit (uses default if None)
            per: Custom time window (uses default if None)
            
        Returns:
            Tuple of (allowed, remaining_requests)
        """
        # Bypass rate limit for whitelisted users
        if self.is_whitelisted(user_id):
            return True, 999
        
        rate = rate or self.default_rate
        per = per or self.default_per
        
        async with self._lock:
            now = time.time()
            cutoff = now - per
            
            # Get user's command history
            user_commands = self._user_commands[user_id][command_name]
            
            # Remove old entries outside the time window
            self._user_commands[user_id][command_name] = [
                ts for ts in user_commands if ts > cutoff
            ]
            
            # Check if user has exceeded limit
            current_count = len(self._user_commands[user_id][command_name])
            remaining = max(0, rate - current_count)
            
            if current_count >= rate:
                # User has exceeded rate limit
                self.logger.warning(
                    f"Rate limit exceeded for user {user_id} on command {command_name}: "
                    f"{current_count}/{rate} requests in {per}s"
                )
                return False, 0
            
            # Add current request
            self._user_commands[user_id][command_name].append(now)
            return True, remaining - 1
    
    async def cleanup_old_entries(self):
        """Clean up old entries to prevent memory bloat."""
        async with self._lock:
            now = time.time()
            cutoff = now - (self.default_per * 2)  # Keep entries for 2x the default window
            
            for user_id in list(self._user_commands.keys()):
                for command_name in list(self._user_commands[user_id].keys()):
                    self._user_commands[user_id][command_name] = [
                        ts for ts in self._user_commands[user_id][command_name] 
                        if ts > cutoff
                    ]
                    
                    # Remove empty command lists
                    if not self._user_commands[user_id][command_name]:
                        del self._user_commands[user_id][command_name]
                
                # Remove users with no commands
                if not self._user_commands[user_id]:
                    del self._user_commands[user_id]


class CooldownByUser(app_commands.Cooldown):
    """Custom cooldown that applies per-user globally."""
    
    def __init__(self, rate: int, per: float):
        super().__init__(rate, per, app_commands.BucketType.user)


def rate_limit_cooldown(rate: int = 10, per: float = 60.0):
    """
    Decorator to apply rate limiting to commands.
    
    Args:
        rate: Number of requests allowed
        per: Time window in seconds
    """
    def decorator(func):
        # Add Discord.py cooldown with bucket type
        func = app_commands.checks.dynamic_cooldown(
            lambda x: CooldownByUser(rate, per)
        )(func)
        
        return func
    return decorator


# Stricter rate limits for critical commands
def strict_rate_limit(rate: int = 3, per: float = 60.0):
    """
    Decorator for strict rate limiting on critical security commands.
    
    Args:
        rate: Number of requests allowed (default: 3 per minute)
        per: Time window in seconds
    """
    return rate_limit_cooldown(rate, per)


# Moderate rate limits for moderation commands
def mod_rate_limit(rate: int = 5, per: float = 60.0):
    """
    Decorator for moderate rate limiting on moderation commands.
    
    Args:
        rate: Number of requests allowed (default: 5 per minute)
        per: Time window in seconds
    """
    return rate_limit_cooldown(rate, per)


# Global rate limiter instance
_global_rate_limiter = None
_cache_layer_instance = None


def get_global_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(cache_layer=_cache_layer_instance)
    return _global_rate_limiter


def set_cache_layer_for_rate_limiter(cache_layer):
    """Set the cache layer for the rate limiter (call during bot initialization)."""
    global _cache_layer_instance, _global_rate_limiter
    _cache_layer_instance = cache_layer
    if _global_rate_limiter is not None:
        _global_rate_limiter.cache_layer = cache_layer