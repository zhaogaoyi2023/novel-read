"""
Authentication and authorization management.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from .config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthManager:
    """Manage authentication and authorization."""
    
    def __init__(self):
        self.jwt_secret = settings.jwt_secret
        self.jwt_expire_hours = settings.jwt_expire_hours
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=self.jwt_expire_hours)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.jwt_secret, algorithm="HS256")
        
        return encoded_jwt
    
    def decode_access_token(self, token: str) -> Optional[dict]:
        """Decode a JWT access token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except JWTError:
            return None
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key."""
        return api_key == settings.api_key
    
    @staticmethod
    def hash_content(content: str) -> str:
        """Hash content for verification."""
        return hashlib.sha256(content.encode()).hexdigest()


# Global auth manager instance
auth_manager = AuthManager()
