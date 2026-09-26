#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : cache.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    轻量缓存（Redis 可选，未配置时降级进程内存）
    用途：OA access_token 缓存。多实例部署必须配置 Redis，
    否则各实例各自持有 access_token，OA 侧提前失效时重取更频繁。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import time
from typing import Dict, Optional, Tuple

from loguru import logger

from app import config

_redis_client = None
_redis_tried = False

# 内存降级缓存：{key: (value, expire_at)}
_memory_cache: Dict[str, Tuple[str, float]] = {}


async def _get_redis():
    """惰性获取 Redis 客户端（未配置/连不上时返回 None）"""
    global _redis_client, _redis_tried
    if _redis_tried:
        return _redis_client
    _redis_tried = True

    url = config.get_redis_url()
    if not url:
        return None
    try:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(url, decode_responses=True)
        await _redis_client.ping()
        logger.info(f"Redis 已连接: {url}")
        return _redis_client
    except Exception as e:  # noqa: BLE001 - Redis 不可用时降级
        logger.warning(f"Redis 连接失败，OA access_token 使用内存缓存: {e}")
        _redis_client = None
        return _redis_client


class Cache:
    """get / setex 两用缓存（Redis 优先，降级内存）"""

    async def get(self, key: str) -> Optional[str]:
        redis = await _get_redis()
        if redis is not None:
            try:
                value = await redis.get(key)
                return str(value) if value else None
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Redis 读取失败，降级内存缓存: {e}")

        cached = _memory_cache.get(key)
        if cached and cached[1] > time.time():
            return cached[0]
        return None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        redis = await _get_redis()
        if redis is not None:
            try:
                await redis.setex(key, max(ttl, 60), value)
                return
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Redis 写入失败，仅使用内存缓存: {e}")

        _memory_cache[key] = (value, time.time() + max(ttl, 60))


async def close_cache() -> None:
    global _redis_client, _redis_tried
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:  # noqa: BLE001
            pass
        _redis_client = None
    _redis_tried = False


# 全局单例
cache = Cache()
