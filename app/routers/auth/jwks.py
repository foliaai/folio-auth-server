#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : jwks.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    JWKS 端点（公开）：暴露本域 RS256 公钥
    消费方（folio-auth-core）按 kid 从这里取公钥本地验签；
    换私钥后 kid 变化，消费方按未知 kid 自动刷新。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter, Response

from app.services.keys import build_jwks

router = APIRouter(tags=["Auth"])


@router.get(
    "/jwks",
    summary="本域公钥（JWKS）",
    description="RS256 公钥集合。消费方（folio-auth-core）用于本地验签，可缓存 1 小时。",
)
async def get_jwks(response: Response) -> dict:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return build_jwks()
