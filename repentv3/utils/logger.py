"""
Repent - Logging Infrastructure
Provides structured logging for debugging, security monitoring, and operational insights.
"""

import logging
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path


class RepentLogger:
    """Centralized logging system for the Repent bot."""
    
    def __init__(self, name: str = "Repent", log_level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup console and file handlers."""
        # Console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for errors and critical events
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            error_handler = logging.FileHandler(log_dir / "error.log")
            error_handler.setLevel(logging.ERROR)
            error_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            error_handler.setFormatter(error_formatter)
            self.logger.addHandler(error_handler)
            
            # Security log for antinuke events
            security_handler = logging.FileHandler(log_dir / "security.log")
            security_handler.setLevel(logging.WARNING)
            security_formatter = logging.Formatter(
                '%(asctime)s - SECURITY - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            security_handler.setFormatter(security_formatter)
            self.logger.addHandler(security_handler)
        except Exception as e:
            self.logger.error(f"Failed to setup file handlers: {e}")
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message."""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log critical message."""
        self.logger.critical(message, exc_info=exc_info, extra=kwargs)
    
    def security(self, event_type: str, details: str, guild_id: int = None, user_id: int = None):
        """Log security event with structured format."""
        message = f"EVENT: {event_type} | DETAILS: {details}"
        if guild_id:
            message += f" | GUILD: {guild_id}"
        if user_id:
            message += f" | USER: {user_id}"
        self.logger.warning(message)
    
    def antinuke_trigger(self, action: str, guild_id: int, user_id: int, punishment: str):
        """Log antinuke trigger for security monitoring."""
        self.security(
            "ANTINUKE_TRIGGER",
            f"Action: {action}, Punishment: {punishment}",
            guild_id=guild_id,
            user_id=user_id
        )
    
    def command_error(self, command: str, user_id: int, error: str):
        """Log command error."""
        self.error(f"Command error: {command} by user {user_id}: {error}")
    
    def database_error(self, operation: str, error: str):
        """Log database operation error."""
        self.error(f"Database error during {operation}: {error}")
    
    def webhook_event(self, event_type: str, guild_id: int, details: str):
        """Log webhook-related security event."""
        self.security(
            f"WEBHOOK_{event_type}",
            details,
            guild_id=guild_id
        )
    
    def anomaly_detected(self, guild_id: int, user_id: int, score: float, anomaly_types: list):
        """Log anomaly detection event."""
        self.security(
            "ANOMALY_DETECTED",
            f"Score: {score:.2f}, Types: {', '.join(anomaly_types)}",
            guild_id=guild_id,
            user_id=user_id
        )


# Global logger instance
logger = RepentLogger()


def get_logger() -> RepentLogger:
    """Get the global logger instance."""
    return logger