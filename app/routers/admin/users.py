#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : users.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    用户管理路由（管理端）
      GET   /api/admin/users              - 分页列出用户
      PATCH /api/admin/users/{id}/role    - 调整角色（user / admin）
      PATCH /api/admin/users/{id}/status  - 启停账号
    鉴权：folio-auth-core 的 require_admin（role claim 或引导白名单）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import math
from typing import Optional

from auth_core.deps import require_admin
from auth_core.claims import CurrentUser
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.repos import user_profile_repo
from app.schemas.common import ApiResponse, PaginationResponse
from app.schemas.user import AdminUserView, RoleUpdateRequest, StatusUpdateRequest

router = APIRouter(tags=["Admin"])

# 目前系统只有两档角色；后续细分时在这里扩展
ALLOWED_ROLES = {"user", "admin"}


def _to_view(profile) -> AdminUserView:
    return AdminUserView(
        user_id=profile.user_id,
        nickname=profile.nickname,
        role=profile.role,
        status=profile.status,
        bio=profile.bio,
        last_login_at=profile.last_login_at.isoformat() if profile.last_login_at else None,
        last_login_method=profile.last_login_method,
        created_at=profile.create_time.isoformat() if profile.create_time else None,
    )


@router.get(
    "/users",
    response_model=ApiResponse[PaginationResponse[AdminUserView]],
    summary="用户列表（管理员）",
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, max_length=64, description="模糊匹配 user_id / 昵称"),
    session: Session = Depends(get_db_session),
    admin: CurrentUser = Depends(require_admin),
) -> ApiResponse[PaginationResponse[AdminUserView]]:
    profiles, total = user_profile_repo.list_profiles(
        session, page=page, page_size=page_size, keyword=keyword
    )
    return ApiResponse.success(
        data=PaginationResponse(
            items=[_to_view(p) for p in profiles],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if page_size else 0,
        )
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=ApiResponse[AdminUserView],
    summary="调整用户角色（管理员）",
)
async def update_user_role(
    user_id: str,
    body: RoleUpdateRequest,
    session: Session = Depends(get_db_session),
    admin: CurrentUser = Depends(require_admin),
) -> ApiResponse[AdminUserView]:
    if body.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"不支持的角色: {body.role}（可选: user / admin）")

    if user_id == admin.user_id and body.role != "admin":
        # 防误操作：管理员把自己降级会导致自己失去管理入口
        raise HTTPException(status_code=400, detail="不能撤销自己的管理员角色")

    profile = user_profile_repo.update_role(session, user_id, body.role, operator_id=admin.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse.success(data=_to_view(profile), message="角色已更新")


@router.patch(
    "/users/{user_id}/status",
    response_model=ApiResponse[AdminUserView],
    summary="启用 / 禁用账号（管理员）",
    description="禁用后登录将被拒绝；已签发的存量 token 到期自然失效。",
)
async def update_user_status(
    user_id: str,
    body: StatusUpdateRequest,
    session: Session = Depends(get_db_session),
    admin: CurrentUser = Depends(require_admin),
) -> ApiResponse[AdminUserView]:
    if user_id == admin.user_id and body.status == 1:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")

    profile = user_profile_repo.update_status(
        session, user_id, body.status, operator_id=admin.user_id
    )
    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")

    message = "账号已禁用" if body.status == 1 else "账号已启用"
    return ApiResponse.success(data=_to_view(profile), message=message)
