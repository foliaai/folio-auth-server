#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    路由层入口：导出各 API 路由
      - auth_router:     /api/auth（oa/login、logto/login、jwks）
      - user_router:     /api/user（个人资料）
      - admin_router:    /api/admin（用户管理、登录审计）
      - settings_router: /api/settings（全局设置）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from app.routers.admin import admin_router
from app.routers.auth import auth_router
from app.routers.settings import router as settings_router
from app.routers.user import router as user_router

__all__ = ["auth_router", "user_router", "admin_router", "settings_router"]
