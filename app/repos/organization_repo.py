#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : organization_repo.py
@Author  : caixiongjiang
@Date  : 2026/09/28
@Function:
    Organization / UserOrganization Repository
    - sync_user_departments: OA 登录时以现值整体刷新（upsert 组织 + 替换关联）
      身份属性与昵称/头像的"库内优先"相反，永远以 OA 为准
    - list_user_departments: join 查询用户部门（主部门在前，展示用）
    - map_main_departments: 批量取主部门名（管理端列表，避免 N+1）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Organization, UserOrganization


class OrganizationRepository:
    """Organization Repository"""

    def sync_user_departments(
        self,
        session: Session,
        user_id: str,
        departments: List[Dict],
    ) -> bool:
        """
        登录时以 OA 现值整体刷新用户组织关系（单一事务）

        Args:
            departments: [{"id": int, "name": str, "is_main": bool}]，空列表 = 清空该用户全部关联
        Returns:
            是否成功（失败仅记日志，不阻断登录——组织属展示属性）
        """
        now = datetime.now()
        try:
            for dept in departments:
                org = session.get(Organization, dept["id"])
                if org is None:
                    session.add(
                        Organization(
                            department_id=dept["id"],
                            name=dept["name"],
                            source="oa",
                            synced_at=now,
                            creator=user_id,
                            updater=user_id,
                            create_time=now,
                            update_time=now,
                            deleted=0,
                        )
                    )
                else:
                    org.name = dept["name"]
                    org.synced_at = now
                    org.updater = user_id
                    org.update_time = now

            session.query(UserOrganization).filter(
                UserOrganization.user_id == user_id
            ).delete(synchronize_session=False)

            for dept in departments:
                session.add(
                    UserOrganization(
                        user_id=user_id,
                        department_id=dept["id"],
                        is_main=1 if dept.get("is_main") else 0,
                    )
                )

            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"刷新用户组织关系失败: user_id={user_id}, error={e}")
            return False

    def list_user_departments(self, session: Session, user_id: str) -> List[Dict]:
        """join 查询用户所属组织（主部门在前；组织名以 organization 表为单一事实源）"""
        try:
            rows = (
                session.query(UserOrganization, Organization)
                .join(Organization, UserOrganization.department_id == Organization.department_id)
                .filter(UserOrganization.user_id == user_id)
                .order_by(UserOrganization.is_main.desc(), UserOrganization.department_id)
                .all()
            )
            return [
                {
                    "id": uo.department_id,
                    "name": org.name,
                    "is_main": bool(uo.is_main),
                }
                for uo, org in rows
            ]
        except SQLAlchemyError as e:
            logger.error(f"查询用户组织失败: user_id={user_id}, error={e}")
            return []

    def map_main_departments(
        self, session: Session, user_ids: List[str]
    ) -> Dict[str, Optional[str]]:
        """批量取用户主部门名（管理端列表用）；无主部门取第一个，无关联为 None"""
        result: Dict[str, Optional[str]] = {uid: None for uid in user_ids}
        if not user_ids:
            return result
        try:
            rows = (
                session.query(UserOrganization, Organization)
                .join(Organization, UserOrganization.department_id == Organization.department_id)
                .filter(UserOrganization.user_id.in_(user_ids))
                .order_by(UserOrganization.is_main.desc(), UserOrganization.department_id)
                .all()
            )
            for uo, org in rows:
                # 排序保证主部门先出现；同用户仅保留第一条（主部门优先）
                if result.get(uo.user_id) is None:
                    result[uo.user_id] = org.name
            return result
        except SQLAlchemyError as e:
            logger.error(f"批量查询用户主部门失败: error={e}")
            return result


# 全局单例
organization_repo = OrganizationRepository()
