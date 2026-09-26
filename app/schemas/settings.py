#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : settings.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    全局设置相关请求 / 响应模型
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SettingView(BaseModel):
    """设置项视图"""

    key: str
    value: Optional[Any] = None
    description: Optional[str] = None
    is_public: bool = False
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None


class SettingUpsertRequest(BaseModel):
    """新增 / 更新设置项"""

    value: Any = Field(..., description="设置值（任意 JSON）")
    description: Optional[str] = Field(default=None, max_length=255)
    is_public: bool = Field(
        default=False,
        description="是否公开（公开项未登录可读，适合前端启动配置类开关）",
    )
