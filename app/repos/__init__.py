#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    仓储层入口
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from app.repos.global_setting_repo import global_setting_repo
from app.repos.login_audit_repo import login_audit_repo
from app.repos.user_profile_repo import user_profile_repo

__all__ = ["user_profile_repo", "login_audit_repo", "global_setting_repo"]
