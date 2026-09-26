#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : env.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    轻量环境变量管理（.env 加载 + 类型化读取）
    只保留本服务需要的最小集合，不复用 AKS 的 EnvManager
    （那个捆绑了 Milvus/Kafka 等与本服务无关的配置）。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from loguru import logger

# 项目根目录（app/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = PROJECT_ROOT / ".env"

_loaded = False


def _ensure_loaded() -> None:
    """加载 .env（幂等；显式设置的进程环境变量优先级更高，load_dotenv 默认不覆盖）"""
    global _loaded
    if _loaded:
        return
    _loaded = True
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
        logger.info(f"已加载环境变量文件: {_ENV_FILE}")
    else:
        logger.warning(f"环境变量文件不存在: {_ENV_FILE}，仅使用系统环境变量")


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """读取环境变量（strip 后返回）"""
    _ensure_loaded()
    import os

    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip()


def get_env_int(key: str, default: int) -> int:
    raw = get_env(key)
    if raw is None or not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"环境变量 {key}={raw} 无法转换为整数，使用默认值 {default}")
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    raw = get_env(key)
    if raw is None or not raw:
        return default
    return raw.lower() in {"true", "1", "yes", "on", "t", "y"}


def get_env_list(key: str, separator: str = ",") -> List[str]:
    raw = get_env(key)
    if not raw:
        return []
    return [item.strip() for item in raw.split(separator) if item.strip()]
