const DEFAULT_AGENT_BASE_URL = 'http://127.0.0.1:8765'

const agentBaseUrl = (
  import.meta.env.VITE_AGENT_BASE_URL || DEFAULT_AGENT_BASE_URL
).replace(/\/+$/, '')

export interface HealthResponse {
  status: string
  service: string
  version: string
  time: string
  llm_provider: string
  allow_remote_llm: boolean
}

export interface ModelStatusResponse {
  provider: string
  base_url: string
  available: boolean
  configured_model: string
  configured_model_present: boolean
  models: string[]
  error: string | null
  local_only: boolean
}

export interface ChatRequest {
  prompt?: string
  messages?: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>
  model?: string
  temperature?: number
  max_tokens?: number
  think?: boolean
}

export interface ChatResponse {
  request_id: string
  model: string
  provider: string
  reply: string
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T
  }

  let detail = response.statusText
  try {
    const errorData = (await response.json()) as { detail?: string }
    if (errorData.detail) {
      detail = errorData.detail
    }
  } catch {
    // Ignore parsing error and fallback to status text.
  }

  throw new Error(detail || 'Request failed')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${agentBaseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {})
    }
  })
  return parseResponse<T>(response)
}

export const getHealth = (): Promise<HealthResponse> => request<HealthResponse>('/health')

export const getModelsStatus = (): Promise<ModelStatusResponse> =>
  request<ModelStatusResponse>('/models/status')

export const sendChat = (payload: ChatRequest): Promise<ChatResponse> =>
  request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
