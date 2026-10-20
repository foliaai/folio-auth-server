#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : directory.py
@Author  : caixiongjiang
@Date    : 2026/10/19
@Function:
    目录查询路由（团队知识库配套，设计文档 §6）

      GET /api/orgs/{department_id}/members - 部门成员列表（JP 建团队导入快照用）
      GET /api/users/search                 - 用户搜索（邀请成员，JP/prd 共用）

    两个端点均为只读、登录即可访问；auth 库零 DDL、零写路径。
    prd（Logto）无组织数据：/orgs 对不存在部门返回 404，前端按
    profile.departments 数据驱动隐藏入口，不会调用。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth_core.deps import get_current_user_id

from app.db import get_db_session
from app.repos import organization_repo, user_profile_repo
from app.schemas.common import ApiResponse
from app.schemas.directory import (
    OrgMemberItem,
    OrgMembersResponse,
    UserProfilesResponse,
    UserProfileBrief,
    UserSearchItem,
    UserSearchResponse,
)

router = APIRouter(prefix="/api", tags=["Directory"])

# 防枚举：搜索关键词最小长度与返回上限
_MIN_KEYWORD_LEN = 2
_MAX_RESULTS = 20
# 批量档案单次上限（团队成员列表一次拉全，防参数滥用）
_MAX_BATCH_IDS = 100


@router.get(
    "/orgs/{department_id}/members",
    response_model=ApiResponse[OrgMembersResponse],
    summary="获取部门成员列表",
    description=(
        "按 OA DepartmentID 返回部门成员（user_id + 是否主部门）。"
        "供前端建团队时「从部门导入」拉取成员快照——导入后由团队独立维护，"
        "不随 OA 同步变化。组织不存在返回 404。"
    ),
)
async def list_org_members(
    department_id: int,
    _user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[OrgMembersResponse]:
    org = organization_repo.get_by_department_id(session, department_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    members = organization_repo.list_department_members(session, department_id)
    return ApiResponse.success(
        data=OrgMembersResponse(
            department_id=department_id,
            department_name=org.name,
            members=[OrgMemberItem(**m) for m in members],
        ),
        message="获取部门成员成功",
    )


@router.get(
    "/users/search",
    response_model=ApiResponse[UserSearchResponse],
    summary="搜索用户（邀请成员用）",
    description=(
        "按昵称 / 用户ID 模糊搜索存活用户，只返回 user_id + 显示名。"
        f"关键词至少 {_MIN_KEYWORD_LEN} 个字符，最多返回 {_MAX_RESULTS} 条"
        "（防枚举约束）。"
    ),
)
async def search_users(
    q: str = Query(..., description="关键词（昵称 / 用户ID，模糊匹配）"),
    limit: int = Query(
        default=20, ge=1, le=_MAX_RESULTS, description="返回条数上限"
    ),
    _user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserSearchResponse]:
    keyword = (q or "").strip()
    if len(keyword) < _MIN_KEYWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"关键词至少 {_MIN_KEYWORD_LEN} 个字符",
        )

    profiles = user_profile_repo.search_public(session, keyword, limit)
    return ApiResponse.success(
        data=UserSearchResponse(
            users=[
                UserSearchItem(
                    user_id=p.user_id,
                    display_name=p.nickname or p.user_id,
                )
                for p in profiles
            ],
        ),
        message="搜索成功",
    )


@router.get(
    "/users/profiles",
    response_model=ApiResponse[UserProfilesResponse],
    summary="批量获取用户档案摘要",
    description=(
        "按 user_id 列表返回显示名 + 头像（团队成员列表渲染用）。"
        f"单次最多 {_MAX_BATCH_IDS} 个；查不到的 id 静默缺席，"
        "前端按工号回退显示。"
    ),
)
async def get_user_profiles(
    user_ids: str = Query(
        ...,
        description="逗号分隔的用户ID列表（如 84852241,10001）",
    ),
    _user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserProfilesResponse]:
    ids = [u.strip() for u in user_ids.split(",") if u.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="user_ids 不能为空")
    if len(ids) > _MAX_BATCH_IDS:
        raise HTTPException(
            status_code=400, detail=f"单次最多 {_MAX_BATCH_IDS} 个用户ID"
        )

    profiles = user_profile_repo.get_many_active(session, ids)
    return ApiResponse.success(
        data=UserProfilesResponse(
            profiles=[
                UserProfileBrief(
                    user_id=p.user_id,
                    display_name=p.nickname or p.user_id,
                    avatar_url=p.avatar_url,
                )
                for p in profiles
            ],
        ),
        message="获取档案成功",
    )
