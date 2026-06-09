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

export interface AppSettingsResponse {
  llm_provider: string
  llm_base_url: string
  llm_model: string
  allow_remote_llm: boolean
  enable_thinking: boolean
  default_max_tokens: number
  workspace_path: string
  data_dir: string
}

export interface AppSettingsUpdate {
  llm_provider?: string
  llm_base_url?: string
  llm_model?: string
  allow_remote_llm?: boolean
  llm_api_key?: string
  llm_api_key_env?: string
  enable_thinking?: boolean
  default_max_tokens?: number
  request_timeout_seconds?: number
  workspace_path?: string
}

export interface VoiceTranscriptionResponse {
  status: 'ok' | 'not_configured' | 'error'
  transcript: string
  message: string
  audio_bytes: number
}

export interface ChatRequest {
  prompt?: string
  messages?: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>
  model?: string
  temperature?: number
  max_tokens?: number
  think?: boolean
  stream?: boolean
}

export interface ChatResponse {
  request_id: string
  model: string
  provider: string
  reply: string
  tasks_created?: TaskItem[]
  computer_actions?: ComputerActionResult[]
  file_actions?: FileActionResult[]
  workflow_events?: AgentWorkflowEvent[]
}

export interface AgentWorkflowEvent {
  step: string
  status: 'running' | 'completed' | 'skipped' | 'error'
  message: string
}

export interface ComputerActionResult {
  tool: string
  status: 'success' | 'error' | 'skipped' | 'confirm_required'
  message: string
  details: Record<string, unknown>
}

export interface FileActionResult {
  action: string
  status: 'success' | 'error' | 'skipped'
  message: string
  path: string
  details: Record<string, unknown>
}

export interface TaskItem {
  id: string
  title: string
  description: string
  status: 'todo' | 'in_progress' | 'done'
  priority: 'low' | 'medium' | 'high'
  progress: number
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  title: string
  description?: string
  status?: TaskItem['status']
  priority?: TaskItem['priority']
  progress?: number
}

export interface TaskUpdate {
  title?: string
  description?: string
  status?: TaskItem['status']
  priority?: TaskItem['priority']
  progress?: number
}

export interface ChatStreamEvent {
  type:
    | 'start'
    | 'delta'
    | 'done'
    | 'error'
    | 'tasks'
    | 'workflow'
    | 'computer_actions'
    | 'file_actions'
  request_id: string
  model?: string
  provider?: string
  delta?: string
  reply?: string
  error?: string
  tasks_created?: TaskItem[]
  computer_actions?: ComputerActionResult[]
  file_actions?: FileActionResult[]
  workflow_step?: string
  workflow_status?: AgentWorkflowEvent['status']
  message?: string
}

function formatErrorDetail(detail: unknown): string {
  if (!detail) {
    return ''
  }
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail.map(formatErrorDetail).filter(Boolean).join('；')
  }
  if (typeof detail === 'object') {
    const payload = detail as Record<string, unknown>
    const message = payload.msg || payload.message || payload.detail
    if (message) {
      const location = Array.isArray(payload.loc) ? payload.loc.join('.') : ''
      const text = formatErrorDetail(message)
      return location ? `${location}: ${text}` : text
    }

    try {
      return JSON.stringify(payload)
    } catch {
      return String(payload)
    }
  }

  return String(detail)
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T
  }

  let detail = response.statusText
  try {
    const errorData = (await response.json()) as { detail?: unknown }
    if (errorData.detail) {
      detail = formatErrorDetail(errorData.detail)
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

export const getAppSettings = (): Promise<AppSettingsResponse> =>
  request<AppSettingsResponse>('/settings')

export const updateAppSettings = (
  payload: AppSettingsUpdate
): Promise<AppSettingsResponse> =>
  request<AppSettingsResponse>('/settings', {
    method: 'PUT',
    body: JSON.stringify(payload)
  })

export const sendChat = (payload: ChatRequest): Promise<ChatResponse> =>
  request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(payload)
  })

export const getTasks = (): Promise<TaskItem[]> => request<TaskItem[]>('/tasks')

export const createTask = (payload: TaskCreate): Promise<TaskItem> =>
  request<TaskItem>('/tasks', {
    method: 'POST',
    body: JSON.stringify(payload)
  })

export const updateTask = (taskId: string, payload: TaskUpdate): Promise<TaskItem> =>
  request<TaskItem>(`/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })

export const transcribeVoice = async (audio: Blob): Promise<VoiceTranscriptionResponse> => {
  const response = await fetch(`${agentBaseUrl}/voice/transcribe`, {
    method: 'POST',
    headers: {
      'Content-Type': audio.type || 'application/octet-stream'
    },
    body: audio
  })
  return parseResponse<VoiceTranscriptionResponse>(response)
}

export const sendChatStream = async (
  payload: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void
): Promise<ChatResponse> => {
  const response = await fetch(`${agentBaseUrl}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream'
    },
    body: JSON.stringify({
      ...payload,
      stream: true
    })
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const errorData = (await response.json()) as { detail?: unknown }
      if (errorData.detail) {
        detail = formatErrorDetail(errorData.detail)
      }
    } catch {
      // Ignore parsing error and fallback to status text.
    }
    throw new Error(detail || 'Request failed')
  }

  if (!response.body) {
    throw new Error('Streaming is not supported in this environment.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let requestId = ''
  let model = payload.model || ''
  let provider = 'ollama'
  let reply = ''
  let done = false

  const consumeEventBlock = (block: string): void => {
    const data = block
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n')

    if (!data) {
      return
    }

    const event = JSON.parse(data) as ChatStreamEvent
    onEvent(event)

    if (event.request_id) {
      requestId = event.request_id
    }
    if (event.model) {
      model = event.model
    }
    if (event.provider) {
      provider = event.provider
    }

    if (event.type === 'delta' && event.delta) {
      reply += event.delta
    }

    if (event.type === 'done') {
      reply = event.reply ?? reply
      done = true
    }

    if (event.type === 'error') {
      throw new Error(event.error || 'Streaming request failed.')
    }
  }

  while (true) {
    const { value, done: streamDone } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !streamDone })

    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      consumeEventBlock(block)
    }

    if (streamDone) {
      if (buffer.trim()) {
        consumeEventBlock(buffer)
      }
      break
    }
  }

  if (!done && !reply) {
    throw new Error('Streaming completed without a valid reply.')
  }

  return {
    request_id: requestId,
    model,
    provider,
    reply
  }
}
