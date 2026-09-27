#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : config.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    folio-auth-server 配置读取（环境变量清单见 .env.example）

    与 AKS 时期的关键差异：
      - 本域 token 一律 RS256（私钥只在本服务），issuer 固定 folio-auth
      - AUTH_MODE 只决定"上游 IdP 是谁"（oa / logto），
        两种模式最终都签发同一套本域 RS256 JWT
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Literal, Optional

from app.env import get_env, get_env_bool, get_env_int, get_env_list

AuthMode = Literal["logto", "oa"]

AUTH_MODE_LOGTO: AuthMode = "logto"
AUTH_MODE_OA: AuthMode = "oa"

# 本域 JWT
DEFAULT_ISSUER = "folio-auth"
# 默认有效期 7 天（与前端 cookie 存储时长对齐）；
# Phase 4 计划缩短到 12-24h，届时需要前端配合处理过期重登
DEFAULT_TOKEN_EXPIRES_SECONDS = 7 * 24 * 3600

# OA 开放平台默认地址（从 AKS 迁移，保持一致）
DEFAULT_OA_API_BASE = "https://ehrwuji.jiepei.com/oaopenapi"

DEFAULT_MYSQL_DATABASE = "folio_auth"


# ==================== 通用 ====================


def get_app_env() -> str:
    return get_env("APP_ENV", "development") or "development"


def is_production() -> bool:
    return get_app_env() == "production"


def get_cors_allowed_origins() -> List[str]:
    raw = get_env("CORS_ALLOWED_ORIGINS")
    defaults = [
        "http://localhost:4001",
        "http://127.0.0.1:4001",
    ]
    if not raw:
        return defaults
    origins = [item for item in raw.split(",") if item.strip()]
    return origins or defaults


# ==================== 上游 IdP ====================


def get_auth_mode() -> AuthMode:
    raw = (get_env("AUTH_MODE", AUTH_MODE_LOGTO) or "").lower()
    return "oa" if raw == "oa" else "logto"


def is_oa_auth_enabled() -> bool:
    return get_auth_mode() == AUTH_MODE_OA


# ==================== 本域 token（RS256） ====================


def get_token_issuer() -> str:
    return get_env("AUTH_TOKEN_ISSUER", DEFAULT_ISSUER) or DEFAULT_ISSUER


def get_token_expires_seconds() -> int:
    value = get_env_int("AUTH_TOKEN_EXPIRES_SECONDS", DEFAULT_TOKEN_EXPIRES_SECONDS)
    return value if value > 0 else DEFAULT_TOKEN_EXPIRES_SECONDS


def get_rsa_private_key_pem() -> Optional[str]:
    """
    RS256 私钥（PEM 文本）。
    支持两种注入方式：
      - AUTH_RSA_PRIVATE_KEY：PEM 全文（换行可写作 \\n）
      - AUTH_RSA_PRIVATE_KEY_FILE：PEM 文件路径
    生产必配；开发环境两者都缺省时由 keys 服务生成临时密钥。
    """
    inline = get_env("AUTH_RSA_PRIVATE_KEY")
    if inline:
        return inline.replace("\\n", "\n")

    file_path = get_env("AUTH_RSA_PRIVATE_KEY_FILE")
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            raise RuntimeError(f"读取私钥文件失败: {file_path}, error={e}") from e

    return None


# ==================== 用户与角色 ====================


def get_default_role() -> str:
    return get_env("AUTH_DEFAULT_ROLE", "user") or "user"


def get_admin_roles() -> List[str]:
    return get_env_list("AUTH_ADMIN_ROLES") or ["admin"]


def get_bootstrap_admin_user_ids() -> List[str]:
    """引导管理员白名单（首个管理员授角色前使用，配置工号/Logto sub）"""
    return get_env_list("AUTH_ADMIN_USER_IDS")


# ==================== MySQL ====================


def get_mysql_url() -> str:
    host = get_env("MYSQL_HOST", "localhost") or "localhost"
    port = get_env_int("MYSQL_PORT", 3306)
    user = get_env("MYSQL_USER", "root") or "root"
    password = get_env("MYSQL_PASSWORD", "") or ""
    database = get_env("MYSQL_DATABASE", DEFAULT_MYSQL_DATABASE) or DEFAULT_MYSQL_DATABASE
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


# ==================== Redis（可选，OA access_token 缓存） ====================


def get_redis_url() -> Optional[str]:
    """未配置时 OA access_token 退化为进程内存缓存（单实例部署可用）"""
    if get_env_bool("REDIS_ENABLED", False):
        host = get_env("REDIS_HOST", "localhost") or "localhost"
        port = get_env_int("REDIS_PORT", 6379)
        db = get_env_int("REDIS_DB", 5)
        password = get_env("REDIS_PASSWORD") or None
        auth_part = f":{password}@" if password else ""
        return f"redis://{auth_part}{host}:{port}/{db}"
    return None


# ==================== MinIO（头像对象存储） ====================


def get_minio_endpoint() -> str:
    return (get_env("MINIO_ENDPOINT", "") or "").strip()


def get_minio_access_key() -> str:
    return get_env("MINIO_ACCESS_KEY", "") or ""


def get_minio_secret_key() -> str:
    return get_env("MINIO_SECRET_KEY", "") or ""


def get_minio_bucket() -> str:
    return get_env("MINIO_BUCKET", "knowledge-files") or "knowledge-files"


def get_minio_secure() -> bool:
    return get_env_bool("MINIO_SECURE", False)


# ==================== OA 开放平台（内部部署） ====================


def get_oa_api_base() -> str:
    base = get_env("OA_API_BASE", DEFAULT_OA_API_BASE) or DEFAULT_OA_API_BASE
    return base.rstrip("/")


def get_oa_app_key() -> str:
    return get_env("OA_APP_KEY", "") or ""


def get_oa_app_secret() -> str:
    return get_env("OA_APP_SECRET", "") or ""


# ==================== Logto（公网部署） ====================


def get_logto_endpoint() -> str:
    """Logto 根地址（如 http://localhost:3001），OIDC issuer 为 {endpoint}/oidc"""
    return (get_env("LOGTO_ENDPOINT", "") or "").rstrip("/")


def get_logto_app_id() -> str:
    return get_env("LOGTO_APP_ID", "") or ""


def get_logto_app_secret() -> Optional[str]:
    """传统 Web 应用（机密客户端）填写；纯 SPA 公共客户端留空（走 PKCE）"""
    return get_env("LOGTO_APP_SECRET") or None
