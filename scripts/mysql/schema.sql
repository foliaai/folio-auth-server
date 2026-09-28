-- ============================================================
-- folio-auth-server 建表脚本（folio_auth 库）
-- 与 SQLAlchemy 自动建表（init_db）等价，供 DBA 手工执行或核对；
-- 全新部署直接启动服务即可自动建表，无需手工跑本脚本。
--
-- 表清单：
--   user_profile       全局用户档案（从 AKS 库同名人迁入 + 新增 role/last_login_*/gender）
--   login_audit        登录审计
--   global_setting     全局系统设置
--   organization       组织（OA 部门扁平镜像，共享知识库的授权客体）
--   user_organization  用户 ↔ 组织 关联（多部门，登录时以 OA 现值整体替换）
-- ============================================================

CREATE DATABASE IF NOT EXISTS `folio_auth`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `folio_auth`;

-- ------------------------------------------------------------
-- 全局用户档案
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_profile` (
  `user_id`             VARCHAR(64)  NOT NULL COMMENT '用户唯一标识（OA 工号 EmployeeNo 或 Logto sub）',
  `nickname`            VARCHAR(64)  NULL     COMMENT '用户昵称 / 显示名称',
  `role`                VARCHAR(32)  NOT NULL DEFAULT 'user' COMMENT '角色：user=普通用户，admin=管理员',
  `avatar_url`          VARCHAR(512) NULL     COMMENT '自定义头像对外访问 URL',
  `avatar_storage_path` VARCHAR(512) NULL     COMMENT '头像在 MinIO 上的存储路径 (bucket/object_path)',
  `bio`                 TEXT         NULL     COMMENT '用户个人简介 / 签名',
  `gender`              INT          NULL     COMMENT '性别：OA Sex（1=男，2=女，0/NULL=未知）；每次 OA 登录以现值刷新',
  `custom_data`         JSON         NULL     COMMENT '扩展自定义 JSON 配置（上游 IdP 信息等）',
  `last_login_at`       DATETIME     NULL     COMMENT '最近一次登录时间',
  `last_login_method`   VARCHAR(16)  NULL     COMMENT '最近一次登录方式：oa / logto',
  `status`              INT          NOT NULL DEFAULT 0 COMMENT '状态：0=正常，1=禁用',
  `creator`             VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '创建者',
  `create_time`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updater`             VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '最后更新者',
  `update_time`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `deleted`             INT          NOT NULL DEFAULT 0 COMMENT '软删除标记：0=未删除，1=已删除',
  PRIMARY KEY (`user_id`),
  KEY `idx_user_profile_deleted` (`deleted`),
  KEY `idx_user_profile_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='全局用户档案';

-- ------------------------------------------------------------
-- 登录审计
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `login_audit` (
  `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `user_id`     VARCHAR(64)     NOT NULL COMMENT '用户标识（登录尝试的对象）',
  `method`      VARCHAR(16)     NOT NULL COMMENT '登录方式：oa / logto',
  `success`     INT             NOT NULL DEFAULT 1 COMMENT '1=成功，0=失败',
  `fail_reason` VARCHAR(255)    NULL     COMMENT '失败原因（内部记录用）',
  `ip`          VARCHAR(64)     NULL     COMMENT '客户端 IP',
  `user_agent`  VARCHAR(512)    NULL     COMMENT '客户端 User-Agent（截断存储）',
  `login_time`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
  PRIMARY KEY (`id`),
  KEY `idx_login_audit_user_time` (`user_id`, `login_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录审计';

-- ------------------------------------------------------------
-- 全局系统设置
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `global_setting` (
  `setting_key`   VARCHAR(128) NOT NULL COMMENT '设置项 key（如 system.login.allow_new_users）',
  `setting_value` JSON         NULL     COMMENT '设置值（任意 JSON）',
  `description`   VARCHAR(255) NULL     COMMENT '设置项说明',
  `is_public`     INT          NOT NULL DEFAULT 0 COMMENT '是否公开：1=未登录可读，0=仅管理员可读',
  `updated_by`    VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '最后更新者',
  `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  PRIMARY KEY (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='全局系统设置';

-- ------------------------------------------------------------
-- 组织（OA 部门扁平镜像，无父子层级）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `organization` (
  `department_id` INT          NOT NULL COMMENT 'OA DepartmentID（稳定锚，跨改名不变）',
  `name`          VARCHAR(255) NOT NULL COMMENT '完整组织名（如 IT技术中心/IT研发部，扁平不拆层级）',
  `source`        VARCHAR(16)  NOT NULL DEFAULT 'oa' COMMENT '来源：oa=OA 登录同步 / manual=手工维护（公网侧将来留口）',
  `synced_at`     DATETIME     NULL     COMMENT '最近一次有成员登录刷新的时间',
  `status`        INT          NOT NULL DEFAULT 0 COMMENT '状态：0=正常，1=禁用',
  `creator`       VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '创建者',
  `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updater`       VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '最后更新者',
  `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `deleted`       INT          NOT NULL DEFAULT 0 COMMENT '软删除标记：0=未删除，1=已删除',
  PRIMARY KEY (`department_id`),
  KEY `idx_organization_source` (`source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组织（OA 部门）';

-- ------------------------------------------------------------
-- 用户 ↔ 组织 关联（多部门；每次 OA 登录整体替换）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_organization` (
  `user_id`       VARCHAR(64) NOT NULL COMMENT '用户标识（user_profile.user_id，OA 工号）',
  `department_id` INT         NOT NULL COMMENT '组织（organization.department_id）',
  `is_main`       INT         NOT NULL DEFAULT 0 COMMENT '是否主部门：1=是（OA IsMainDepartment）',
  PRIMARY KEY (`user_id`, `department_id`),
  KEY `idx_uo_department` (`department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户所属组织';

-- ------------------------------------------------------------
-- 存量部署升级（0.1.x → 本版）：
--   organization / user_organization 两张新表由 init_db 自动创建，无需手工执行；
--   create_all 不会给已有表加列，user_profile 的 gender 需手工执行一次：
--
-- ALTER TABLE `user_profile`
--   ADD COLUMN `gender` INT NULL COMMENT '性别：OA Sex（1=男，2=女，0/NULL=未知）；每次 OA 登录以现值刷新' AFTER `bio`;
-- ------------------------------------------------------------

-- ------------------------------------------------------------
-- 存量数据迁移：AKS 库 user_profile → folio_auth 库
-- （列名完全兼容；role/last_login_at 为新增列，取默认值）
--
-- INSERT INTO folio_auth.user_profile
--   (user_id, nickname, avatar_url, avatar_storage_path, bio, custom_data,
--    status, creator, create_time, updater, update_time, deleted)
-- SELECT user_id, nickname, avatar_url, avatar_storage_path, bio, custom_data,
--        0, creator, create_time, updater, update_time, deleted
-- FROM   <aks 库名>.user_profile;
--
-- 迁移后建议手工提拔管理员：
-- UPDATE folio_auth.user_profile SET role='admin' WHERE user_id IN ('<你的工号>');
-- ------------------------------------------------------------
