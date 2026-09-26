#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : audit.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    登录审计辅助：客户端 IP / UA 提取 + 统一写入入口
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.repos import login_audit_repo


def get_client_ip(request: Request) -> Optional[str]:
    """提取客户端 IP（反向代理场景读 X-Forwarded-For 第一个）"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_client_ua(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


def record_login(
    session: Session,
    request: Request,
    user_id: str,
    method: str,
    success: bool,
    fail_reason: Optional[str] = None,
) -> None:
    """记录一次登录尝试（成功与失败都记）"""
    login_audit_repo.record(
        session,
        user_id=user_id,
        method=method,
        success=success,
        fail_reason=fail_reason,
        ip=get_client_ip(request),
        user_agent=get_client_ua(request),
    )
