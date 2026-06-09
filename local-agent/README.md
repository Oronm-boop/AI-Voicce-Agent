# Local Agent Runtime

本目录是 MVP 的 Python 本地后端。它只负责最小闭环：

- `GET /health`
- `GET /models/status`
- `POST /chat`
- `GET /tasks`
- `POST /tasks`
- `PATCH /tasks/{task_id}`
- `GET /settings`
- `PUT /settings`
- `POST /voice/transcribe`

默认只允许连接本机模型地址，例如 `127.0.0.1` 或 `localhost`，不调用云端大模型。

电脑控制默认通过 Windows-MCP 执行。启动 `local-agent` 前请另开一个 Windows 终端运行：

```powershell
uvx windows-mcp serve --transport streamable-http --host 127.0.0.1 --port 8000
```

对应 `.env` 配置：

```env
WINDOWS_MCP_URL=http://127.0.0.1:8000/mcp/
WINDOWS_MCP_AUTH_TOKEN=
WINDOWS_MCP_TIMEOUT_SECONDS=30
```

工作空间文件增删改查也通过 Windows-MCP 执行：读写、追加、删除、列目录、查询信息走 `FileSystem` 工具，目录创建走 `PowerShell` 工具；后端仍会先校验路径必须位于已选择的工作空间内。

## Agent 工作流

`POST /chat` 内部已接入 LangGraph。当前第一版图节点如下：

```text
understand_request
  -> assistant_reply
  -> generate_task_plan
  -> write_tasks
```

- `understand_request`：识别普通对话或任务规划意图。
- `assistant_reply`：调用本地模型生成面向用户的回复。
- `generate_task_plan`：当用户要“拆任务 / todo / 计划”时生成结构化任务 JSON。
- `write_tasks`：校验后写入 SQLite 任务表。

流式 `/chat` 会额外返回 `workflow` 事件，用于前端展示“正在理解需求、正在生成回复、正在拆解任务”等步骤状态。

## 开发启动

```powershell
cd local-agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## 接口验证

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/models/status

$body = @{ prompt = "你好，用一句话介绍你自己" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8765/chat `
  -ContentType "application/json" `
  -Body $body

$task = @{
  title = "完成任务系统后端"
  description = "实现 SQLite 存储和任务 CRUD API"
  priority = "high"
} | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8765/tasks `
  -ContentType "application/json" `
  -Body $task
Invoke-RestMethod http://127.0.0.1:8765/tasks
```

## Ollama 准备

```powershell
ollama serve
ollama pull qwen2.5:0.5b
```

如果你使用其他本地模型名，修改 `.env` 中的 `LLM_MODEL`。

## Postman 测试 `/chat`

`POST http://127.0.0.1:8765/chat`

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "prompt": "你好，用一句话介绍你自己",
  "max_tokens": 512,
  "think": false
}
```

`qwen2.5:0.5b` 体积小、响应快，适合 MVP 首轮接口联调。后续可以在 `.env` 中把 `LLM_MODEL` 切换为更强的本地模型。

## 流式返回（SSE）

`POST http://127.0.0.1:8765/chat`

Body 示例：

```json
{
  "prompt": "你好，用一句话介绍你自己",
  "stream": true,
  "max_tokens": 512
}
```

返回 `Content-Type: text/event-stream`，事件类型包括：

- `workflow`：LangGraph 工作流步骤状态
- `start`：开始生成
- `delta`：增量文本
- `done`：结束并包含完整 `reply`
- `tasks`：后端已从对话中创建任务
- `error`：错误信息

## 任务 API

当用户在 `/chat` 中表达“拆任务、做计划、生成 todo list”等意图时，后端会额外调用本地模型生成结构化任务 JSON，校验后写入 SQLite。也可以直接使用任务 API：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/tasks
```

## 语音输入接口

`POST /voice/transcribe` 接收前端麦克风音频。当前已接入 sherpa-onnx 离线 ASR，前端会发送 `16kHz mono PCM WAV`，后端转写后返回识别文本。

### 准备 sherpa-onnx ASR

安装依赖：

```powershell
cd local-agent
.\.venv\Scripts\activate
pip install -r requirements.txt
```

下载推荐的 MVP 中文/英文模型：

```powershell
cd local-agent
New-Item -ItemType Directory -Force .\models\asr | Out-Null
Invoke-WebRequest `
  -Uri https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2 `
  -OutFile .\models\asr\sense-voice.tar.bz2
tar -xjf .\models\asr\sense-voice.tar.bz2 -C .\models\asr
Remove-Item .\models\asr\sense-voice.tar.bz2
```

`.env` 中确认以下配置：

```env
ASR_PROVIDER=sherpa-onnx
ASR_MODEL_TYPE=sense_voice
ASR_MODEL=models/asr/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx
ASR_TOKENS=models/asr/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/tokens.txt
ASR_NUM_THREADS=2
ASR_COMPUTE_PROVIDER=cpu
```

如果模型或依赖缺失，接口会返回 `not_configured`，前端会显示对应提示，不会调用云端语音识别。

## Windows 打包（Python 后端 EXE）

```powershell
cd local-agent
.\build_windows.ps1 -Clean
```

产物路径：

```text
local-agent\dist\local-agent-runtime\local-agent-runtime.exe
```
