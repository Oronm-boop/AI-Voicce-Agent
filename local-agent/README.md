# Local Agent Runtime

本目录是 MVP 的 Python 本地后端。它只负责最小闭环：

- `GET /health`
- `GET /models/status`
- `POST /chat`

默认只允许连接本机模型地址，例如 `127.0.0.1` 或 `localhost`，不调用云端大模型。

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
  "max_tokens": 128,
  "think": false
}
```

`qwen2.5:0.5b` 体积小、响应快，适合 MVP 首轮接口联调。后续可以在 `.env` 中把 `LLM_MODEL` 切换为更强的本地模型。
