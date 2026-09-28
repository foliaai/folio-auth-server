#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : user_profile.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    全局用户档案表（权威用户表）
    与 AKS 同名表相比新增 role / last_login_at；
    avatar 字段保留（头像文件服务在 Phase 3 随 /api/user/* 整体迁入）。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text

from app.db import AuditModel


class UserProfile(AuditModel):
    """全局用户档案（OA 工号 / Logto sub 作为 user_id）"""

    __tablename__ = "user_profile"

    __table_args__ = (
        Index("idx_user_profile_deleted", "deleted"),
        Index("idx_user_profile_role", "role"),
    )

    user_id = Column(
        String(64),
        primary_key=True,
        comment="用户唯一标识（OA 工号 EmployeeNo 或 Logto sub）",
    )

    nickname = Column(String(64), nullable=True, comment="用户昵称 / 显示名称")

    role = Column(
        String(32),
        default="user",
        server_default="user",
        nullable=False,
        comment="角色：user=普通用户，admin=管理员",
    )

    avatar_url = Column(String(512), nullable=True, comment="自定义头像对外访问 URL")

    avatar_storage_path = Column(
        String(512), nullable=True, comment="头像在 MinIO 上的存储路径 (bucket/object_path)"
    )

    bio = Column(Text, nullable=True, comment="用户个人简介 / 签名")

    gender = Column(
        Integer,
        nullable=True,
        comment="性别：OA Sex（1=男，2=女，0/NULL=未知）；每次 OA 登录以现值刷新",
    )

    custom_data = Column(JSON, nullable=True, comment="扩展自定义 JSON 配置（上游 IdP 信息等）")

    last_login_at = Column(DateTime, nullable=True, comment="最近一次登录时间")

    last_login_method = Column(
        String(16), nullable=True, comment="最近一次登录方式：oa / logto"
    )

    # 状态语义（继承自 AuditModel.status，此处显式说明）：
    #   0 = 正常；1 = 禁用（登录拒绝签发 token）
