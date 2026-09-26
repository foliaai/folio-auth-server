#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : db.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    MySQL 连接与会话管理
    审计字段（status/creator/create_time/updater/update_time/deleted）
    与 AKS BaseModel 保持同名同义，user_profile 数据可从 AKS 库
    直接 INSERT ... SELECT 迁移（见 scripts/mysql/schema.sql）。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import Generator

from fastapi import Depends
from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app import config

Base = declarative_base()

_engine = None
_session_factory = None


class AuditModel(Base):
    """
    审计基类（与 AKS src/db/mysql/models/base_model.BaseModel 字段一致）

    - status:  0=正常，1=禁用（登录时校验，禁用账号拒绝签发 token）
    - deleted: 软删除标记
    """

    __abstract__ = True

    status = Column(Integer, default=0, nullable=False, comment="状态：0=正常，1=禁用")
    creator = Column(String(64), default="", nullable=False, comment="创建者")
    create_time = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updater = Column(String(64), default="", nullable=False, comment="最后更新者")
    update_time = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="最后更新时间"
    )
    deleted = Column(Integer, default=0, nullable=False, comment="软删除标记：0=未删除，1=已删除")


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            config.get_mysql_url(),
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话"""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """自动建表（幂等）；连不上 MySQL 时抛异常由调用方决定是否阻断启动"""
    import app.models  # noqa: F401 - 触发模型注册

    Base.metadata.create_all(bind=get_engine())
    logger.info("MySQL 初始化完成（folio-auth 库自动建表）")


def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("MySQL 连接已释放")


def check_db_alive() -> bool:
    """健康检查用：SELECT 1"""
    try:
        with get_engine().connect() as conn:
            from sqlalchemy import text

            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"MySQL 健康检查失败: {e}")
        return False
