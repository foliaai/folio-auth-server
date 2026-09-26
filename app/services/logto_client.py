#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : logto_client.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    Logto OIDC 客户端（公网部署）
    修复 AKS 时期的安全漏洞：前端不再直接持有 Logto token 充当本域凭证，
    而是回调后把 code+PKCE 交给本服务：
      1. 服务端用 code + code_verifier 到 Logto token 端点换 id_token/access_token
      2. 验证 id_token 签名（Logto JWKS）与 issuer/audience
      3. 用 access_token 拉取 userinfo（权威身份来源）
      4. 换发本域 RS256 JWT（与 OA 模式同一套凭证）
    Logto 的 token 只在服务端短暂存在，不下发前端。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, Optional

import httpx
import jwt
from loguru import logger

from app import config

_HTTP_TIMEOUT_SECONDS = 10.0

# id_token 验签允许的算法白名单（Logto 默认用 ES384 签 id_token；
# 白名单校验拒绝算法混淆攻击，但不写死单一算法）
_ALLOWED_ID_TOKEN_ALGS = {
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "PS256", "PS384", "PS512",
    "EdDSA",
}

# 进程内缓存：discovery 文档与 Logto JWKS（分别带简单 TTL）
_DISCOVERY_CACHE_TTL = 3600


class LogtoApiError(Exception):
    """Logto 调用失败"""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LogtoClient:
    """Logto OIDC 客户端（进程内单例使用）"""

    def __init__(self) -> None:
        self._discovery: Optional[Dict[str, Any]] = None
        self._discovery_fetched_at: float = 0.0
        self._jwks: Optional[Dict[str, Any]] = None

    # ==================== 配置 ====================

    def _ensure_configured(self) -> None:
        if not config.get_logto_endpoint() or not config.get_logto_app_id():
            raise LogtoApiError(
                "Logto 登录未配置：缺少 LOGTO_ENDPOINT / LOGTO_APP_ID",
                status_code=503,
            )

    @property
    def issuer(self) -> str:
        """Logto OIDC issuer（discovery 文档中的 issuer 字段与此一致）"""
        return f"{config.get_logto_endpoint()}/oidc"

    # ==================== discovery ====================

    async def _get_discovery(self) -> Dict[str, Any]:
        """获取并缓存 discovery 文档（token/userinfo/jwks 端点均从这里来）"""
        import time

        if (
            self._discovery is not None
            and time.time() - self._discovery_fetched_at < _DISCOVERY_CACHE_TTL
        ):
            return self._discovery

        url = f"{config.get_logto_endpoint()}/oidc/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(url)
                response.raise_for_status()
                document = response.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"拉取 Logto discovery 失败: {url}, error={e}")
            raise LogtoApiError("Logto 认证服务暂不可用，请稍后重试") from e

        self._discovery = document
        import time as _time

        self._discovery_fetched_at = _time.time()
        return document

    # ==================== 业务接口 ====================

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> Dict[str, Any]:
        """
        授权码 + PKCE 换取 token（服务端直连，前端不经手 Logto token）

        Args:
            code:          前端 OIDC 回调拿到的授权码（一次性）
            redirect_uri:  与发起授权时一致的回调地址
            code_verifier: PKCE code_verifier（前端 sessionStorage 中持有）

        Returns:
            Logto token 响应（id_token / access_token / expires_in 等）

        Raises:
            LogtoApiError: code 无效（401）或 Logto 服务异常（502）
        """
        self._ensure_configured()
        if not code or not code.strip():
            raise LogtoApiError("缺少 Logto 授权码", status_code=401)

        discovery = await self._get_discovery()
        token_endpoint = discovery.get("token_endpoint")
        if not token_endpoint:
            raise LogtoApiError("Logto discovery 缺少 token_endpoint")

        form: Dict[str, str] = {
            "grant_type": "authorization_code",
            "client_id": config.get_logto_app_id(),
            "code": code.strip(),
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        # 机密客户端（传统 Web 应用）带 secret；SPA 公共客户端留空走纯 PKCE
        app_secret = config.get_logto_app_secret()
        if app_secret:
            form["client_secret"] = app_secret

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(token_endpoint, data=form)
                if response.status_code != 200:
                    detail = ""
                    try:
                        detail = str(response.json().get("error_description") or response.json().get("error") or "")
                    except ValueError:
                        pass
                    logger.warning(
                        f"Logto code 换 token 失败: status={response.status_code}, detail={detail}"
                    )
                    raise LogtoApiError(
                        "Logto 登录校验失败，请重新发起登录", status_code=401
                    )
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Logto token 端点请求失败: {e}")
            raise LogtoApiError("Logto 认证服务暂不可用，请稍后重试") from e

    async def verify_id_token(self, id_token: str) -> Dict[str, Any]:
        """
        验证 Logto id_token（签名 + issuer + audience），返回 claims

        防御纵深：token 是服务端直连换取的，理论上已可信；
        再验一次签名可挡住 Logto 配置错误与中间人场景。
        """
        self._ensure_configured()
        jwks = await self._get_jwks()

        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as e:
            raise LogtoApiError("Logto id_token 格式非法", status_code=401) from e

        algorithm = header.get("alg")
        if algorithm not in _ALLOWED_ID_TOKEN_ALGS:
            raise LogtoApiError(
                f"Logto id_token 使用了不支持的算法: {algorithm}", status_code=401
            )

        kid = header.get("kid") or ""
        key_entry = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == kid), None
        )
        if key_entry is None:
            raise LogtoApiError("Logto 签名密钥未知", status_code=401)

        try:
            public_key = jwt.PyJWK(key_entry, algorithm=algorithm).key
            return jwt.decode(
                id_token,
                public_key,
                algorithms=[algorithm],
                issuer=self.issuer,
                audience=config.get_logto_app_id(),
                leeway=30,
            )
        except jwt.PyJWTError as e:
            logger.warning(f"Logto id_token 校验失败: {e}")
            raise LogtoApiError("Logto 登录凭证校验失败", status_code=401) from e

    async def fetch_userinfo(self, access_token: str) -> Dict[str, Any]:
        """用 access_token 拉取 userinfo（sub 为权威用户标识）"""
        discovery = await self._get_discovery()
        userinfo_endpoint = discovery.get("userinfo_endpoint")
        if not userinfo_endpoint:
            raise LogtoApiError("Logto discovery 缺少 userinfo_endpoint")

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Logto userinfo 请求失败: {e}")
            raise LogtoApiError("Logto 用户服务暂不可用，请稍后重试") from e
        except ValueError as e:
            logger.error(f"解析 Logto userinfo 响应失败: {e}")
            raise LogtoApiError("Logto 用户服务返回格式异常") from e

    async def _get_jwks(self) -> Dict[str, Any]:
        """拉取 Logto JWKS（进程内缓存；kid 未命中时调用方应重建实例重试）"""
        if self._jwks is not None:
            return self._jwks

        discovery = await self._get_discovery()
        jwks_uri = discovery.get("jwks_uri")
        if not jwks_uri:
            raise LogtoApiError("Logto discovery 缺少 jwks_uri")

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                self._jwks = response.json()
                return self._jwks
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"拉取 Logto JWKS 失败: {jwks_uri}, error={e}")
            raise LogtoApiError("Logto 认证服务暂不可用，请稍后重试") from e


# 全局单例
logto_client = LogtoClient()
