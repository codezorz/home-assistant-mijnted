import jwt
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .list_util import ListUtil

_LOGGER = logging.getLogger(__name__)


class JwtUtil:
    """Utility class for JWT token operations."""
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """Decode a JWT token without verifying signature.
        
        Args:
            token: JWT token string to decode
            
        Returns:
            Decoded payload dictionary, or None if decoding fails
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception as err:
            _LOGGER.debug("Failed to decode JWT token: %s", err)
            return None
    
    @staticmethod
    def get_first_claim_value(claim_value: Any, default: Optional[str] = None) -> Optional[str]:
        """Get first value from a claim, handling list, string, or other types.
        
        Args:
            claim_value: Claim value (can be list, string, or other)
            default: Optional default value if claim is empty or invalid
            
        Returns:
            First value as string, or default if not available
        """
        if not claim_value:
            return default
        
        if isinstance(claim_value, str):
            return claim_value
        
        if isinstance(claim_value, list):
            first_item = ListUtil.get_first_item(claim_value)
            if first_item is not None:
                return str(first_item)
        
        return default
    
    @staticmethod
    def is_token_expired(token: str) -> bool:
        """Check if a JWT token is expired.
        
        Args:
            token: JWT token string to check
            
        Returns:
            True if token is expired or invalid, False if valid
        """
        payload = JwtUtil.decode_token(token)
        if not payload:
            return True
        
        exp = payload.get("exp")
        if exp:
            exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
            return exp_time <= datetime.now(timezone.utc)
        return True

