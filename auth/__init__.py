"""
User Authentication Module
JWT-based auth with SQLite storage
Supports: username/password, QR code token login
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)

# ============================================================
# Config
# ============================================================
JWT_SECRET = secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72
QR_TOKEN_EXPIRE_SECONDS = 120

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

DB_DIR = Path("./data")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "users.db"


# ============================================================
# Database
# ============================================================
def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            last_login TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qr_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT,
            created_at REAL NOT NULL,
            used INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ============================================================
# Models
# ============================================================
class UserInfo(BaseModel):
    id: str
    username: str
    email: str = ""
    avatar: str = ""

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user: UserInfo

class QRCodeResponse(BaseModel):
    qr_id: str
    qr_url: str
    expires_in: int


# ============================================================
# Auth helpers
# ============================================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_jwt(user_id: str, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserInfo | None:
    """FastAPI dependency: extract user from JWT in Authorization header"""
    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get("auth_token")
    if not token:
        return None
    payload = decode_jwt(token)
    if not payload:
        return None
    return UserInfo(
        id=payload["sub"],
        username=payload["username"],
    )


# ============================================================
# User operations
# ============================================================

def get_user_by_username(username: str) -> dict | None:
    conn = _get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: str) -> dict | None:
    conn = _get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(username: str, password: str, email: str = "") -> dict:
    conn = _get_db()
    user_id = hashlib.sha256(f"{username}:{time.time()}".encode()).hexdigest()[:16]
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, email, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, hash_password(password), email, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("用户名已存在")
    conn.close()
    return {"id": user_id, "username": username, "email": email}

def create_qr_token() -> dict:
    """Generate a temporary QR login token"""
    token = secrets.token_urlsafe(24)
    conn = _get_db()
    conn.execute(
        "INSERT INTO qr_tokens (token, created_at) VALUES (?, ?)",
        (token, time.time()),
    )
    conn.commit()
    conn.close()
    return {
        "qr_id": token,
        "qr_url": f"/api/auth/qr-login?token={token}",
        "expires_in": QR_TOKEN_EXPIRE_SECONDS,
    }

def check_qr_token(token: str) -> str | None:
    """Check if QR token has been claimed. Returns user_id if claimed."""
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM qr_tokens WHERE token = ? AND used = 1", (token,)
    ).fetchone()
    conn.close()
    if row:
        return row["user_id"]
    return None

def claim_qr_token(token: str, user_id: str) -> bool:
    """Claim a QR token for a user"""
    conn = _get_db()
    cursor = conn.execute(
        "UPDATE qr_tokens SET user_id = ?, used = 1 WHERE token = ? AND used = 0",
        (user_id, token),
    )
    conn.commit()
    ok = cursor.rowcount > 0
    conn.close()
    return ok


# Initialize on import
init_db()
