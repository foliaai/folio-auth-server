#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : user_organization.py
@Author  : caixiongjiang
@Date  : 2026/09/28
@Function:
    用户 ↔ 组织 关联表（多部门，OA UserDepartment 数组的落库形态）
    - 每次 OA 登录以 OA 现值整体替换（身份属性，区别于昵称/头像的库内优先）
    - idx_uo_department 支撑按组织反查成员（将来共享知识库的成员列表 / 权限审计）
    - 纯关系表，不继承 AuditModel（无软删 / 状态语义，替换即真相）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, Index, Integer, String

from app.db import Base


class UserOrganization(Base):
    """用户所属组织（一人可属多部门，IsMainDepartment 标记主部门）"""

    __tablename__ = "user_organization"

    __table_args__ = (
        Index("idx_uo_department", "department_id"),
    )

    user_id = Column(
        String(64),
        primary_key=True,
        comment="用户标识（user_profile.user_id，OA 工号）",
    )

    department_id = Column(
        Integer,
        primary_key=True,
        comment="组织（organization.department_id）",
    )

    is_main = Column(
        Integer,
        default=0,
        nullable=False,
        comment="是否主部门：1=是（OA IsMainDepartment）",
    )
