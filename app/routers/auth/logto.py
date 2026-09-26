#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : logto.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    Logto 授权码登录路由（公网部署）
    端点：POST /api/auth/logto/login

    AKS 时期公网部署的安全漏洞在这里修复：
    前端不再把 Logto 的 access_token 当本域凭证用（后端裸信 X-User-Id），
    而是回调后把 code + PKCE code_verifier 交给本服务：
      1. 服务端到 Logto token 端点换 id_token / access_token
      2. 验证 id_token（Logto JWKS + issuer/audience）
      3. userinfo 拉取权威身份（sub / name / email / picture）
      4. 首次登录建档、禁用校验、签发本域 RS256 JWT
    Logto token 不下发前端；前端后续统一携带本域 JWT。
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
from app.schemas.auth import LogtoLoginRequest, LoginData, TokenUser
from app.schemas.common import ApiResponse
from app.services.audit import record_login
from app.services.logto_client import LogtoApiError, logto_client
from app.services.token_service import create_access_token

router = APIRouter(tags=["Auth"])

LOGIN_METHOD = "logto"


def _extract_identity(userinfo: Dict[str, Any]) -> tuple[str, str, Dict[str, Any]]:
    """
    从 Logto userinfo 中提取本系统用户标识与展示信息

    Returns:
        (user_id, display_name, extra)：user_id = sub（Logto 全局唯一）
    """
    user_id = str(userinfo.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=502, detail="Logto 未返回有效的用户标识")

    display_name = (
        str(userinfo.get("name") or userinfo.get("username") or "").strip() or None
    )
    extra = {
        "email": str(userinfo.get("email") or "").strip() or None,
        "picture": str(userinfo.get("picture") or "").strip() or None,
        "name": display_name,
    }
    return user_id, display_name or "", extra


@router.post(
    "/logto/login",
    response_model=ApiResponse[LoginData],
    summary="Logto 授权码登录（服务端换票）",
    description=(
        "公网部署登录入口。接收前端 OIDC 回调的 code 与 PKCE code_verifier，"
        "服务端到 Logto 换取并验证身份后，签发本域 RS256 JWT。"
        "Logto 的 token 只在服务端短暂使用，不会下发前端。"
    ),
)
async def logto_login(
    body: LogtoLoginRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> ApiResponse[LoginData]:
    try:
        token_response = await logto_client.exchange_code(
            code=body.code,
            redirect_uri=body.redirect_uri,
            code_verifier=body.code_verifier,
        )
        id_token = token_response.get("id_token")
        access_token = token_response.get("access_token")

        # 防御纵深：验证 id_token（服务端直连换取，已可信，再验一次签名挡配置错误）
        if id_token:
            await logto_client.verify_id_token(str(id_token))

        userinfo = await logto_client.fetch_userinfo(str(access_token))
    except LogtoApiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:  # noqa: BLE001 - 兜底避免登录链路异常泄漏
        logger.exception(f"Logto 登录异常: {e}")
        raise HTTPException(status_code=500, detail="Logto 登录服务异常") from e

    user_id, display_name, extra = _extract_identity(userinfo)

    # 上游信息存 custom_data（后续头像/邮箱展示用）
    custom_data = {
        "logto": {
            "sub": user_id,
            "email": extra["email"],
            "picture": extra["picture"],
        }
    }
    profile = user_profile_repo.get_or_create(
        session, user_id, nickname=display_name or None, custom_data=custom_data
    )

    if profile is not None and profile.status != STATUS_ACTIVE:
        record_login(
            session, request, user_id=user_id, method=LOGIN_METHOD,
            success=False, fail_reason="account_disabled",
        )
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    token, expires_in = create_access_token(
        user_id, display_name or None, role=profile.role if profile else None
    )
    user_profile_repo.update_login(
        session, user_id, method=LOGIN_METHOD, nickname=display_name or None
    )
    record_login(session, request, user_id=user_id, method=LOGIN_METHOD, success=True)

    logger.info(f"Logto 登录成功: user_id={user_id}, name={display_name or '-'}")

    return ApiResponse.success(
        data=LoginData(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
            user=TokenUser(
                user_id=user_id,
                name=extra["name"],
                role=profile.role if profile else "user",
                email=extra["email"],
                avatar=extra["picture"],
            ),
        ),
        message="登录成功",
    )
