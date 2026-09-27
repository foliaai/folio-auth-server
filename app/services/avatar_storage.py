#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : avatar_storage.py
@Author  : caixiongjiang
@Date    : 2026/09/27
@Function:
    头像对象存储（MinIO）。从 AKS 的 StorageManager 收敛为头像专用薄封装：
    同步 minio SDK + asyncio.to_thread，避免阻塞事件循环。
    storage_path 约定与 AKS 一致："{bucket}/{object_path}"。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
import io
from typing import Tuple

from loguru import logger
from minio import Minio

from app import config

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            config.get_minio_endpoint(),
            access_key=config.get_minio_access_key(),
            secret_key=config.get_minio_secret_key(),
            secure=config.get_minio_secure(),
        )
    return _client


def _split_path(storage_path: str) -> Tuple[str, str]:
    bucket, _, object_path = storage_path.partition("/")
    return bucket, object_path


async def upload(object_path: str, data: bytes, content_type: str) -> str:
    """上传头像对象，返回 storage_path（bucket/object_path）"""
    bucket = config.get_minio_bucket()

    def _put() -> None:
        _get_client().put_object(
            bucket, object_path, io.BytesIO(data), length=len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(_put)
    logger.debug(f"头像已上传 MinIO: {bucket}/{object_path}, 大小: {len(data)}")
    return f"{bucket}/{object_path}"


async def download(storage_path: str) -> bytes:
    """按 storage_path 读取头像字节"""
    bucket, object_path = _split_path(storage_path)

    def _get() -> bytes:
        resp = _get_client().get_object(bucket, object_path)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    return await asyncio.to_thread(_get)


async def delete(storage_path: str) -> None:
    """删除头像对象（不存在时静默，MinIO remove_object 对缺失对象不报错）"""
    bucket, object_path = _split_path(storage_path)
    await asyncio.to_thread(_get_client().remove_object, bucket, object_path)
    logger.debug(f"头像已从 MinIO 删除: {storage_path}")
