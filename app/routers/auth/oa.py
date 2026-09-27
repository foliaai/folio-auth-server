#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : oa.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    OA 授权码登录路由（内部部署）
    端点：POST /api/auth/oa/login
    前端拿到 OA 回调 code 后调用本接口，由服务端完成：
      1. access_token 获取与缓存（Redis，降级内存）
      2. code 换取员工身份（工号 / 姓名）
      3. 首次登录写入 user_profile（user_id = 工号）
      4. 账号状态校验（禁用拒绝登录）
      5. 签发本域 RS256 JWT 返回前端（含 role claim）
      6. 记录登录审计
    迁移差异（相对 AKS api/routers/auth/oa.py）：
      token 从 HS256(aks-auth) 升级为 RS256(folio-auth)；
      新增禁用校验 / role claim / 登录审计 / last_login_at。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.repos import user_profile_repo
from app.repos.user_profile_repo import STATUS_ACTIVE
from app.schemas.auth import LoginData, OALoginRequest, TokenUser
from app.schemas.common import ApiResponse
from app.services.audit import record_login
from app.services.oa_client import OAApiError, oa_client
from app.services.token_service import create_access_token

router = APIRouter(tags=["Auth"])

FRONTEND_REDIRECT_HINT = "请返回登录页重新发起登录"
LOGIN_METHOD = "oa"


def _extract_identity(user_info: Dict[str, Any]) -> tuple[str, str, Dict[str, Any]]:
    """
    从 OA UserInfo 中提取本系统用户标识与展示信息

    Returns:
        (user_id, display_name, extra)：user_id 优先取工号 EmployeeNo，缺失时降级为 EmployeeID；
        display_name 组合规则：Name(AlisName)，缺一退化为存在的那个，双缺为空（展示层兜底工号）
    """
    employee_no = str(user_info.get("EmployeeNo") or "").strip()
    employee_id = user_info.get("EmployeeID")
    name = str(user_info.get("Name") or "").strip()
    alias_name = str(user_info.get("AlisName") or "").strip()

    user_id = employee_no
    if not user_id and employee_id is not None:
        user_id = str(employee_id).strip()

    if not user_id:
        raise HTTPException(status_code=502, detail="OA 未返回有效的用户标识")

    if name and alias_name:
        display_name = f"{name}({alias_name})"
    else:
        display_name = name or alias_name

    extra = {
        "employee_no": employee_no or None,
        "employee_id": int(employee_id) if str(employee_id or "").isdigit() else None,
        "name": name or None,
        "alias_name": alias_name or None,
    }
    return user_id, display_name, extra


@router.post(
    "/oa/login",
    response_model=ApiResponse[LoginData],
    summary="OA 授权码登录",
    description=(
        "内部部署登录入口。接收 OA 网页授权回调返回的 code，"
        "服务端换取员工身份后签发本域 RS256 JWT。"
        "AppSecret 与 OA access_token 均不会下发前端。"
    ),
)
async def oa_login(
    body: OALoginRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> ApiResponse[LoginData]:
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail=f"缺少 OA 授权码，{FRONTEND_REDIRECT_HINT}")

    try:
        user_info = await oa_client.get_user_by_code(code)
    except OAApiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:  # noqa: BLE001 - 兜底避免登录链路异常泄漏
        logger.exception(f"OA 登录异常: {e}")
        raise HTTPException(status_code=500, detail="OA 登录服务异常") from e

    user_id, display_name, extra = _extract_identity(user_info)

    # 首次登录建档；已存在的记录补全昵称，但尊重用户后续自定义
    profile = user_profile_repo.get_or_create(session, user_id, nickname=display_name or None)

    # 禁用账号拒绝登录（审计照记）
    if profile is not None and profile.status != STATUS_ACTIVE:
        record_login(
            session, request, user_id=user_id, method=LOGIN_METHOD,
            success=False, fail_reason="account_disabled",
        )
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    # 展示名优先库内值（用户可能自定义过昵称），库内为空退化上游组合名，最终兜底工号
    effective_name = (profile.nickname if profile else None) or display_name or user_id

    token, expires_in = create_access_token(
        user_id,
        (profile.nickname if profile else None) or display_name or None,
        role=profile.role if profile else None,
    )
    user_profile_repo.update_login(
        session, user_id, method=LOGIN_METHOD, nickname=display_name or None
    )
    record_login(session, request, user_id=user_id, method=LOGIN_METHOD, success=True)

    logger.info(f"OA 登录成功: user_id={user_id}, name={effective_name}")

    return ApiResponse.success(
        data=LoginData(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
            user=TokenUser(
                user_id=user_id,
                name=effective_name,
                role=profile.role if profile else "user",
                employee_no=extra["employee_no"],
                employee_id=extra["employee_id"],
                alias_name=extra["alias_name"],
                # 自定义头像（MinIO + avatar_url）优先；OA 无上游头像
                avatar=profile.avatar_url if profile else None,
            ),
        ),
        message="登录成功",
    )
