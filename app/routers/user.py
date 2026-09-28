#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : user.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    个人资料路由（从 AKS api/routers/user/profile.py 迁入）
      GET  /api/user/profile        - 获取当前用户资料
      PUT  /api/user/profile        - 更新当前用户资料（昵称、简介等）
      POST /api/user/avatar         - 上传自定义头像（MinIO + avatar_url，覆盖旧头像）
      GET  /api/user/avatar/{id}    - 头像文件直读（匿名，img 标签用）
    「恢复默认头像」功能已整体移除（前端无入口）：上传新图自动替换并清理旧对象，
    默认 Identicon 仅在无自定义头像时展示。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import io
import time
from pathlib import Path
from typing import Dict, List

from auth_core.deps import get_current_user_id
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from loguru import logger
from PIL import Image
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.repos import organization_repo, user_profile_repo
from app.schemas.common import ApiResponse, UserDepartmentItem
from app.schemas.user import AvatarUploadResponse, UserProfileResponse, UserProfileUpdateRequest
from app.services import avatar_storage

router = APIRouter(prefix="/api/user", tags=["User"])


def _to_response(profile, departments: List[Dict] | None = None) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=profile.user_id,
        nickname=profile.nickname,
        role=profile.role,
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        gender=profile.gender,
        departments=[UserDepartmentItem(**d) for d in (departments or [])],
        custom_data=profile.custom_data,
        last_login_at=profile.last_login_at.isoformat() if profile.last_login_at else None,
        last_login_method=profile.last_login_method,
        created_at=profile.create_time.isoformat() if profile.create_time else None,
        updated_at=profile.update_time.isoformat() if profile.update_time else None,
    )


@router.get(
    "/profile",
    response_model=ApiResponse[UserProfileResponse],
    summary="获取当前用户资料",
    description="获取当前登录用户的资料。如果记录不存在，将自动初始化一条空记录。",
)
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserProfileResponse]:
    profile = user_profile_repo.get_or_create(session, user_id)
    departments = organization_repo.list_user_departments(session, user_id)
    return ApiResponse.success(data=_to_response(profile, departments), message="获取用户资料成功")


@router.put(
    "/profile",
    response_model=ApiResponse[UserProfileResponse],
    summary="更新当前用户资料",
    description="更新当前登录用户的昵称、个人简介等信息。",
)
async def update_profile(
    body: UserProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserProfileResponse]:
    profile = user_profile_repo.update_profile(
        session=session,
        user_id=user_id,
        nickname=body.nickname,
        bio=body.bio,
        custom_data=body.custom_data,
    )
    if not profile:
        raise HTTPException(status_code=500, detail="更新用户资料失败")

    departments = organization_repo.list_user_departments(session, user_id)
    return ApiResponse.success(data=_to_response(profile, departments), message="个人资料更新成功")


# ==================== 自定义头像（MinIO + avatar_url） ====================

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024


def _optimize_avatar_image(raw_bytes: bytes, content_type: str) -> tuple[bytes, str, str]:
    """
    对上传的图片进行尺寸限制和 WebP 格式优化（与 AKS 时期策略一致）

    Returns:
        (优化后字节, 文件后缀, MIME 类型)；SVG 与动态 GIF 保持原样
    """
    if content_type in ("image/svg+xml", "image/gif"):
        ext = ALLOWED_IMAGE_TYPES.get(content_type, ".png")
        return raw_bytes, ext, content_type

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            # 缩放至最大 512x512，保持宽高比
            max_size = 512
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img.save(output, format="WEBP", quality=90, method=6)
            return output.getvalue(), ".webp", "image/webp"
    except Exception as e:  # noqa: BLE001 - 优化失败回退原始字节，不阻断上传
        logger.warning(f"头像图片优化处理失败，回退使用原始字节: {e}")
        ext = ALLOWED_IMAGE_TYPES.get(content_type, ".png")
        return raw_bytes, ext, content_type


@router.post(
    "/avatar",
    response_model=ApiResponse[AvatarUploadResponse],
    summary="上传自定义头像",
    description=(
        "接收头像图片（PNG/JPEG/WEBP/GIF/SVG，最大 5MB），自动优化为 512px WebP 后"
        "上传 MinIO，并更新 user_profile 的头像路径与访问 URL。"
    ),
)
async def upload_avatar(
    file: UploadFile = File(..., description="头像图片文件（最大 5MB）"),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[AvatarUploadResponse]:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {content_type}。仅支持 JPG、PNG、WEBP、GIF、SVG",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"头像文件过大 ({len(raw_bytes) / 1024 / 1024:.1f}MB)，最大允许 5MB",
        )
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="头像文件内容为空")

    optimized_bytes, ext, final_mime = _optimize_avatar_image(raw_bytes, content_type)

    timestamp = int(time.time())
    object_path = f"avatars/{user_id}/avatar_{timestamp}{ext}"

    existing = user_profile_repo.get_by_user_id(session, user_id)
    old_storage_path = existing.avatar_storage_path if existing else None

    try:
        storage_path = await avatar_storage.upload(object_path, optimized_bytes, final_mime)
    except Exception as e:  # noqa: BLE001
        logger.error(f"上传头像至 MinIO 失败: user_id={user_id}, error={e}")
        raise HTTPException(status_code=500, detail="头像存储失败")

    # 对外 URL 走前端同源代理（/auth-api -> /api），时间戳用于强制刷新前端缓存
    avatar_url = f"/auth-api/user/avatar/{user_id}?t={timestamp}"

    updated = user_profile_repo.update_avatar(
        session=session,
        user_id=user_id,
        avatar_url=avatar_url,
        avatar_storage_path=storage_path,
    )
    if not updated:
        # 落库失败回滚 MinIO 对象
        try:
            await avatar_storage.delete(storage_path)
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=500, detail="头像记录更新失败")

    # 清理旧头像对象（失败仅告警，不阻断）
    if old_storage_path:
        try:
            await avatar_storage.delete(old_storage_path)
            logger.info(f"已清理旧头像: {old_storage_path}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"清理旧头像异常（忽略）: {old_storage_path}, error={e}")

    logger.info(f"用户头像更新成功: user_id={user_id}, path={storage_path}")
    return ApiResponse.success(
        data=AvatarUploadResponse(user_id=user_id, avatar_url=avatar_url),
        message="头像上传成功",
    )


@router.get(
    "/avatar/{target_user_id}",
    summary="头像文件直读",
    description="匿名读取用户头像字节（img 标签无法携带 Bearer，必须公开；user_id 本身非敏感）。",
)
async def get_avatar_image(
    target_user_id: str,
    session: Session = Depends(get_db_session),
) -> Response:
    profile = user_profile_repo.get_by_user_id(session, target_user_id)
    if not profile or not profile.avatar_storage_path:
        raise HTTPException(status_code=404, detail="该用户未设置自定义头像")

    try:
        data = await avatar_storage.download(profile.avatar_storage_path)
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"下载用户头像失败: user_id={target_user_id}, "
            f"path={profile.avatar_storage_path}, error={e}"
        )
        raise HTTPException(status_code=404, detail="头像文件不存在或读取失败")

    ext = Path(profile.avatar_storage_path).suffix.lower()
    mime_map = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }

    return Response(
        content=data,
        media_type=mime_map.get(ext, "image/webp"),
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
            "Content-Disposition": f'inline; filename="avatar_{target_user_id}{ext}"',
        },
    )
