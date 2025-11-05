# 推理 API 参考

本节概述 Story 5.3 新增的推理接口与 SDK 使用方式。

## REST 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/v1/inference` | 执行同步推理（支持批量输入）。 |
| `GET` | `/api/v1/inference/logs` | 按工作空间查询最近调用日志。 |
| `GET` | `/api/v1/inference/calls/{id}` | 查看单次调用的详细信息（含错误原因、token 统计）。 |
| `POST` | `/api/v1/inference/api-keys` | 创建推理 API Key，响应附带一次性明文；需 `deployment_manage` 权限。 |
| `GET` | `/api/v1/inference/api-keys` | 列出 API Key（状态、配额、最后使用时间）。 |
| `DELETE` | `/api/v1/inference/api-keys/{id}` | 吊销指定 API Key。 |

### 请求示例

```json
POST /api/v1/inference
Authorization: Bearer <token>

{
  "workspace_id": 1,
  "deployment_id": 2,
  "inputs": ["今天的待办是什么？"],
  "parameters": {"temperature": 0.6}
}
```

响应：

```json
{
  "call_id": 15,
  "deployment_id": 2,
  "model_version_id": 7,
  "outputs": [
    {"output": "[deployment:2] 温度=0.60 → 今天的待办是什么？ :: 响应 1"}
  ],
  "latency_ms": 12.7,
  "input_tokens": 6,
  "output_tokens": 14
}
```

> 当请求头包含 `X-LLMFT-API-Key: <secret>` 时，可在无用户 JWT 的情况下调用推理接口；API Key 与工作空间一一对应，限流/配额策略与账号保持一致。

> 429 响应示例：`{"detail": "调用频率超出限制，请稍后重试。"}`，并会在后台写入 `inference.rate_limited` 审计事件与一条 `status=rate_limited` 的调用日志。

### 错误码

| 状态码 | 说明 |
|--------|------|
| `400` | 参数缺失、部署不存在或不处于 Active 状态。 |
| `401` | JWT/ API Key 无效或已吊销。 |
| `403` | 当前身份缺少 `inference_use` 权限。 |
| `404` | 工作空间或部署不存在。 |
| `429` | 触发限流或每日配额限制。 |

## gRPC 接口（摘要）

- Service: `llmft.inference.Inference`
- Method: `rpc Invoke(InvokeRequest) returns (InvokeResponse)`
- 运行时通过 `backend/app/grpc/inference_server.py` 暴露，与 REST 共享限流/日志逻辑；依赖 `grpcio` 与 `protobuf`。
- Proto 文件位置：`backend/app/grpc/inference.proto`

## SDK

### Python (`sdk/python/llmft_client`)

```python
from llmft_client import InferenceClient

client = InferenceClient(base_url="http://localhost:8000", api_key="<secret>")
result = client.invoke(workspace_id=1, deployment_id=2, inputs=["ping"])
print(result.outputs[0].output)
```

### JavaScript (`sdk/js/llmft-client`)

```ts
import { InferenceClient } from '@llmft/inference-client';

const client = new InferenceClient({ baseUrl: 'http://localhost:8000', apiKey: '<secret>' });
const response = await client.invoke({ workspaceId: 1, deploymentId: 2, inputs: ['ping'] });
console.log(response.outputs[0].output);
```

> SDK 示例默认使用 REST 接口；gRPC 使用需依赖官方 `grpc`/`@grpc/grpc-js`，具体示例见各 SDK README。
