#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : auth.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    登录相关请求 / 响应模型
    OA 与 Logto 两种模式返回结构保持一致（仅 user 字段来源不同），
    前端只需一套存储逻辑。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional

from pydantic import BaseModel, Field


class OALoginRequest(BaseModel):
    """OA 授权码登录请求"""

    code: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="OA 网页授权回调返回的 code（一次性）",
    )


class LogtoLoginRequest(BaseModel):
    """Logto 授权码登录请求（服务端换票）"""

    code: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Logto OIDC 回调返回的授权码（一次性）",
    )
    redirect_uri: str = Field(
        ...,
        max_length=512,
        description="与发起授权时一致的回调地址（如 http://localhost:4001/callback）",
    )
    code_verifier: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="PKCE code_verifier（前端 sessionStorage 持有）",
    )


class TokenUser(BaseModel):
    """登录返回的用户信息（两种模式共用）"""

    user_id: str = Field(..., description="本系统用户标识（OA 工号 / Logto sub）")
    name: Optional[str] = Field(default=None, description="展示名")
    role: str = Field(default="user", description="角色：user / admin")
    employee_no: Optional[str] = Field(default=None, description="OA 工号（仅 OA 模式）")
    employee_id: Optional[int] = Field(default=None, description="OA 内部员工 ID（仅 OA 模式）")
    alias_name: Optional[str] = Field(default=None, description="OA 员工别名（仅 OA 模式）")
    email: Optional[str] = Field(default=None, description="邮箱（仅 Logto 模式，若有）")
    avatar: Optional[str] = Field(default=None, description="上游头像 URL（仅 Logto 模式，若有）")


class LoginData(BaseModel):
    """登录成功返回数据（OA / Logto 共用结构）"""

    access_token: str = Field(..., description="本域 JWT（RS256），后续请求通过 Authorization: Bearer 携带")
    token_type: str = Field(default="bearer", description="凭证类型")
    expires_in: int = Field(..., description="JWT 有效期（秒）")
    user: TokenUser = Field(..., description="登录用户信息")
