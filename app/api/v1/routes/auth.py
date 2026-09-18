"""认证路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.user_service import UserService
from app.api.v1.schemas.user import UserCreate, UserResponse, ForgotPasswordRequest
from app.api.v1.schemas.common import TokenResponse, RefreshTokenRequest, success_response
from app.api.deps import get_current_user
from app.models.user import User
from app.utils.security import verify_refresh_token, create_access_token

router = APIRouter()


@router.post("/register")
async def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    """用户注册"""
    user_service = UserService(db)
    user = await run_in_threadpool(
        user_service.register,
        user_in.username,
        user_in.password,
        user_in.email,
        user_in.phone,
    )
    return success_response(data=UserResponse.model_validate(user).model_dump())


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """用户登录"""
    user_service = UserService(db)
    access_token, refresh_token = await run_in_threadpool(
        user_service.login,
        form_data.username,
        form_data.password,
    )
    return success_response(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        ).model_dump()
    )


@router.post("/refresh")
async def refresh_token(
    refresh_in: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """刷新访问令牌"""
    payload = verify_refresh_token(refresh_in.refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期")

    user_id = int(payload.get("sub"))
    user_service = UserService(db)
    user = await run_in_threadpool(user_service.get_user_by_id, user_id)

    if user.status != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被封禁或注销")

    new_access_token = create_access_token(
        subject=user_id,
        extra_claims={"username": user.username},
    )
    return success_response(
        data=TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_in.refresh_token,
        ).model_dump()
    )


@router.post("/forgot-password")
async def forgot_password(
    reset_in: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """忘记密码: 通过 账号(用户名或邮箱) + 手机号 验证身份后重置密码(无需登录)"""
    user_service = UserService(db)
    await run_in_threadpool(
        user_service.reset_password,
        reset_in.account,
        reset_in.phone,
        reset_in.new_password,
    )
    return success_response(message="密码重置成功, 请使用新密码登录")


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取当前登录用户信息"""
    return success_response(data=UserResponse.model_validate(current_user).model_dump())
