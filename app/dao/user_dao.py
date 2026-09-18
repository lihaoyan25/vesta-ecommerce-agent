"""用户数据访问层"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User

class UserDAO:
    def get_by_username(self, db: Session, username: str, exclude_user_id: Optional[int] = None) -> Optional[User]:
        """根据用户名获取用户, 可排除指定用户(用于查重排除自身)"""
        query = db.query(User).filter(User.username == username)
        if exclude_user_id is not None:
            query = query.filter(User.user_id != exclude_user_id)
        return query.first()

    def get_by_email(self, db: Session, email: str, exclude_user_id: Optional[int] = None) -> Optional[User]:
        """根据邮箱获取用户, 可排除指定用户(用于查重排除自身)"""
        query = db.query(User).filter(User.email == email)
        if exclude_user_id is not None:
            query = query.filter(User.user_id != exclude_user_id)
        return query.first()

    def get_by_phone(self, db: Session, phone: str, exclude_user_id: Optional[int] = None) -> Optional[User]:
        """根据手机号获取用户, 可排除指定用户(用于查重排除自身)"""
        query = db.query(User).filter(User.phone == phone)
        if exclude_user_id is not None:
            query = query.filter(User.user_id != exclude_user_id)
        return query.first()

    def get_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        return db.query(User).filter(User.user_id == user_id).first()
