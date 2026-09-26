#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : user.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    用户相关响应模型（个人资料 / 管理端视图 / 登录审计视图）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    """个人资料（/api/user/profile 响应，结构与 AKS 一致 + role/last_login_at）"""

    user_id: str
    nickname: Optional[str] = None
    role: str = "user"
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = None
    last_login_at: Optional[str] = None
    last_login_method: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserProfileUpdateRequest(BaseModel):
    """更新个人资料请求（与 AKS 一致；头像上传接口在 Phase 3 迁入）"""

    nickname: Optional[str] = Field(default=None, max_length=64)
    bio: Optional[str] = Field(default=None, max_length=2000)
    custom_data: Optional[Dict[str, Any]] = None


# ==================== 管理端 ====================


class AdminUserView(BaseModel):
    """管理端用户视图"""

    user_id: str
    nickname: Optional[str] = None
    role: str = "user"
    status: int = 0
    bio: Optional[str] = None
    last_login_at: Optional[str] = None
    last_login_method: Optional[str] = None
    created_at: Optional[str] = None


class RoleUpdateRequest(BaseModel):
    """调整用户角色"""

    role: str = Field(..., description="目标角色：user / admin")


class StatusUpdateRequest(BaseModel):
    """启停账号"""

    status: int = Field(..., ge=0, le=1, description="0=启用，1=禁用")


class LoginAuditView(BaseModel):
    """登录审计视图"""

    id: int
    user_id: str
    method: str
    success: bool
    fail_reason: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    login_time: Optional[str] = None
