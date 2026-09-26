#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : login_audit.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    登录审计表（成功与失败都记录，管理端可查）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import BIGINT

from app.db import Base


class LoginAudit(Base):
    """登录审计记录（只增不改）"""

    __tablename__ = "login_audit"

    __table_args__ = (
        Index("idx_login_audit_user_time", "user_id", "login_time"),
    )

    id = Column(
        BIGINT(unsigned=True).with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        comment="自增主键",
    )

    user_id = Column(String(64), nullable=False, comment="用户标识（登录尝试的对象）")

    method = Column(String(16), nullable=False, comment="登录方式：oa / logto")

    success = Column(Integer, default=1, nullable=False, comment="1=成功，0=失败")

    fail_reason = Column(String(255), nullable=True, comment="失败原因（内部记录用）")

    ip = Column(String(64), nullable=True, comment="客户端 IP")

    user_agent = Column(String(512), nullable=True, comment="客户端 User-Agent（截断存储）")

    login_time = Column(DateTime, default=datetime.now, nullable=False, comment="登录时间")
