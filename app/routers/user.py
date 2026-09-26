#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : user.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    个人资料路由（从 AKS api/routers/user/profile.py 迁入的读写部分）
      GET /api/user/profile - 获取当前用户资料
      PUT /api/user/profile - 更新当前用户资料（昵称、简介等）
    头像上传/读取（依赖 MinIO StorageManager）在 Phase 3 随存储服务
    一起迁入，届时补 POST/DELETE /api/user/avatar 与 GET /api/user/avatar/{id}。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from auth_core.deps import get_current_user_id
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.repos import user_profile_repo
from app.schemas.common import ApiResponse
from app.schemas.user import UserProfileResponse, UserProfileUpdateRequest

router = APIRouter(prefix="/api/user", tags=["User"])


def _to_response(profile) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=profile.user_id,
        nickname=profile.nickname,
        role=profile.role,
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        custom_data=profile.custom_data,
        last_login_at=profile.last_login_at.isoformat() if profile.last_login_at else None,
        last_login_method=profile.last_login_method,
        created_at=profile.create_time.isoformat() if profile.create_time else None,
        updated_at=profile.update_time.isoformat() if profile.update_time else None,
    )


@router.get(
    "/profile",
    response_model=ApiResponse[UserProfileResponse],
    summary="获取当前用户资料",
    description="获取当前登录用户的资料。如果记录不存在，将自动初始化一条空记录。",
)
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserProfileResponse]:
    profile = user_profile_repo.get_or_create(session, user_id)
    return ApiResponse.success(data=_to_response(profile), message="获取用户资料成功")


@router.put(
    "/profile",
    response_model=ApiResponse[UserProfileResponse],
    summary="更新当前用户资料",
    description="更新当前登录用户的昵称、个人简介等信息。",
)
async def update_profile(
    body: UserProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserProfileResponse]:
    profile = user_profile_repo.update_profile(
        session=session,
        user_id=user_id,
        nickname=body.nickname,
        bio=body.bio,
        custom_data=body.custom_data,
    )
    if not profile:
        raise HTTPException(status_code=500, detail="更新用户资料失败")

    return ApiResponse.success(data=_to_response(profile), message="个人资料更新成功")
