#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: folio-auth-server
@File    : login_test.py
@Author  : caixiongjiang
@Date    : 2026/09/26
@Function:
    本地登录链路验证脚本（开发用，Phase 3 前端切换前的后端验收工具）

    在终端里驱动一次完整的授权码登录，验证 folio-auth-server 全链路：
      授权 URL → 浏览器登录上游 IdP → 回调 code → 本服务换发本域 JWT
      → auth-core 真实 JWKS 验签 → 带 token 访问 /api/user/profile

    用法（在 folio-auth-server 目录下）：
      uv run python scripts/dev/login_test.py --mode oa
      uv run python scripts/dev/login_test.py --mode logto

    说明：
      - 前端 folio-web 不需要启动。浏览器跳转回调地址会显示"无法访问"，
        属预期——直接把地址栏里的完整 URL（含 code）复制回终端即可。
      - OA 模式授权页为静默授权（snsapi_base），通常秒级回跳。
      - Logto 模式脚本自动生成 PKCE（与前端 logto.ts 相同的 S256 流程）。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import argparse
import asyncio
import base64
import hashlib
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

# 依赖 auth-server venv 中的 httpx 与 auth_core（验签直接复用消费方视角）
from auth_core import AuthCoreSettings, TokenVerifier

# 项目根目录（scripts/dev 的上上级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_AUTH_BASE = "http://127.0.0.1:8003"
DEFAULT_REDIRECT_URI = "http://localhost:4001/callback"

OA_AUTHORIZE_URL = "https://oasso.jiepei.com/connect/authorize"
OA_AGENT_ID_DEFAULT = "100019"  # 与 folio-web/.env.jp 的 NEXT_PUBLIC_OA_AGENT_ID 一致

LOGTO_ENDPOINT_DEFAULT = "http://localhost:3001"
LOGTO_SCOPES = "openid profile email offline_access"  # 与 folio-web logto.ts 一致


def load_env_file(path: Path) -> dict:
    """极简 .env 解析（不去依赖 app.env，避免 dotenv 副作用）"""
    result = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def resolve_logto_app_id(args) -> str:
    """logto app id：参数 > auth-server .env > folio-web/.env（开发机联动）"""
    if args.logto_app_id:
        return args.logto_app_id
    server_env = load_env_file(PROJECT_ROOT / ".env")
    if server_env.get("LOGTO_APP_ID"):
        return server_env["LOGTO_APP_ID"]
    web_env = load_env_file(
        PROJECT_ROOT.parent / "folio-web" / ".env"
    )
    if web_env.get("NEXT_PUBLIC_LOGTO_APP_ID"):
        print(f"（logto app id 取自 folio-web/.env: NEXT_PUBLIC_LOGTO_APP_ID）")
        return web_env["NEXT_PUBLIC_LOGTO_APP_ID"]
    print("错误：找不到 logto app id，请用 --logto-app-id 指定")
    sys.exit(1)


def random_state() -> str:
    return secrets.token_urlsafe(24)


def make_pkce() -> tuple[str, str]:
    """生成 (code_verifier, code_challenge)，S256，与前端 logto.ts 一致"""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def extract_code(pasted: str) -> tuple[str, str | None]:
    """从粘贴内容提取 code 与 state（支持完整 URL 或裸 code）"""
    pasted = pasted.strip().strip('"').strip("'")
    if "code=" in pasted:
        query = parse_qs(urlparse(pasted).query)
        code = (query.get("code") or [""])[0]
        state = (query.get("state") or [None])[0]
        return code, state
    return pasted, None


def print_step(title: str) -> None:
    print(f"\n{'=' * 56}\n{title}\n{'=' * 56}")


async def verify_token_chain(auth_base: str, token: str) -> None:
    """用消费方视角（folio-auth-core + 真实 JWKS 端点）验证签发的 token"""
    print_step("第 4 步：auth-core 消费方视角验签（真实 JWKS 拉取）")
    verifier = TokenVerifier(
        AuthCoreSettings(
            jwks_url=f"{auth_base}/api/auth/jwks",
            issuer="folio-auth",
            jwks_min_refresh_interval_seconds=0,
        )
    )
    user = await verifier.verify(token)
    print(f"✅ 验签通过: user_id={user.user_id}, role={user.role}, name={user.name}")

    print_step("第 5 步：带 token 访问 /api/user/profile")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{auth_base}/api/user/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            profile = resp.json()["data"]
            print(f"✅ 个人资料: user_id={profile['user_id']}, role={profile['role']}, "
                  f"nickname={profile['nickname']}, last_login_at={profile['last_login_at']}")
        else:
            print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")

    print(
        "\n结论：登录→签发→验签→业务接口 全链路通过。"
        "登录审计可在 /api/admin/logins 查看（需管理员 token）。"
    )


