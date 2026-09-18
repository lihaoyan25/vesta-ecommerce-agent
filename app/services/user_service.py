"""用户业务服务"""
from typing import Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.dao.user_dao import UserDAO
from app.utils.security import hash_password, verify_password, create_access_token, create_refresh_token


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.user_dao = UserDAO()

    def register(
        self,
        username: str,
        password: str,
        email: str,
        phone: str | None = None,
    ) -> User:
        """用户注册"""
        # 业务校验: 用户名是否存在
        if self.user_dao.get_by_username(self.db, username):
            raise HTTPException(status_code=400, detail="用户名已存在")
        # 业务校验: 邮箱是否已注册
        if self.user_dao.get_by_email(self.db, email):
            raise HTTPException(status_code=400, detail="邮箱已注册")
        # 业务校验: 手机号是否已注册
        if phone and self.user_dao.get_by_phone(self.db, phone):
            raise HTTPException(status_code=400, detail="手机号已注册")

        # 创建用户 (默认赠送1000元体验金)
        user = User(
            username=username,
            hashed_password=hash_password(password),
            email=email,
            phone=phone,
            balance=Decimal("1000.00"),
            status=1,
            role="user"
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def login(self, account: str, password: str) -> Tuple[str, str]:
        """用户登录, account 支持用户名/邮箱/手机号自动识别, 返回(access_token, refresh_token)"""
        # 依次按 用户名 -> 邮箱 -> 手机号 查找
        user = self.user_dao.get_by_username(self.db, account)
        if not user:
            user = self.user_dao.get_by_email(self.db, account)
        if not user:
            user = self.user_dao.get_by_phone(self.db, account)

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账号或密码错误",
                headers={"WWW-Authenticate": "Bearer"}
            )

        if user.status != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被封禁或注销"
            )

        access_token = create_access_token(
            subject=user.user_id,
            extra_claims={"username": user.username},
        )
        refresh_token = create_refresh_token(subject=user.user_id)
        return access_token, refresh_token

    def get_user_by_id(self, user_id: int) -> User:
        """根据ID获取用户"""
        user = self.user_dao.get_by_id(self.db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        return user

    def recharge(self, user_id: int, amount: Decimal) -> User:
        """账户充值"""
        if amount <= 0:
            raise HTTPException(status_code=400, detail="充值金额必须大于0")
        user = self.get_user_by_id(user_id)
        user.balance += amount
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_my_info(
        self,
        user_id: int,
        username: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        current_password: str | None = None,
    ) -> User:
        """更新当前用户信息; 修改邮箱/手机号属于敏感操作, 需验证当前密码"""
        user = self.get_user_by_id(user_id)

        # 敏感操作校验: 改邮箱/手机号需当前密码确认
        if (email is not None or phone is not None) and not current_password:
            raise HTTPException(status_code=400, detail="修改邮箱/手机号需要验证当前密码")
        if current_password is not None and not verify_password(current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="当前密码错误")

        if username is not None and username != user.username:
            if self.user_dao.get_by_username(self.db, username):
                raise HTTPException(status_code=400, detail="用户名已存在")
            user.username = username
        if email is not None and email != user.email:
            if self.user_dao.get_by_email(self.db, email):
                raise HTTPException(status_code=400, detail="邮箱已注册")
            user.email = email
        if phone is not None and phone != user.phone:
            if self.user_dao.get_by_phone(self.db, phone):
                raise HTTPException(status_code=400, detail="手机号已注册")
            user.phone = phone

        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str,
    ) -> User:
        """修改密码"""
        user = self.get_user_by_id(user_id)
        if not verify_password(old_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="原密码错误")
        user.hashed_password = hash_password(new_password)
        self.db.commit()
        self.db.refresh(user)
        return user

    def reset_password(self, account: str, phone: str, new_password: str) -> None:
        """忘记密码: 通过 账号(用户名或邮箱) + 手机号 验证身份后重置密码

        预留升级: 接入邮件服务后可在此增加验证码校验
        """
        # 与登录一致: 账号支持用户名或邮箱
        user = self.user_dao.get_by_username(self.db, account)
        if not user:
            user = self.user_dao.get_by_email(self.db, account)

        # 统一模糊提示, 避免暴露账号是否存在/是否绑定了手机号
        if not user or user.phone != phone:
            raise HTTPException(status_code=400, detail="账号, 手机号不匹配或未绑定手机号")

        if user.status != 1:
            raise HTTPException(status_code=403, detail="账号已被封禁或注销")

        user.hashed_password = hash_password(new_password)
        self.db.commit()
