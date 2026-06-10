export interface LocalLLMCompleteParams {
  baseUrl: string
  prompt: string
  model?: string
  temperature?: number
  maxTokens?: number
}

export interface LocalLLMCompleteResult {
  text: string
  model: string
  usage: {
    promptTokens: number
    completionTokens: number
    totalTokens: number
  }
}

export interface LocalLLMStreamEvent {
  type: 'start' | 'delta' | 'done' | 'error'
  request_id: string
  model?: string
  provider?: string
  delta?: string
  reply?: string
  error?: string
}

function getApi() {
  if (!window.api?.localLLM) {
    throw new Error('Local LLM API is not available. Please ensure the preload script is loaded.')
  }
  return window.api.localLLM
}

export interface LocalLLMStreamCallbacks {
  onStart?: (requestId: string, model: string) => void
  onDelta?: (delta: string) => void
  onDone?: (reply: string, model: string) => void
  onError?: (error: string) => void
}

export const sendLocalLLMStream = async (
  baseUrl: string,
  prompt: string,
  options: {
    model?: string
    temperature?: number
    maxTokens?: number
  },
  callbacks: LocalLLMStreamCallbacks
): Promise<LocalLLMCompleteResult> => {
  const api = getApi()
  const { model, temperature, maxTokens } = options

  const removeListener = api.onStreamEvent((event: LocalLLMStreamEvent) => {
    switch (event.type) {
      case 'start':
        callbacks.onStart?.(event.request_id, event.model || model || 'unknown')
        break
      case 'delta':
        if (event.delta) {
          callbacks.onDelta?.(event.delta)
        }
        break
      case 'done':
        callbacks.onDone?.(event.reply || '', event.model || model || 'unknown')
        break
      case 'error':
        callbacks.onError?.(event.error || 'Unknown error')
        break
    }
  })

  try {
    const result = await api.completeStream({
      baseUrl,
      prompt,
      model,
      temperature,
      maxTokens
    })
    return result
  } finally {
    removeListener()
  }
}

export const buildPromptFromMessages = (
  messages: Array<{ role: string; content: string }>
): string => {
  // Convert chat messages to a single prompt string for completions API
  let prompt = ''
  for (const msg of messages) {
    if (msg.role === 'system') {
      prompt += `<|system|>\n${msg.content}\n`
    } else if (msg.role === 'user') {
      prompt += `<|user|>\n${msg.content}\n`
    } else if (msg.role === 'assistant') {
      prompt += `<|assistant|>\n${msg.content}\n`
    }
  }
  prompt += '<|assistant|>\n'
  return prompt
}
