#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : directory.py
@Author  : caixiongjiang
@Date    : 2026/10/19
@Function:
    目录查询 API 模型（团队知识库的配套只读接口）

    两个端点均为最小信息原则（防枚举/防泄露）：
    - 部门成员：只返回 user_id + is_main（内网部门名单在 OA 本就全员可见）
    - 用户搜索：只返回 user_id + 显示名（不暴露邮箱、角色、登录方式）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List

from pydantic import BaseModel, Field


class OrgMemberItem(BaseModel):
    """部门成员条目"""
    user_id: str = Field(..., description="成员用户ID（OA 工号 / Logto sub）")
    is_main: bool = Field(default=False, description="是否主部门")


class OrgMembersResponse(BaseModel):
    """部门成员列表"""
    department_id: int = Field(..., description="OA DepartmentID")
    department_name: str = Field(..., description="完整组织名")
    members: List[OrgMemberItem] = Field(
        default_factory=list, description="成员列表（主部门在前）"
    )


class UserSearchItem(BaseModel):
    """用户搜索结果条目"""
    user_id: str = Field(..., description="用户ID")
    display_name: str = Field(..., description="显示名（昵称缺失时回退为用户ID）")


class UserSearchResponse(BaseModel):
    """用户搜索响应"""
    users: List[UserSearchItem] = Field(default_factory=list, description="命中列表")
