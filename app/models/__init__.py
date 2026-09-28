#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    数据模型（folio_auth 库五张表）
    - user_profile:       全局身份档案（从 AKS 迁入 + role/last_login_at/gender）
    - login_audit:        登录审计
    - global_setting:     全局系统设置
    - organization:       组织（OA 部门扁平镜像，共享知识库的授权客体）
    - user_organization:  用户 ↔ 组织 关联（多部门，登录时以 OA 现值整体替换）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from app.models.global_setting import GlobalSetting
from app.models.login_audit import LoginAudit
from app.models.organization import Organization
from app.models.user_organization import UserOrganization
from app.models.user_profile import UserProfile

__all__ = [
    "UserProfile",
    "LoginAudit",
    "GlobalSetting",
    "Organization",
    "UserOrganization",
]
