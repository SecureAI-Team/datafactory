"""Authentication service - JWT token management"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from ..models.user import User, UserSession

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))


class AuthService:
    """认证服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== Password Operations ====================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    # ==================== Token Operations ====================
    
    @staticmethod
    def create_access_token(user_id: int, username: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
        """Create a new access token"""
        if expires_delta is None:
            expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def create_refresh_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
        """Create a new refresh token"""
        if expires_delta is None:
            expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
            "jti": secrets.token_urlsafe(16)  # Unique token ID
        }
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate a token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    # ==================== User Authentication ====================
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password"""
        user = self.db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        return user
    
    def login(self, username: str, password: str, device_info: dict = None, ip_address: str = None) -> Optional[Tuple[str, str, User]]:
        """
        Login a user and return access token, refresh token, and user
        Returns None if authentication fails
        """
        user = self.authenticate_user(username, password)
        if not user:
            return None
        
        # Create tokens
        access_token = self.create_access_token(user.id, user.username, user.role)
        refresh_token = self.create_refresh_token(user.id)
        
        # Store session
        session = UserSession(
            user_id=user.id,
            token_hash=self.hash_token(refresh_token),
            device_info=device_info or {},
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        self.db.add(session)
        
        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        return access_token, refresh_token, user
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """
        Refresh an access token using a refresh token
        Returns new access_token and refresh_token, or None if invalid
        """
        payload = self.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = int(payload.get("sub"))
        token_hash = self.hash_token(refresh_token)
        
        # Verify session exists and is valid
        session = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.token_hash == token_hash,
            UserSession.expires_at > datetime.now(timezone.utc)
        ).first()
        
        if not session:
            return None
        
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return None
        
        # Create new tokens
        new_access_token = self.create_access_token(user.id, user.username, user.role)
        new_refresh_token = self.create_refresh_token(user.id)
        
        # Update session
        session.token_hash = self.hash_token(new_refresh_token)
        session.expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        self.db.commit()
        
        return new_access_token, new_refresh_token
    
    def logout(self, refresh_token: str) -> bool:
        """Logout by invalidating the refresh token"""
        token_hash = self.hash_token(refresh_token)
        
        session = self.db.query(UserSession).filter(
            UserSession.token_hash == token_hash
        ).first()
        
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        
        return False
    
    def logout_all(self, user_id: int) -> int:
        """Logout all sessions for a user"""
        count = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).delete()
        self.db.commit()
        return count
    
    # ==================== User Management ====================
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        display_name: str = None,
        role: str = "user",
        department: str = None
    ) -> User:
        """Create a new user"""
        user = User(
            username=username,
            email=email,
            password_hash=self.hash_password(password),
            display_name=display_name or username,
            role=role,
            department=department,
            is_active=True
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Update user password"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        if not self.verify_password(old_password, user.password_hash):
            return False
        
        user.password_hash = self.hash_password(new_password)
        self.db.commit()
        
        # Invalidate all sessions except current
        self.logout_all(user_id)
        
        return True

