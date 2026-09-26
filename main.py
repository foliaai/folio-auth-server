#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : main.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    FastAPI 应用入口（folio-auth-server，:8003）
    启动方式: uv run uvicorn main:app --reload --host 0.0.0.0 --port 8003

    本服务是全系统唯一的 token 签发方（RS256 私钥只在这里）。
    自身的 admin 接口也用 folio-auth-core 验签——把自己的公钥以
    static_jwks 直接注入 verifier，零网络调用完成自举。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from auth_core import AuthCoreSettings, configure_verifier
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app import config
from app.db import check_db_alive, close_db, init_db
from app.routers import admin_router, auth_router, settings_router, user_router
from app.services.cache import close_cache
from app.services.keys import load_private_key


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期：启动时加载密钥/配置校验器/建表，关闭时释放连接"""
    logger.info("folio-auth-server 启动中...")

    # 1) 加载 RS256 私钥（生产缺失直接启动失败，fail-fast）
    load_private_key()

    # 2) 用自己的公钥自举 folio-auth-core 校验器（admin guard 等依赖即生效）
    from app.services.keys import build_jwks

    configure_verifier(
        AuthCoreSettings(
            issuer=config.get_token_issuer(),
            admin_roles=tuple(config.get_admin_roles()),
            admin_user_ids=tuple(config.get_bootstrap_admin_user_ids()),
            header_passthrough=False,
        ),
        static_jwks=build_jwks(),
    )
    logger.info("auth-core 校验器已配置（static_jwks 自举）")

    # 3) 建表（MySQL 不可用时不阻断启动——/health 会暴露状态，登录接口自然报错）
    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        logger.error(f"MySQL 初始化失败（服务继续启动，登录/管理接口不可用）: {e}")

    logger.info(
        f"启动完成: auth_mode={config.get_auth_mode()}, issuer={config.get_token_issuer()}"
    )

    yield

    logger.info("应用关闭中，释放资源...")
    await close_cache()
    close_db()
    logger.info("所有资源已释放")


app = FastAPI(
    title="Folio Auth Server",
    description=(
        "Folio 统一认证与系统设置服务：OA / Logto 上游登录、"
        "本域 RS256 JWT 签发、用户管理（角色/状态）、登录审计、全局设置。"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(settings_router)


@app.get("/health", tags=["Ops"], summary="健康检查")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "folio-auth-server",
        "auth_mode": config.get_auth_mode(),
        "issuer": config.get_token_issuer(),
        "db_alive": check_db_alive(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