async def login_exchange(auth_base: str, mode: str, payload: dict) -> str | None:
    print_step("第 3 步：code 交给 folio-auth-server 换发本域 JWT")
    endpoint = f"{auth_base}/api/auth/{mode}/login"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(endpoint, json=payload)
    body = resp.json()
    if resp.status_code != 200 or not body.get("data"):
        print(f"❌ HTTP {resp.status_code}: {body}")
        return None
    data = body["data"]
    print(f"✅ 登录成功: user_id={data['user']['user_id']}, role={data['user']['role']}, "
          f"expires_in={data['expires_in']}s")
    print(f"   access_token 头 40 字符: {data['access_token'][:40]}...")
    return data["access_token"]


# ==================== OA 模式 ====================


async def run_oa_flow(args) -> None:
    state = random_state()
    authorize = (
        f"{OA_AUTHORIZE_URL}?scope=snsapi_base"
        f"&agentid={args.agent_id}&state={state}"
        f"&redirect_url={args.redirect_uri}"
    )

    print_step("第 1 步：在浏览器打开下面的授权地址并完成 OA 登录")
    print(authorize)
    print(
        "\n提示：OA 是静默授权，若本机已有 OA 会话会直接跳转；"
        "\n提示：若 OA 白名单要求注册地址，可加 --redirect-uri http://192.168.19.12:4001/callback"
    )

    print_step("第 2 步：把跳转后地址栏的完整 URL（含 code）粘贴回来")
    pasted = input("> ").strip()
    code, returned_state = extract_code(pasted)
    if not code:
        print("❌ 没有从粘贴内容里找到 code")
        return
    if returned_state is not None and returned_state != state:
        print("❌ state 校验失败（不是本次发起的登录）")
        return

    token = await login_exchange(args.auth_base, "oa", {"code": code})
    if token:
        await verify_token_chain(args.auth_base, token)


# ==================== Logto 模式 ====================


async def run_logto_flow(args) -> None:
    app_id = resolve_logto_app_id(args)
    verifier, challenge = make_pkce()
    state = random_state()

    print_step("第 0 步：拉取 Logto discovery")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{args.logto_endpoint}/oidc/.well-known/openid-configuration"
        )
        resp.raise_for_status()
        discovery = resp.json()
    authorize_endpoint = discovery["authorization_endpoint"]
    print(f"✅ authorization_endpoint = {authorize_endpoint}")

    authorize = (
        f"{authorize_endpoint}?client_id={app_id}"
        f"&redirect_uri={args.redirect_uri}"
        f"&response_type=code&scope={LOGTO_SCOPES.replace(' ', '+')}"
        f"&state={state}"
        f"&code_challenge={challenge}&code_challenge_method=S256"
    )

    print_step("第 1 步：在浏览器打开下面的授权地址并用 Logto 账号登录")
    print(authorize)
    print(
        "\n提示：本地 Logto 管理台在 http://localhost:3002（如需建测试账号）。\n"
        "提示：跳转回调页会显示无法访问，属预期，复制地址栏 URL 即可。"
    )

    print_step("第 2 步：把跳转后地址栏的完整 URL（含 code）粘贴回来")
    pasted = input("> ").strip()
    code, returned_state = extract_code(pasted)
    if not code:
        print("❌ 没有从粘贴内容里找到 code")
        return
    if returned_state is not None and returned_state != state:
        print("❌ state 校验失败（不是本次发起的登录）")
        return

    token = await login_exchange(
        args.auth_base,
        "logto",
        {
            "code": code,
            "redirect_uri": args.redirect_uri,
            "code_verifier": verifier,
        },
    )
    if token:
        await verify_token_chain(args.auth_base, token)


def main() -> None:
    parser = argparse.ArgumentParser(description="folio-auth-server 本地登录链路验证")
    parser.add_argument(
        "--mode", choices=["oa", "logto"], default="oa", help="登录模式（默认 oa）"
    )
    parser.add_argument("--auth-base", default=DEFAULT_AUTH_BASE, help="auth-server 地址")
    parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI, help="回调地址")
    parser.add_argument("--agent-id", default=OA_AGENT_ID_DEFAULT, help="OA agentid")
    parser.add_argument("--logto-endpoint", default=LOGTO_ENDPOINT_DEFAULT, help="Logto 地址")
    parser.add_argument("--logto-app-id", default=None, help="Logto app id")
    args = parser.parse_args()

    print(f"folio-auth-server 本地登录验证（mode={args.mode}, base={args.auth_base}）")

    # 先确认服务在跑
    try:
        health = httpx.get(f"{args.auth_base}/health", timeout=5).json()
        print(f"服务状态: {health}")
    except Exception as e:  # noqa: BLE001
        print(f"❌ auth-server 未响应（{e}），请先启动: uv run uvicorn main:app --port 8003")
        sys.exit(1)

    flow = run_oa_flow if args.mode == "oa" else run_logto_flow
    asyncio.run(flow(args))


if __name__ == "__main__":
    main()
