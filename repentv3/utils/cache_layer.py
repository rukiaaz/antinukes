"""
Repent - Caching Layer
In-memory caching for frequently accessed data to reduce database load.
"""

import time
import asyncio
from typing import Any, Optional, Dict
from datetime import datetime, timedelta


class CacheEntry:
    """Represents a single cache entry with TTL."""
    
    def __init__(self, value: Any, ttl: int = 300):
        """
        Initialize a cache entry.
        
        Args:
            value: Value to cache
            ttl: Time to live in seconds
        """
        self.value = value
        self.expires_at = time.time() + ttl
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() > self.expires_at
    
    def refresh(self, ttl: int = None):
        """Refresh the cache entry TTL."""
        self.expires_at = time.time() + (ttl or self.ttl)


class CacheLayer:
    """In-memory cache layer with automatic expiration."""
    
    def __init__(self, default_ttl: int = 300, cleanup_interval: int = 60):
        """
        Initialize the cache layer.
        
        Args:
            default_ttl: Default time to live for cache entries
            cleanup_interval: Interval between cleanup runs
        """
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None
    
    async def start(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def _cleanup_loop(self):
        """Periodically clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Cache cleanup error: {e}")
    
    async def _cleanup_expired(self):
        """Remove expired cache entries."""
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def _generate_key(self, prefix: str, *args) -> str:
        """Generate a cache key from components."""
        key_parts = [prefix] + [str(arg) for arg in args]
        return ":".join(key_parts)
    
    async def get(self, prefix: str, *args) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            prefix: Cache key prefix
            *args: Additional key components
            
        Returns:
            Cached value or None if not found/expired
        """
        key = self._generate_key(prefix, *args)
        
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    return entry.value
                else:
                    del self._cache[key]
        
        return None
    
    async def set(self, prefix: str, value: Any, *args, ttl: int = None) -> None:
        """
        Set a value in the cache.
        
        Args:
            prefix: Cache key prefix
            value: Value to cache
            *args: Additional key components
            ttl: Custom TTL (uses default if not specified)
        """
        key = self._generate_key(prefix, *args)
        ttl = ttl or self.default_ttl
        
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl)
    
    async def delete(self, prefix: str, *args) -> None:
        """
        Delete a value from the cache.
        
        Args:
            prefix: Cache key prefix
            *args: Additional key components
        """
        key = self._generate_key(prefix, *args)
        
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    async def clear_pattern(self, pattern: str) -> None:
        """
        Clear all cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (simple substring match)
        """
        async with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if pattern in key
            ]
            for key in keys_to_delete:
                del self._cache[key]
    
    async def clear_all(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_entries": len(self._cache),
            "default_ttl": self.default_ttl,
            "cleanup_interval": self.cleanup_interval
        }


# Global cache instance
_cache_layer: Optional[CacheLayer] = None


def get_cache_layer() -> CacheLayer:
    """Get the global cache layer instance."""
    global _cache_layer
    if _cache_layer is None:
        _cache_layer = CacheLayer()
    return _cache_layer