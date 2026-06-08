"""
Repent - CSRF Protection System
Provides additional security verification for sensitive Discord interactions.
"""

import secrets
import time
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
from discord import Interaction, User


class CSRFProtection:
    """
    CSRF protection for sensitive interactions using nonces.
    Discord provides base-level security, but this adds additional verification.
    """
    
    def __init__(self, nonce_expiry_seconds: int = 300):
        """
        Initialize CSRF protection.
        
        Args:
            nonce_expiry_seconds: How long nonces remain valid
        """
        self.nonce_expiry_seconds = nonce_expiry_seconds
        # Store nonces: {nonce: (user_id, timestamp, interaction_type)}
        self._nonces: Dict[str, tuple] = {}
        self._cleanup_threshold = 1000  # Clean up after this many nonces
    
    def generate_nonce(self, user_id: int, interaction_type: str = "default") -> str:
        """
        Generate a security nonce for an interaction.
        
        Args:
            user_id: User ID requesting the nonce
            interaction_type: Type of interaction (for categorization)
            
        Returns:
            Generated nonce string
        """
        nonce = secrets.token_urlsafe(32)
        timestamp = time.time()
        
        self._nonces[nonce] = (user_id, timestamp, interaction_type)
        
        # Periodic cleanup of old nonces
        if len(self._nonces) > self._cleanup_threshold:
            self._cleanup_old_nonces()
        
        return nonce
    
    def verify_nonce(self, nonce: str, user_id: int, interaction_type: str = None) -> bool:
        """
        Verify a nonce is valid for the user.
        
        Args:
            nonce: Nonce to verify
            user_id: User ID claiming the nonce
            interaction_type: Expected interaction type (optional)
            
        Returns:
            True if nonce is valid, False otherwise
        """
        if nonce not in self._nonces:
            return False
        
        stored_user_id, timestamp, stored_type = self._nonces[nonce]
        
        # Verify user ID matches
        if stored_user_id != user_id:
            return False
        
        # Verify interaction type if specified
        if interaction_type and stored_type != interaction_type:
            return False
        
        # Verify nonce hasn't expired
        if time.time() - timestamp > self.nonce_expiry_seconds:
            del self._nonces[nonce]
            return False
        
        # Remove used nonce to prevent replay attacks
        del self._nonces[nonce]
        return True
    
    def _cleanup_old_nonces(self):
        """Clean up expired nonces."""
        current_time = time.time()
        expired_nonces = [
            nonce for nonce, (_, timestamp, _) in self._nonces.items()
            if current_time - timestamp > self.nonce_expiry_seconds
        ]
        
        for nonce in expired_nonces:
            del self._nonces[nonce]
    
    def verify_interaction_source(self, interaction: Interaction) -> bool:
        """
        Verify the interaction source is legitimate.
        
        Args:
            interaction: Discord interaction to verify
            
        Returns:
            True if interaction appears legitimate
        """
        # Basic verification checks
        if not interaction.guild_id and not interaction.user:
            return False
        
        # Check for suspicious patterns
        user = interaction.user
        if user.bot and user.id != interaction.application_id:
            # Bot interactions from other bots are suspicious
            return False
        
        # Check account age (very new accounts might be suspicious)
        if user.created_at > datetime.now(timezone.utc) - timedelta(days=1):
            # Account created very recently - flag for review
            return True  # Still allow, but could log warning
        
        return True
    
    def generate_confirmation_token(self, user_id: int, action: str) -> str:
        """
        Generate a confirmation token for sensitive actions.
        
        Args:
            user_id: User ID requesting the token
            action: Description of the action being confirmed
            
        Returns:
            Confirmation token
        """
        token_data = f"{user_id}:{action}:{time.time()}"
        token = secrets.token_hex(16)
        self._nonces[token] = (user_id, time.time(), f"confirm:{action}")
        return token
    
    def verify_confirmation_token(self, token: str, user_id: int, action: str) -> bool:
        """
        Verify a confirmation token.
        
        Args:
            token: Token to verify
            user_id: User ID claiming the token
            action: Action that was confirmed
            
        Returns:
            True if token is valid
        """
        if token not in self._nonces:
            return False
        
        stored_user_id, timestamp, stored_action = self._nonces[token]
        
        # Verify user ID and action match
        if stored_user_id != user_id or not stored_action.endswith(f":{action}"):
            return False
        
        # Verify token hasn't expired (confirmation tokens expire faster)
        if time.time() - timestamp > 60:  # 1 minute for confirmations
            del self._nonces[token]
            return False
        
        # Remove used token
        del self._nonces[token]
        return True


# Global CSRF protection instance
_csrf_protection = CSRFProtection()


def get_csrf_protection() -> CSRFProtection:
    """Get the global CSRF protection instance."""
    return _csrf_protection


def require_confirmation(action_description: str = "sensitive action"):
    """
    Decorator for commands that require user confirmation.
    
    Args:
        action_description: Description of the action for confirmation
    """
    def decorator(func):
        async def wrapper(interaction: Interaction, *args, **kwargs):
            csrf = get_csrf_protection()
            
            # Verify interaction source
            if not csrf.verify_interaction_source(interaction):
                await interaction.response.send_message(
                    "Security verification failed.",
                    ephemeral=True
                )
                return
            
            # Store confirmation requirement in interaction metadata
            # This would be used by a confirmation UI system
            # For now, we'll proceed with the original function
            return await func(interaction, *args, **kwargs)
        
        return wrapper
    return decorator