# llm-finetune-platform Backend Skeleton

本目录提供 FastAPI + SQLModel + Alembic 的最小骨架，便于在 Story 1.1（基础登录与账号管理）中实现认证能力。

## 本地开发

```bash
# 创建并激活虚拟环境
cd backend
python -m venv venv
source venv/bin/activate        # Windows 使用 venv\Scripts\activate

# 生成配置（示例使用 sqlite，本地体验时建议拷贝）
cp .env.local .env               # 若使用 PostgreSQL，可改用 .env.example

# 安装依赖（离线可从 requirements-dev.txt 预先下载 wheel 再安装）
pip install -r requirements-dev.txt
pip install -e .                # 可选，便于本地可编辑安装

# 运行开发服务器
uvicorn app.main:app --reload
```

## 关键环境变量

`.env.example` 中列出了 PostgreSQL 配置；想快速体验可直接：

```
DATABASE_URL=sqlite:///./llmft.db
ENVIRONMENT=development
```

- `DATABASE_URL`：数据库连接（默认 PostgreSQL，可在开发时改为 SQLite）。
- `JWT_SECRET_KEY` / `JWT_ALGORITHM`：签发 Access/Refresh Token 的密钥配置。
- `LOGIN_RATE_LIMIT_*`：登录速率限制窗口与次数。
- `VERIFICATION_CODE_EXPIRE_MINUTES` / `VERIFICATION_ATTEMPT_LIMIT`：验证码有效期与尝试上限。

开发环境下应用启动会自动执行 `init_db()` 创建基本数据表。

## 数据库迁移

```bash
alembic revision --autogenerate -m "init schema"
alembic upgrade head
```

## 测试

```bash
python -m pytest
```

更多架构与编码规范参考 `docs/architecture.md` 与 `docs/Python编码规范与风格指南.md`。
