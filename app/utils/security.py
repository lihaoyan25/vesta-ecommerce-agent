"""安全工具模块: 密码加密 & JWT令牌"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt, ExpiredSignatureError
from passlib.context import CryptContext
from app.config import settings

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 密码相关
def hash_password(password: str) -> str:
    """密码哈希"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

# JWT相关
def create_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """创建访问令牌"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "sub": str(subject),
        "type": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(subject: str | Any) -> str:
    """创建刷新令牌"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "sub": str(subject),
        "type": "refresh",
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解码令牌(基础版)"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except ExpiredSignatureError:
        return None
    except JWTError:
        return None

def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """验证访问令牌"""
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    return payload

def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """验证刷新令牌"""
    payload = decode_token(token)
    if payload is None or payload.get("type") != "refresh":
        return None
    return payload
