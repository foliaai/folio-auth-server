#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : global_setting.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    全局系统设置表（跨服务的全局配置，key-value / JSON）
    注意区分：知识引擎自身的业务配置（模型参数等）留在 AKS，
    这里只放"全局"设置（登录策略、默认角色、功能开关等）。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String

from app.db import Base


class GlobalSetting(Base):
    """全局设置（key 唯一，value 为 JSON）"""

    __tablename__ = "global_setting"

    setting_key = Column(
        String(128),
        primary_key=True,
        comment="设置项 key（如 system.login.allow_new_users）",
    )

    setting_value = Column(JSON, nullable=True, comment="设置值（任意 JSON）")

    description = Column(String(255), nullable=True, comment="设置项说明")

    is_public = Column(
        Integer,
        default=0,
        nullable=False,
        comment="是否公开：1=未登录可读（前端启动配置），0=仅管理员可读",
    )

    updated_by = Column(String(64), default="", nullable=False, comment="最后更新者")

    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
        comment="最后更新时间",
    )
