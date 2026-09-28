#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : common.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    公共 Pydantic 模型（统一响应包装、分页）
    与 AKS api/schemas/common.py 结构一致，前端无需适配。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""

    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, message: str, code: int = 400, data: Any = None) -> "ApiResponse":
        return cls(code=code, message=message, data=data)


class PaginationRequest(BaseModel):
    """分页请求参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class UserDepartmentItem(BaseModel):
    """用户所属组织条目（登录响应 / 用户资料共用）"""

    id: int = Field(..., description="OA DepartmentID（稳定锚）")
    name: str = Field(..., description="完整组织名（如 IT技术中心/IT研发部）")
    is_main: bool = Field(default=False, description="是否主部门（OA IsMainDepartment）")


class PaginationResponse(BaseModel, Generic[T]):
    """分页响应"""

    items: List[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    total_pages: int = Field(default=0, description="总页数")
