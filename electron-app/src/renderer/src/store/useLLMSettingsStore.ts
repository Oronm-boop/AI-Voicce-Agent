import { defineStore } from 'pinia'

export type LLMProvider = 'local-agent' | 'local-llm'

interface LLMSettingsState {
  provider: LLMProvider
  localLLMBaseUrl: string
  localLLMModel: string
  localLLMTemperature: number
  localLLMMaxTokens: number
}

const DEFAULT_LOCAL_LLM_URL = 'http://192.168.0.105:8081/v1/'
const DEFAULT_LOCAL_LLM_MODEL = 'Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf'

export const useLLMSettingsStore = defineStore('llmSettings', {
  state: (): LLMSettingsState => ({
    provider: (localStorage.getItem('llm-provider') as LLMProvider) || 'local-agent',
    localLLMBaseUrl: localStorage.getItem('llm-local-url') || DEFAULT_LOCAL_LLM_URL,
    localLLMModel: localStorage.getItem('llm-local-model') || DEFAULT_LOCAL_LLM_MODEL,
    localLLMTemperature: Number(localStorage.getItem('llm-local-temperature') || '0.8'),
    localLLMMaxTokens: Number(localStorage.getItem('llm-local-max-tokens') || '2048')
  }),
  getters: {
    useLocalLLM(state): boolean {
      return state.provider === 'local-llm'
    }
  },
  actions: {
    setProvider(provider: LLMProvider): void {
      this.provider = provider
      localStorage.setItem('llm-provider', provider)
    },
    setLocalLLMBaseUrl(url: string): void {
      this.localLLMBaseUrl = url
      localStorage.setItem('llm-local-url', url)
    },
    setLocalLLMModel(model: string): void {
      this.localLLMModel = model
      localStorage.setItem('llm-local-model', model)
    },
    setLocalLLMTemperature(temp: number): void {
      this.localLLMTemperature = temp
      localStorage.setItem('llm-local-temperature', String(temp))
    },
    setLocalLLMMaxTokens(tokens: number): void {
      this.localLLMMaxTokens = tokens
      localStorage.setItem('llm-local-max-tokens', String(tokens))
    }
  }
})
