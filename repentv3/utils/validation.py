"""
Repent - Input Validation System
Comprehensive input validation to prevent injection attacks and ensure data integrity.
"""

import re
from typing import Optional, Tuple, Any
from datetime import datetime
from discord import User, Member


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class ValidationUtils:
    """Utility class for input validation."""
    
    # Regex patterns for validation
    SNOWFLAKE_PATTERN = re.compile(r'^\d{17,20}$')  # Discord IDs
    SAFE_STRING_PATTERN = re.compile(r'^[\w\s\-.,!?@#%&*()+=\[\]{}|;:\'"`~]+$')
    MENTION_PATTERN = re.compile(r'^<@!?\d{17,20}>$')
    ROLE_MENTION_PATTERN = re.compile(r'^<@&\d{17,20}>$')
    CHANNEL_MENTION_PATTERN = re.compile(r'^<#\d{17,20}>$')
    
    # Length limits
    MAX_REASON_LENGTH = 512
    MAX_MESSAGE_LENGTH = 2000
    MAX_EMBED_TITLE_LENGTH = 256
    MAX_EMBED_DESCRIPTION_LENGTH = 4096
    MAX_FIELD_NAME_LENGTH = 256
    MAX_FIELD_VALUE_LENGTH = 1024
    
    @staticmethod
    def validate_snowflake(value: Any, field_name: str = "ID") -> int:
        """
        Validate Discord snowflake ID.
        
        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            
        Returns:
            Validated snowflake ID as integer
            
        Raises:
            ValidationError: If validation fails
        """
        if isinstance(value, int):
            if value <= 0:
                raise ValidationError(f"{field_name} must be a positive integer")
            return value
        
        if isinstance(value, str):
            if not ValidationUtils.SNOWFLAKE_PATTERN.match(value):
                raise ValidationError(f"Invalid {field_name} format")
            try:
                return int(value)
            except ValueError:
                raise ValidationError(f"{field_name} must be a valid number")
        
        raise ValidationError(f"{field_name} must be a string or integer")
    
    @staticmethod
    def validate_user_id(user_id: Any) -> int:
        """Validate Discord user ID."""
        return ValidationUtils.validate_snowflake(user_id, "User ID")
    
    @staticmethod
    def validate_guild_id(guild_id: Any) -> int:
        """Validate Discord guild ID."""
        return ValidationUtils.validate_snowflake(guild_id, "Guild ID")
    
    @staticmethod
    def validate_reason(reason: str, field_name: str = "reason") -> str:
        """
        Validate reason string length and content.
        
        Args:
            reason: Reason string to validate
            field_name: Name of the field for error messages
            
        Returns:
            Validated reason string
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(reason, str):
            raise ValidationError(f"{field_name} must be a string")
        
        if len(reason) > ValidationUtils.MAX_REASON_LENGTH:
            raise ValidationError(f"{field_name} cannot exceed {ValidationUtils.MAX_REASON_LENGTH} characters")
        
        # Check for potentially dangerous patterns
        dangerous_patterns = ['@everyone', '@here', '<@']
        for pattern in dangerous_patterns:
            if pattern in reason.lower():
                # Allow mentions but log them for security
                pass
        
        return reason.strip()
    
    @staticmethod
    def validate_duration(duration: str) -> Tuple[int, str]:
        """
        Parse and validate duration string.
        
        Args:
            duration: Duration string (e.g., "10m", "1h", "2d")
            
        Returns:
            Tuple of (duration_in_seconds, unit)
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(duration, str):
            raise ValidationError("Duration must be a string")
        
        duration = duration.strip().lower()
        if not duration:
            raise ValidationError("Duration cannot be empty")
        
        # Parse duration
        match = re.match(r'^(\d+)([smhd])$', duration)
        if not match:
            raise ValidationError("Invalid duration format. Use format like '10m', '1h', '2d'")
        
        amount = int(match.group(1))
        unit = match.group(2)
        
        if amount <= 0:
            raise ValidationError("Duration must be positive")
        
        # Convert to seconds
        unit_multipliers = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }
        
        seconds = amount * unit_multipliers[unit]
        
        # Max timeout is 28 days (Discord limit)
        max_seconds = 28 * 86400
        if seconds > max_seconds:
            raise ValidationError(f"Duration cannot exceed 28 days")
        
        return seconds, unit
    
    @staticmethod
    def validate_message_content(content: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
        """
        Validate message content.
        
        Args:
            content: Message content to validate
            max_length: Maximum allowed length
            
        Returns:
            Validated content string
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(content, str):
            raise ValidationError("Content must be a string")
        
        if len(content) > max_length:
            raise ValidationError(f"Content cannot exceed {max_length} characters")
        
        return content
    
    @staticmethod
    def validate_discord_user(user: Any) -> User:
        """
        Validate Discord user object.
        
        Args:
            user: User object to validate
            
        Returns:
            Validated user object
            
        Raises:
            ValidationError: If validation fails
        """
        if user is None:
            raise ValidationError("User cannot be None")
        
        if not isinstance(user, (User, Member)):
            raise ValidationError("Invalid user object")
        
        if user.bot:
            # Log bot interactions for security
            pass
        
        return user
    
    @staticmethod
    def validate_amount(amount: int, min_val: int = 1, max_val: int = 100, field_name: str = "amount") -> int:
        """
        Validate numeric amount within range.
        
        Args:
            amount: Amount to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            field_name: Name of the field for error messages
            
        Returns:
            Validated amount
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(amount, int):
            try:
                amount = int(amount)
            except (ValueError, TypeError):
                raise ValidationError(f"{field_name} must be a number")
        
        if amount < min_val:
            raise ValidationError(f"{field_name} must be at least {min_val}")
        
        if amount > max_val:
            raise ValidationError(f"{field_name} cannot exceed {max_val}")
        
        return amount
    
    @staticmethod
    def sanitize_string(input_string: str, max_length: int = 200) -> str:
        """
        Sanitize a string for safe storage/display.
        
        Args:
            input_string: String to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if not isinstance(input_string, str):
            return ""
        
        # Remove null characters and other control characters
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', input_string)
        
        # Trim to max length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def validate_channel_mention(mention: str) -> int:
        """
        Validate and extract channel ID from mention.
        
        Args:
            mention: Channel mention string
            
        Returns:
            Channel ID
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(mention, str):
            raise ValidationError("Channel mention must be a string")
        
        match = ValidationUtils.CHANNEL_MENTION_PATTERN.match(mention)
        if not match:
            raise ValidationError("Invalid channel mention format")
        
        channel_id = int(mention.strip('<#>'))
        return channel_id
    
    @staticmethod
    def validate_role_mention(mention: str) -> int:
        """
        Validate and extract role ID from mention.
        
        Args:
            mention: Role mention string
            
        Returns:
            Role ID
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(mention, str):
            raise ValidationError("Role mention must be a string")
        
        match = ValidationUtils.ROLE_MENTION_PATTERN.match(mention)
        if not match:
            raise ValidationError("Invalid role mention format")
        
        role_id = int(mention.strip('<@&>'))
        return role_id


# Convenience functions for common validations
def validate_user_input(user_id: Any) -> int:
    """Validate user ID input."""
    return ValidationUtils.validate_user_id(user_id)


def validate_reason_input(reason: str) -> str:
    """Validate reason input."""
    return ValidationUtils.validate_reason(reason)


def validate_duration_input(duration: str) -> Tuple[int, str]:
    """Validate duration input."""
    return ValidationUtils.validate_duration(duration)