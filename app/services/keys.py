#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : keys.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    RS256 密钥管理（本服务持有全系统唯一的 token 签名私钥）

    加载优先级：
      1. AUTH_RSA_PRIVATE_KEY（PEM 全文，\n 转义）
      2. AUTH_RSA_PRIVATE_KEY_FILE（PEM 文件路径）
      3. 非生产环境：进程内临时生成（重启即失效，仅本机开发用）
    生产环境两者都未配置时启动即报错。

    kid = 公钥 SHA-256 指纹前 16 位 hex：
      换钥匙后 kid 自动变化，消费方（folio-auth-core）按 kid 轮换刷新 JWKS。

    生成长期密钥（推荐 2048 位以上，妥善保管私钥）：
      openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
        -out auth_private_key.pem
      openssl rsa -in auth_private_key.pem -pubout -out auth_public_key.pem
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import base64
import hashlib
from typing import Any, Dict, Optional, Tuple

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from loguru import logger

from app import config

_private_key_obj = None
_kid: Optional[str] = None


def _pem_to_key(pem_text: str):
    return serialization.load_pem_private_key(pem_text.encode("utf-8"), password=None)


def load_private_key():
    """
    加载（或生成）RS256 私钥，进程内缓存。

    Returns:
        cryptography 私钥对象

    Raises:
        RuntimeError: 生产环境未配置私钥
    """
    global _private_key_obj, _kid
    if _private_key_obj is not None:
        return _private_key_obj

    pem = config.get_rsa_private_key_pem()
    if pem:
        try:
            _private_key_obj = _pem_to_key(pem)
        except (ValueError, TypeError) as e:
            raise RuntimeError(f"AUTH_RSA_PRIVATE_KEY 不是有效的 RSA 私钥 PEM: {e}") from e
        logger.info("已加载配置注入的 RS256 私钥")
    elif config.is_production():
        raise RuntimeError(
            "生产环境必须配置 AUTH_RSA_PRIVATE_KEY 或 AUTH_RSA_PRIVATE_KEY_FILE"
        )
    else:
        _private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        logger.warning(
            "开发模式：未配置 RS256 私钥，已生成进程临时密钥（重启后所有 token 失效）"
        )

    _kid = _compute_kid(_private_key_obj)
    return _private_key_obj


def _compute_kid(private_key) -> str:
    """公钥 DER 的 SHA-256 指纹前 16 位 hex 作为 kid"""
    public_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(public_der).hexdigest()[:16]


def get_kid() -> str:
    """当前签名钥匙的 kid（先确保私钥已加载）"""
    if _kid is None:
        load_private_key()
    return _kid  # type: ignore[return-value]


def build_jwks() -> Dict[str, Any]:
    """
    构造 JWKS 文档（GET /api/auth/jwks 的响应体）。
    只暴露公钥——私钥永远不会出现在任何响应里。
    """
    private_key = load_private_key()
    public_key = private_key.public_key()

    public_numbers = public_key.public_numbers()
    n_bytes = public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": get_kid(),
        "n": _b64url(n_bytes),
        "e": _b64url(
            public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")
        ),
    }
    return {"keys": [jwk]}


def sign(payload: Dict[str, Any]) -> str:
    """用私钥签发 RS256 token（token_service 的底层）"""
    private_key = load_private_key()
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": get_kid()})


def public_key_pem() -> str:
    """导出公钥 PEM（诊断/分发用）"""
    private_key = load_private_key()
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
