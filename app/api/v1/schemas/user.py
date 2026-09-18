"""用户Schema"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
import re

PHONE_PATTERN = r'^1[3-9]\d{9}$'


def _validate_phone(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if not re.match(PHONE_PATTERN, v):
        raise ValueError("手机号格式不正确")
    return v


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v[0].isalpha():
            raise ValueError("用户名必须以字母开头")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("用户名只能包含字母、数字、下划线")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=20, description="密码")
    password_confirm: str = Field(..., description="确认密码")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("密码必须包含大写字母")
        if not any(c.islower() for c in v):
            raise ValueError("密码必须包含小写字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if 'password' in info.data and v != info.data['password']:
            raise ValueError("两次密码输入不一致")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: EmailStr
    phone: str | None
    balance: Decimal
    role: str
    created_at: datetime | None


class UserUpdate(BaseModel):
    """更新个人资料: 改邮箱/手机号需提供当前密码确认; 改用户名无需"""
    username: Optional[str] = Field(None, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    current_password: Optional[str] = Field(None, description="当前密码, 修改邮箱/手机号时必填")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)


class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=20)


class ForgotPasswordRequest(BaseModel):
    """忘记密码: 通过 账号(用户名或邮箱) + 手机号 验证身份后重置密码

    预留升级: 后续接入邮件服务时可在此模型上扩展验证码字段
    """
    account: str = Field(..., description="账号: 用户名或邮箱")
    phone: str = Field(..., description="注册时绑定的手机号")
    new_password: str = Field(..., min_length=8, max_length=20, description="新密码")
    password_confirm: str = Field(..., description="确认新密码")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        result = _validate_phone(v)
        if result is None:
            raise ValueError("手机号格式不正确")
        return result

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("密码必须包含大写字母")
        if not any(c.islower() for c in v):
            raise ValueError("密码必须包含小写字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError("两次密码输入不一致")
        return v


class RechargeRequest(BaseModel):
    amount: Decimal = Field(gt=0, description="充值金额, 必须大于0")
