"""
Auth API Routes
"""
from __future__ import annotations

import logging
import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    QRCodeResponse,
    UserInfo,
    create_jwt,
    create_user,
    get_user_by_username,
    get_user_by_id,
    verify_password,
    create_qr_token,
    check_qr_token,
    claim_qr_token,
    get_current_user,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest):
    """Register a new user"""
    if len(body.username) < 3 or len(body.username) > 32:
        raise HTTPException(422, "用户名需要3-32个字符")
    if len(body.password) < 6:
        raise HTTPException(422, "密码至少6个字符")
    if not body.username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(422, "用户名只能包含字母、数字、下划线和横线")
    
    try:
        user = create_user(body.username, body.password, body.email)
    except ValueError as e:
        raise HTTPException(409, str(e))
    
    token = create_jwt(user["id"], user["username"])
    return AuthResponse(
        token=token,
        user=UserInfo(id=user["id"], username=user["username"], email=user.get("email", "")),
    )


@auth_router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    """Login with username and password"""
    user = get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    
    token = create_jwt(user["id"], user["username"])
    return AuthResponse(
        token=token,
        user=UserInfo(id=user["id"], username=user["username"], email=user.get("email", "")),
    )


@auth_router.get("/me")
async def me(request = None):
    """Get current user from JWT in Authorization header"""
    from fastapi import Request
    if not request:
        return {"authenticated": False, "user": None}
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        from auth import decode_jwt, get_user_by_id
        payload = decode_jwt(token)
        if payload:
            user = get_user_by_id(payload["sub"])
            if user:
                return {"authenticated": True, "user": {"id": user["id"], "username": user["username"], "email": user.get("email", "")}}
    return {"authenticated": False, "user": None}


@auth_router.get("/qr/generate", response_model=QRCodeResponse)
async def generate_qr():
    """Generate a QR code login token"""
    qr = create_qr_token()
    return QRCodeResponse(**qr)


@auth_router.get("/qr/check")
async def check_qr(token: str = Query(...)):
    """Check if QR code has been scanned and claimed"""
    user_id = check_qr_token(token)
    if user_id:
        user = get_user_by_id(user_id)
        if user:
            jwt_token = create_jwt(user["id"], user["username"])
            return {
                "status": "claimed",
                "token": jwt_token,
                "user": {"id": user["id"], "username": user["username"]},
            }
    return {"status": "waiting"}


@auth_router.post("/qr/claim")
async def claim_qr(token: str = Query(...), user: dict = None):
    """Claim a QR code (called after user scans and confirms)"""
    # In a real app, this would be called by the mobile app
    # For web, we use the simple check approach
    return {"status": "ok"}
