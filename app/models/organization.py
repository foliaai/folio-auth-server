#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : organization.py
@Author  : caixiongjiang
@Date  : 2026/09/28
@Function:
    组织表（OA 部门的扁平镜像，无父子层级）
    - department_id 为 OA DepartmentID，是跨改名/重组的稳定锚
    - name 存完整路径名（如 "IT技术中心/IT研发部"），仅作展示不参与层级解析
    - 部门名单一事实源：用户档案的部门展示由 user_organization join 本表得出，
      OA 改名后任意成员登录刷新本表即全员生效
    - 为将来的组织知识库 / 公共知识库共享预留授权客体
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String

from app.db import AuditModel


class Organization(AuditModel):
    """组织（OA 部门）"""

    __tablename__ = "organization"

    __table_args__ = (
        Index("idx_organization_source", "source"),
    )

    department_id = Column(
        Integer,
        primary_key=True,
        comment="OA DepartmentID（稳定锚，跨改名不变）",
    )

    name = Column(
        String(255),
        nullable=False,
        comment="完整组织名（如 IT技术中心/IT研发部，扁平不拆层级）",
    )

    source = Column(
        String(16),
        default="oa",
        server_default="oa",
        nullable=False,
        comment="来源：oa=OA 登录同步 / manual=手工维护（公网侧将来留口）",
    )

    synced_at = Column(
        DateTime,
        nullable=True,
        comment="最近一次有成员登录刷新的时间",
    )
