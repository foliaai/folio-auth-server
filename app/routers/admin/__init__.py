#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    Admin API 路由模块（全部需要管理员权限，守卫来自 folio-auth-core）
    端点：
      GET   /api/admin/users                - 用户列表（分页/关键词）
      PATCH /api/admin/users/{id}/role      - 调整角色
      PATCH /api/admin/users/{id}/status    - 启停账号
      GET   /api/admin/logins               - 登录审计（分页）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter

from app.routers.admin.logins import router as logins_router
from app.routers.admin.users import router as users_router

admin_router = APIRouter(prefix="/api/admin")
admin_router.include_router(users_router)
admin_router.include_router(logins_router)

__all__ = ["admin_router"]
