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
    """Token bucket rate limiter for command spam protection."""
    
    def __init__(self, default_rate: int = 10, default_per: float = 60.0):
        """
        Initialize rate limiter.
        
        Args:
            default_rate: Default number of requests allowed
            default_per: Default time window in seconds
        """
        self.default_rate = default_rate
        self.default_per = default_per
        # Track user requests: {user_id: {command_name: [(timestamp, count)]}}
        self._user_commands: Dict[int, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self._lock = asyncio.Lock()
        self.logger = get_logger()
    
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
        # Add Discord.py cooldown
        func = app_commands.checks.dynamic_cooldown(lambda x: CooldownByUser(rate, per))(func)
        
        return func
    return decorator


# Global rate limiter instance
_global_rate_limiter = RateLimiter()


def get_global_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _global_rate_limiter