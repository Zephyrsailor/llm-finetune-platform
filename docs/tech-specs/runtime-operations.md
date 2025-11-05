# 运行运维脚本与实现示例

> 版本：2025-10-28  
> 目的：提供 GPU 锁、训练日志 SSE、artefact 清理等关键运维能力的参考实现，供 Phase 4 实施时直接复用或作为脚手架扩展。  

---

## 1. GPU 资源锁定与调度示例

使用 Redis 分布式锁确保同一张 GPU 同时只有一个任务执行，适用于单机多卡或并发训练场景。

```python
# scripts/gpu_lock.py
import contextlib
import time
from redis import Redis

redis = Redis.from_url("redis://redis:6379/0")
LOCK_KEY_TEMPLATE = "gpu-lock:{gpu_id}"
LOCK_TTL = 60 * 60  # 1 hour

@contextlib.contextmanager
def acquire_gpu(gpu_id: int, timeout: int = 30):
    key = LOCK_KEY_TEMPLATE.format(gpu_id=gpu_id)
    start = time.time()
    while time.time() - start < timeout:
        if redis.set(key, "locked", nx=True, ex=LOCK_TTL):
            try:
                yield gpu_id
            finally:
                redis.delete(key)
            return
        time.sleep(1)
    raise TimeoutError(f"GPU {gpu_id} still in use after {timeout}s")
```

在 Celery 任务中使用：

```python
from scripts.gpu_lock import acquire_gpu

@celery.task(bind=True)
def run_training(self, job_id):
    gpu_id = select_available_gpu()  # 可根据 torch.cuda.device_count() & redis 锁状态
    try:
        with acquire_gpu(gpu_id):
            launch_training_process(job_id, gpu_id=gpu_id)
    except TimeoutError as exc:
        self.retry(exc=exc, countdown=60)
```

### GPU 健康检查脚本

```bash
# scripts/check_gpu_health.sh
#!/usr/bin/env bash
set -euo pipefail
nvidia-smi --query-gpu=name,memory.total,memory.used,temperature.gpu --format=csv
python - <<'PY'
import torch
assert torch.cuda.is_available(), "CUDA unavailable"
print("CUDA OK, device count:", torch.cuda.device_count())
PY
```

建议在 CI 或部署时运行上述脚本，确保容器有 GPU 访问权限。

---

## 2. 训练日志 SSE 服务示例

后端 SSE 端点（FastAPI）：

```python
# backend/app/api/training/logs.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.services.training_service import stream_training_logs

router = APIRouter(prefix="/training-runs", tags=["training"])

@router.get("/{run_id}/stream")
async def stream_logs(run_id: str, user=Depends(get_current_user)):
    verify_run_access(user, run_id)

    async def event_generator():
        async for event in stream_training_logs(run_id):
            data = {"timestamp": event.timestamp.isoformat(), "level": event.level, "message": event.message}
            yield f"event: log\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

日志脱敏可在 `stream_training_logs` 内实现，例如过滤 access token：

```python
import re
TOKEN_PATTERN = re.compile(r"(token|api_key)=([A-Za-z0-9._-]+)", re.IGNORECASE)

def sanitize(message: str) -> str:
    return TOKEN_PATTERN.sub(r"\1=***", message)
```

前端订阅示例（React）：

```tsx
useEffect(() => {
  const source = new EventSource(`/api/v1/training-runs/${runId}/stream`, {
    withCredentials: true,
  });
  source.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    setLogs((prev) => [...prev, payload]);
  };
  source.onerror = () => source.close();
  return () => source.close();
}, [runId]);
```

---

## 3. Artefact 清理与容量监控

### 目录布局
- `/var/lib/llmft/datasets/{workspace}/{dataset_id}/v{n}`  
- `/var/lib/llmft/training/{workspace}/{project}/runs/{run_id}`  
- `/var/lib/llmft/models/{workspace}/{project}/versions/{version}`  
- `/var/lib/llmft/logs/{workspace}/{project}/runs/{run_id}.log`

### 清理脚本

```bash
# scripts/cleanup_artifacts.sh
#!/usr/bin/env bash
BASE_DIR=/var/lib/llmft
RETENTION_DAYS=${RETENTION_DAYS:-30}
MODEL_KEEP=${MODEL_KEEP:-5}

echo "[cleanup] removing training logs older than ${RETENTION_DAYS} days"
find "$BASE_DIR/logs" -type f -mtime +$RETENTION_DAYS -print -delete

