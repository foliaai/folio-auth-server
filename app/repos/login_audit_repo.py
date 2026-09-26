#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : login_audit_repo.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    LoginAudit Repository（登录审计写入与分页查询）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import Optional, Tuple

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import LoginAudit


class LoginAuditRepository:
    """LoginAudit Repository"""

    def record(
        self,
        session: Session,
        user_id: str,
        method: str,
        success: bool,
        fail_reason: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """写入一条登录审计（失败不影响主流程，只记日志）"""
        audit = LoginAudit(
            user_id=user_id,
            method=method,
            success=1 if success else 0,
            fail_reason=(fail_reason or "")[:255] or None,
            ip=(ip or "")[:64] or None,
            user_agent=(user_agent or "")[:512] or None,
            login_time=datetime.now(),
        )
        try:
            session.add(audit)
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.warning(f"登录审计写入失败（忽略）: user_id={user_id}, error={e}")

    def list_audits(
        self,
        session: Session,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
    ) -> Tuple[list, int]:
        """分页查询登录审计（可按 user_id 过滤）"""
        query = session.query(LoginAudit)
        if user_id:
            query = query.filter(LoginAudit.user_id == user_id)

        total = query.count()
        items = (
            query.order_by(LoginAudit.login_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


# 全局单例
login_audit_repo = LoginAuditRepository()
