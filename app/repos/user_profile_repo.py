#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : user_profile_repo.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    UserProfile Repository（从 AKS user_profile_repo 迁入，
    新增 role / last_login_at / 禁用状态语义；avatar 方法保留待 Phase 3 使用）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import config
from app.models import UserProfile

# status 取值
STATUS_ACTIVE = 0
STATUS_DISABLED = 1


class UserProfileRepository:
    """UserProfile Repository"""

    def get_by_user_id(self, session: Session, user_id: str) -> Optional[UserProfile]:
        """按 user_id 查询（未删除）"""
        try:
            return (
                session.query(UserProfile)
                .filter(
                    UserProfile.user_id == user_id,
                    UserProfile.deleted == 0,
                )
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"查询用户档案失败: user_id={user_id}, error={e}")
            return None

    def get_or_create(
        self,
        session: Session,
        user_id: str,
        nickname: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> UserProfile:
        """获取用户档案，不存在则建档（默认角色取配置）"""
        profile = self.get_by_user_id(session, user_id)
        if profile is not None:
            return profile

        now = datetime.now()
        profile = UserProfile(
            user_id=user_id,
            nickname=nickname,
            role=config.get_default_role(),
            custom_data=custom_data,
            creator=user_id,
            updater=user_id,
            create_time=now,
            update_time=now,
            deleted=0,
            status=STATUS_ACTIVE,
        )
        try:
            session.add(profile)
            session.commit()
            session.refresh(profile)
            logger.info(f"成功初始化用户档案: user_id={user_id}")
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"初始化用户档案失败: user_id={user_id}, error={e}")
            # 并发保护：再次尝试查询
            existing = self.get_by_user_id(session, user_id)
            if existing:
                return existing
            raise

    def update_login(
        self,
        session: Session,
        user_id: str,
        method: str,
        nickname: Optional[str] = None,
        gender: Optional[int] = None,
    ) -> None:
        """
        登录成功后更新最近登录时间/方式；首次登录补全昵称（尊重用户自定义）

        gender 与昵称语义相反：属身份属性，OA 给值即刷新（is not None 判断，0=未知也是有效值）。
        """
        profile = self.get_or_create(session, user_id)
        try:
            profile.last_login_at = datetime.now()
            profile.last_login_method = method
            if nickname and not profile.nickname:
                profile.nickname = nickname
            if gender is not None:
                profile.gender = gender
            profile.updater = user_id
            profile.update_time = datetime.now()
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新登录信息失败: user_id={user_id}, error={e}")

    def update_profile(
        self,
        session: Session,
        user_id: str,
        nickname: Optional[str] = None,
        bio: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserProfile]:
        """更新用户昵称、简介等基本信息"""
        profile = self.get_or_create(session, user_id)
        try:
            if nickname is not None:
                profile.nickname = nickname.strip() if nickname else None
            if bio is not None:
                profile.bio = bio.strip() if bio else None
            if custom_data is not None:
                profile.custom_data = custom_data
            profile.updater = user_id
            profile.update_time = datetime.now()
            session.commit()
            session.refresh(profile)
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新用户资料失败: user_id={user_id}, error={e}")
            return None

    def update_avatar(
        self,
        session: Session,
        user_id: str,
        avatar_url: str,
        avatar_storage_path: str,
    ) -> Optional[UserProfile]:
        """更新用户自定义头像（访问 URL + MinIO 存储路径）"""
        profile = self.get_or_create(session, user_id)
        try:
            profile.avatar_url = avatar_url
            profile.avatar_storage_path = avatar_storage_path
            profile.updater = user_id
            profile.update_time = datetime.now()
            session.commit()
            session.refresh(profile)
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新用户头像失败: user_id={user_id}, error={e}")
            return None

    def update_role(
        self,
        session: Session,
        user_id: str,
        role: str,
        operator_id: str,
    ) -> Optional[UserProfile]:
        """管理员调整用户角色"""
        profile = self.get_by_user_id(session, user_id)
        if not profile:
            return None
        try:
            profile.role = role
            profile.updater = operator_id
            profile.update_time = datetime.now()
            session.commit()
            session.refresh(profile)
            logger.info(f"用户角色已调整: user_id={user_id}, role={role}, by={operator_id}")
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新用户角色失败: user_id={user_id}, error={e}")
            return None

    def update_status(
        self,
        session: Session,
        user_id: str,
        status: int,
        operator_id: str,
    ) -> Optional[UserProfile]:
        """管理员启停账号（禁用后登录拒绝签发 token；存量 token 到期自然失效）"""
        profile = self.get_by_user_id(session, user_id)
        if not profile:
            return None
        try:
            profile.status = status
            profile.updater = operator_id
            profile.update_time = datetime.now()
            session.commit()
            session.refresh(profile)
            logger.info(f"用户状态已调整: user_id={user_id}, status={status}, by={operator_id}")
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新用户状态失败: user_id={user_id}, error={e}")
            return None

    def list_profiles(
        self,
        session: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> Tuple[list, int]:
        """
        分页列出用户（管理端）

        Args:
            keyword: 模糊匹配 user_id / nickname
        Returns:
            (profiles, total)
        """
        query = session.query(UserProfile).filter(UserProfile.deleted == 0)
        if keyword:
            like = f"%{keyword.strip()}%"
            query = query.filter(
                UserProfile.user_id.like(like) | UserProfile.nickname.like(like)
            )

        total = query.count()
        items = (
            query.order_by(UserProfile.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


# 全局单例
user_profile_repo = UserProfileRepository()