echo "[cleanup] pruning unused training runs"
find "$BASE_DIR/training" -type d -name "runs" -prune -print0 | while IFS= read -r -d '' runs_dir; do
  ls -1t "$runs_dir" | tail -n +$((MODEL_KEEP + 1)) | while read -r old_run; do
    rm -rf "$runs_dir/$old_run"
  done
done
```

可通过 Cron 或 Celery beat 定期执行：

```bash
0 2 * * * /usr/bin/env bash /app/scripts/cleanup_artifacts.sh >> /var/log/llmft/cleanup.log 2>&1
```

### 容量监控示例

```bash
# scripts/check_disk_usage.sh
#!/usr/bin/env bash
set -euo pipefail
BASE_DIR=${1:-/var/lib/llmft}
THRESHOLD=${THRESHOLD:-80}
usage=$(df -h "$BASE_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$usage" -ge "$THRESHOLD" ]; then
  echo "[warn] $BASE_DIR usage ${usage}% >= ${THRESHOLD}%" >&2
  exit 2
fi
```

可在部署流水线或监控脚本中调用，并结合通知渠道提醒运维。

---

## 4. 即时 Story 生成 SOP

> 以下内容与 `docs/stories/story-1.1.md` / `story-1.2.md` 配合使用。

1. **准备输入**  
   - 相关 PRD 段落、Architecture/tech-spec 节点、UX 章节、风险与依赖。  
   - Story 目标、验收标准草稿。
2. **执行 create-story**  
   - 创建文件 `docs/stories/story-<epic>.<index>.md`，结构参照 `story-1.1`。  
   - 填写背景、验收、实现建议、依赖、风险。  
3. **更新 Workflow Status**  
   - 在 `docs/bmm-workflow-status.md` 的 `ORDERED_STORY_LIST` 末尾追加故事 ID。  
   - 更新 `TODO_STORY`/`TODO_TITLE` 或 `IN_PROGRESS_STORY` 字段。  
4. **评审与跟踪**  
   - 将故事文件纳入 PR 或记录到 Issue。  
   - Implementation 阶段完成故事后，更新状态文件的 `COMPLETED_STORY_LIST`、`DONE_COUNT`。

---

## 5. 工作空间角色矩阵运维指引

### 5.1 默认角色和权限说明
- 系统默认提供 5 类角色：`workspace-admin`、`data-steward`、`training-engineer`、`operations-engineer`、`business-reviewer`。  
- 权限操作枚举：`data_import`（数据导入与治理）、`training_launch`（训练发起）、`deployment_manage`（部署运维）、`evaluation_view`（评估查看）、`approval_manage`（治理审批）。  
- 默认矩阵由迁移脚本自动生成，可通过 `GET /api/v1/workspaces/{id}/roles` 查看。

### 5.2 角色变更流程
1. **查看当前矩阵**  
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     "$API_BASE/v1/workspaces/{workspace_id}/roles" | jq
   ```
2. **创建/更新角色**  
   - 创建：`POST /roles`，Body `{ "name": "...", "operations": ["evaluation_view", ...] }`。  
   - 更新：`PATCH /roles/{roleId}`，只允许修改名称、描述和操作列表；系统角色不可改权限。  
3. **成员授权**  
   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"role_ids":[3,4]}' \
     "$API_BASE/v1/workspaces/{workspace_id}/members/{user_id}/roles"
   ```
   请求成功即刻生效，并写入审计日志 `workspace.role.assignment`。

### 5.3 回滚策略
- 任何角色增删改均产生日志：`workspace.role.created/updated/assignment`，可在审计仓库或数据库查询。  
- 若发生误授权，可使用审计日志中的 `previous_role_ids` 快速恢复：重新调用成员角色接口覆盖回旧集合。  
- 对于误改角色权限，执行 `PATCH /roles/{roleId}` 恢复原有操作集，并在审计日志中留痕。  
- 建议在正式环境变更前导出当前矩阵（保留 JSON 文件），以便批量回滚。

### 5.4 自动化与脚本（TODO）
- 计划提供批量脚本，支持从 JSON/CSV 导入角色定义与成员映射，便于首批配置或灾备恢复。  
- 执行流程：`python scripts/seed_workspace_roles.py --workspace <id> --file roles.json`（待实现）。  
- 脚本需包含 dry-run 与审计对齐检查，确保不会覆盖系统角色核心权限。

> 注意：角色管理操作依赖权限 `approval_manage`。普通成员仅能读取矩阵，如遇 403 需联系工作空间管理员授权。

---

后续若新增模块或脚本，请在本文件追加章节，并同步引用到 Architecture/technical-decisions/Implementation Readiness 报告。
