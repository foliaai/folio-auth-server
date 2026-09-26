#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : global_setting_repo.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    GlobalSetting Repository（全局设置读写）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import GlobalSetting


class GlobalSettingRepository:
    """GlobalSetting Repository"""

    def get(self, session: Session, key: str) -> Optional[GlobalSetting]:
        try:
            return session.query(GlobalSetting).filter(GlobalSetting.setting_key == key).first()
        except SQLAlchemyError as e:
            logger.error(f"查询全局设置失败: key={key}, error={e}")
            return None

    def get_value(self, session: Session, key: str, default: Any = None) -> Any:
        """读取单个设置值（不存在返回默认值）"""
        setting = self.get(session, key)
        return setting.setting_value if setting else default

    def list_all(self, session: Session, public_only: bool = False) -> List[GlobalSetting]:
        query = session.query(GlobalSetting)
        if public_only:
            query = query.filter(GlobalSetting.is_public == 1)
        try:
            return query.order_by(GlobalSetting.setting_key).all()
        except SQLAlchemyError as e:
            logger.error(f"查询全局设置列表失败: error={e}")
            return []

    def upsert(
        self,
        session: Session,
        key: str,
        value: Any,
        operator_id: str,
        description: Optional[str] = None,
        is_public: bool = False,
    ) -> Optional[GlobalSetting]:
        """插入或更新设置项"""
        setting = self.get(session, key)
        try:
            if setting is None:
                setting = GlobalSetting(
                    setting_key=key,
                    setting_value=value,
                    description=description,
                    is_public=1 if is_public else 0,
                    updated_by=operator_id,
                    updated_at=datetime.now(),
                )
                session.add(setting)
            else:
                setting.setting_value = value
                if description is not None:
                    setting.description = description
                setting.is_public = 1 if is_public else 0
                setting.updated_by = operator_id
                setting.updated_at = datetime.now()
            session.commit()
            session.refresh(setting)
            logger.info(f"全局设置已更新: key={key}, by={operator_id}")
            return setting
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新全局设置失败: key={key}, error={e}")
            return None

    def delete(self, session: Session, key: str) -> bool:
        setting = self.get(session, key)
        if not setting:
            return False
        try:
            session.delete(setting)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"删除全局设置失败: key={key}, error={e}")
            return False

    def to_dict(self, setting: GlobalSetting) -> Dict[str, Any]:
        return {
            "key": setting.setting_key,
            "value": setting.setting_value,
            "description": setting.description,
            "is_public": bool(setting.is_public),
            "updated_by": setting.updated_by,
            "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
        }


# 全局单例
global_setting_repo = GlobalSettingRepository()
