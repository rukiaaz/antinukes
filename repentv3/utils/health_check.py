"""
Repent - Health Check System
Provides health monitoring and status reporting for the bot.
"""

import asyncio
import time
import psutil
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from discord.ext import commands


class HealthChecker:
    """Monitors bot health and provides status reports."""
    
    def __init__(self, bot: commands.Bot):
        """
        Initialize health checker.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self._start_time = time.time()
        self._last_health_check = None
        self._health_status = "unknown"
    
    async def check_discord_connection(self) -> Dict[str, Any]:
        """Check Discord connection status."""
        if not self.bot.is_ready():
            return {
                "status": "disconnected",
                "latency": None,
                "guilds": 0
            }
        
        return {
            "status": "connected",
            "latency": round(self.bot.latency * 1000, 2),  # Convert to ms
            "guilds": len(self.bot.guilds),
            "users": sum(g.member_count for g in self.bot.guilds)
        }
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            from database import _get_db, _release_db
            start_time = time.time()
            db = await _get_db()
            
            # Simple query to test connection
            await db.execute("SELECT 1")
            await _release_db(db)
            
            query_time = (time.time() - start_time) * 1000  # Convert to ms
            
            return {
                "status": "healthy",
                "query_time_ms": round(query_time, 2)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            process = psutil.Process()
            
            return {
                "status": "healthy",
                "cpu_percent": process.cpu_percent(),
                "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                "threads": process.num_threads(),
                "uptime_seconds": round(time.time() - self._start_time, 2)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_cache_layer(self) -> Dict[str, Any]:
        """Check cache layer status."""
        try:
            from utils.cache_layer import get_cache_layer
            cache = get_cache_layer()
            stats = cache.get_stats()
            
            return {
                "status": "healthy",
                "cached_entries": stats["total_entries"],
                "default_ttl": stats["default_ttl"]
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get_health_report(self) -> Dict[str, Any]:
        """
        Get comprehensive health report.
        
        Returns:
            Dictionary containing all health metrics
        """
        self._last_health_check = datetime.now(timezone.utc).isoformat()
        
        # Run all checks concurrently
        discord_status, db_status, system_status, cache_status = await asyncio.gather(
            self.check_discord_connection(),
            self.check_database(),
            asyncio.to_thread(self.check_system_resources),
            self.check_cache_layer(),
            return_exceptions=True
        )
        
        # Determine overall health status
        overall_status = "healthy"
        if isinstance(discord_status, Exception) or discord_status["status"] != "connected":
            overall_status = "degraded"
        if isinstance(db_status, Exception) or db_status["status"] != "healthy":
            overall_status = "unhealthy"
        
        self._health_status = overall_status
        
        return {
            "overall_status": overall_status,
            "timestamp": self._last_health_check,
            "discord": discord_status if not isinstance(discord_status, Exception) else {"status": "error", "error": str(discord_status)},
            "database": db_status if not isinstance(db_status, Exception) else {"status": "error", "error": str(db_status)},
            "system": system_status if not isinstance(system_status, Exception) else {"status": "error", "error": str(system_status)},
            "cache": cache_status if not isinstance(cache_status, Exception) else {"status": "error", "error": str(cache_status)}
        }
    
    def get_uptime(self) -> str:
        """Get bot uptime as formatted string."""
        uptime_seconds = time.time() - self._start_time
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker(bot: commands.Bot = None) -> HealthChecker:
    """Get or create the global health checker instance."""
    global _health_checker
    if _health_checker is None and bot is not None:
        _health_checker = HealthChecker(bot)
    return _health_checker