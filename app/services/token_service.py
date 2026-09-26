#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : token_service.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    本域 JWT 签发（RS256，issuer=folio-auth）
    取代 AKS 时期的 HS256（aks-auth）：私钥只在本服务，
    消费方（AKS / skill-server / agent-server）通过 folio-auth-core
    用 JWKS 公钥本地验签。

    claims 约定（folio-auth-core 按此解析）：
      sub   = user_id（OA 工号 / Logto sub）
      name  = 展示名（不参与鉴权）
      role  = 角色（admin guard 依据）
      iss   = folio-auth
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app import config
from app.services.keys import sign


def create_access_token(
    user_id: str,
    name: Optional[str] = None,
    role: Optional[str] = None,
) -> Tuple[str, int]:
    """
    为用户签发本域 JWT（RS256）

    Args:
        user_id: 用户标识（OA 模式为工号 EmployeeNo，logto 模式为 Logto sub）
        name:    用户姓名（仅用于展示，不参与鉴权）
        role:    角色；缺省时读取全局默认角色配置

    Returns:
        (token, expires_in)：token 字符串与有效期（秒）
    """
    if not user_id or not user_id.strip():
        raise ValueError("签发 JWT 需要有效的 user_id")

    expires_in = config.get_token_expires_seconds()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id.strip(),
        "iss": config.get_token_issuer(),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "role": role or config.get_default_role(),
    }
    if name:
        payload["name"] = name

    token = sign(payload)
    return token, expires_in
