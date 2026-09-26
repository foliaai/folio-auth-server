#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : settings.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    全局系统设置路由
      GET  /api/settings           - 全部设置（管理员）
      GET  /api/settings/public    - 公开设置（未登录可读，前端启动配置）
      PUT  /api/settings/{key}     - 新增 / 更新设置项（管理员）
      DELETE /api/settings/{key}   - 删除设置项（管理员）
    边界：知识引擎自身的业务配置（模型参数等）留在 AKS，
    这里只放跨服务的"全局"设置。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from auth_core.claims import CurrentUser
from auth_core.deps import require_admin
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.repos import global_setting_repo
from app.schemas.common import ApiResponse
from app.schemas.settings import SettingUpsertRequest, SettingView

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get(
    "",
    response_model=ApiResponse[list[SettingView]],
    summary="全部全局设置（管理员）",
)
async def list_settings(
    session: Session = Depends(get_db_session),
    admin: CurrentUser = Depends(require_admin),
) -> ApiResponse[list[SettingView]]:
    settings = global_setting_repo.list_all(session)
    return ApiResponse.success(
        data=[SettingView(**global_setting_repo.to_dict(s)) for s in settings]
    )


@router.get(
    "/public",
    response_model=ApiResponse[dict],
    summary="公开设置（未登录可读）",
    description="返回 is_public=1 的设置项 {key: value}，适合前端启动时拉取开关类配置。",
)
async def list_public_settings(
    session: Session = Depends(get_db_session),
) -> ApiResponse[dict]:
    settings = global_setting_repo.list_all(session, public_only=True)
    return ApiResponse.success(data={s.setting_key: s.setting_value for s in settings})


@router.put(
    "/{key}",
    response_model=ApiResponse[SettingView],
    summary="新增 / 更新设置项（管理员）",
)
async def upsert_setting(
    key: str,
    body: SettingUpsertRequest,
    session: Session = Depends(get_db_session),
    admin: CurrentUser = Depends(require_admin),
) -> ApiResponse[SettingView]:
    if not key.strip() or len(key) > 128:
        raise HTTPException(status_code=400, detail="设置项 key 非法（1-128 字符）")

    setting = global_setting_repo.upsert(
        session,
        key=key.strip(),
        value=body.value,
        operator_id=admin.user_id,
        description=body.description,
        is_public=body.is_public,
    )
    if not setting:
        raise HTTPException(status_code=500, detail="保存设置失败")
    return ApiResponse.success(
        data=SettingView(**global_setting_repo.to_dict(setting)), message="设置已保存"
    )


@router.delete(
    "/{key}",
    response_model=ApiResponse[None],
    summary="删除设置项（管理员）",
)
async def delete_setting(
    key: str,
    session: Session = Depends(get_db_session),
    admin: CurrentUser = Depends(require_admin),
) -> ApiResponse[None]:
    if not global_setting_repo.delete(session, key):
        raise HTTPException(status_code=404, detail="设置项不存在")
    return ApiResponse.success(message="设置已删除")
