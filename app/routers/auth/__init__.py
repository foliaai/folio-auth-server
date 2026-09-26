#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    Auth API 路由模块
    端点：
      POST /api/auth/oa/login     - OA 授权码登录（内部部署）
      POST /api/auth/logto/login  - Logto 授权码换发本域 JWT（公网部署）
      GET  /api/auth/jwks         - 本域公钥（消费方 folio-auth-core 验签用）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter

from app.routers.auth.jwks import router as jwks_router
from app.routers.auth.logto import router as logto_router
from app.routers.auth.oa import router as oa_router

auth_router = APIRouter(prefix="/api/auth")
auth_router.include_router(oa_router)
auth_router.include_router(logto_router)
auth_router.include_router(jwks_router)

__all__ = ["auth_router"]
