# folio-auth-server

Folio 统一认证与系统设置服务（:8003）—— 全系统**唯一**的 token 签发方。

| | |
|---|---|
| 上游 IdP | 企业 OA SSO（内部部署）/ [Logto](https://github.com/logto-io/logto)（公网部署），`AUTH_MODE` 二选一 |
| 本域凭证 | RS256 JWT（issuer `folio-auth`），私钥只在本服务，公钥经 `/api/auth/jwks` 发布 |
| 消费方 | 各后端引入 [folio-auth-core](https://github.com/foliaai/folio-auth-core)（verify-only 包）本地验签 |

## API 一览

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| POST | `/api/auth/oa/login` | 匿名 | OA 授权码登录（code 换员工身份 → 本域 JWT） |
| POST | `/api/auth/logto/login` | 匿名 | Logto 授权码登录（code+PKCE 服务端换票 → 本域 JWT） |
| GET | `/api/auth/jwks` | 匿名 | RS256 公钥（JWKS），消费方验签用 |
| GET / PUT | `/api/user/profile` | 登录 | 个人资料（头像接口 Phase 3 迁入） |
| GET | `/api/admin/users` | 管理员 | 用户列表（分页 / 关键词） |
| PATCH | `/api/admin/users/{id}/role` | 管理员 | 调整角色（user / admin） |
| PATCH | `/api/admin/users/{id}/status` | 管理员 | 启用 / 禁用账号 |
| GET | `/api/admin/logins` | 管理员 | 登录审计（分页） |
| GET / PUT / DELETE | `/api/settings`… | 管理员 | 全局设置；`/api/settings/public` 匿名可读 |
| GET | `/health` | 匿名 | 健康检查（含 db 状态） |

## 数据表（`folio_auth` 库，启动自动建表）

- `user_profile` —— 全局用户档案（user_id / nickname / **role** / avatar / bio / **last_login_at**；status=1 禁用拒登录）
- `login_audit` —— 登录审计（成功与失败都记）
- `global_setting` —— 跨服务的全局设置（key / JSON value / is_public）

存量迁移：AKS 库 `user_profile` 列名完全兼容，`INSERT ... SELECT` 即可（见 `scripts/mysql/schema.sql` 注释）。知识引擎自身的业务配置（模型参数等）留在 AKS，不放这里。

## 本地启动

```bash
cp .env.example .env        # 按注释填写；OA 凭证可从 AKS 的 .env.jp 平移
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

开发环境不配私钥会每次启动生成临时密钥（token 重启失效）；生成稳定开发密钥：

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out ~/.folio/auth_dev_private_key.pem
# .env: AUTH_RSA_PRIVATE_KEY_FILE=/Users/<you>/.folio/auth_dev_private_key.pem
```

**生产环境必须配置私钥**（`AUTH_RSA_PRIVATE_KEY` 或 `AUTH_RSA_PRIVATE_KEY_FILE`），否则拒绝启动。私钥泄露 = 全系统凭证可伪造，务必妥善保管、定期轮换（换钥匙后消费方按 kid 自动刷新 JWKS，无需重启）。

## 首个管理员引导

系统冷启动时还没有任何 admin 角色，两种方式二选一：

1. `.env` 设 `AUTH_ADMIN_USER_IDS=<你的工号或Logto sub>`（引导白名单，重启生效）
2. 迁移存量数据后手工提拔：`UPDATE user_profile SET role='admin' WHERE user_id='<你的工号>'`

有了第一个管理员后，走 `PATCH /api/admin/users/{id}/role` 正常管理，白名单可清空。

## 架构位置

```
folio-web (:4001)
  ├─ /api/*      → folio-aks-server (:8000)      知识引擎
  ├─ /skill-api/* → folio-skill-server (:8001)
  ├─ /agent-api/* → folio-agent-server (:8002)   规划中
  └─ /auth-api/* → folio-auth-server (:8003)     ★本服务
                        │ 签发 RS256 JWT（唯一私钥）
                        ▼
        folio-auth-core（各后端本地验签，JWKS 公钥）
```

## License

MIT
