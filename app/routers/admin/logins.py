#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : logins.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    登录审计查询路由（管理端）
      GET /api/admin/logins - 分页查询登录记录（可按 user_id 过滤）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import math
from typing import Optional

from auth_core.claims import CurrentUser
from auth_core.deps import require_admin
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.repos import login_audit_repo
from app.schemas.common import ApiResponse, PaginationResponse
from app.schemas.user import LoginAuditView

router = APIRouter(tags=["Admin"])


@router.get(
    "/logins",
    response_model=ApiResponse[PaginationResponse[LoginAuditView]],
    summary="登录审计（管理员）",
)
async def list_logins(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None, max_length=64),
    session: Session = Depends(get_db_session),
    admin: CurrentUser = Depends(require_admin),
) -> ApiResponse[PaginationResponse[LoginAuditView]]:
    audits, total = login_audit_repo.list_audits(
        session, page=page, page_size=page_size, user_id=user_id
    )
    items = [
        LoginAuditView(
            id=audit.id,
            user_id=audit.user_id,
            method=audit.method,
            success=bool(audit.success),
            fail_reason=audit.fail_reason,
            ip=audit.ip,
            user_agent=audit.user_agent,
            login_time=audit.login_time.isoformat() if audit.login_time else None,
        )
        for audit in audits
    ]
    return ApiResponse.success(
        data=PaginationResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if page_size else 0,
        )
    )
