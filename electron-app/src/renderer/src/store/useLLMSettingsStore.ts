import { defineStore } from 'pinia'

/**
 * Three model source types the user can choose from.
 *  - lan-machine : 局域网 AI 一体机 (OpenAI-compatible)
 *  - local-ollama: 本地 Ollama
 *  - cloud       : 云端大模型 (OpenAI-compatible + API Key)
 */
export type ModelSource = 'lan-machine' | 'local-ollama' | 'cloud'

/** Pre-defined cloud provider shortcuts. */
export interface CloudPreset {
  label: string
  baseUrl: string
}

export const CLOUD_PRESETS: CloudPreset[] = [
  { label: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1' },
  { label: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
  { label: '智谱 AI (GLM)', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  { label: '通义千问 (Qwen)', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' }
]

interface LLMSettingsState {
  modelSource: ModelSource

  // --- 局域网 AI 一体机 ---
  lanIp: string
  lanPort: string
  lanModel: string

  // --- 本地 Ollama ---
  ollamaIp: string
  ollamaPort: string
  ollamaModel: string

  // --- 云端大模型 ---
  cloudBaseUrl: string
  cloudModel: string
  cloudApiKey: string
  cloudPresetIndex: number // -1 = custom

  // --- 公共 ---
  enableThinking: boolean
  defaultMaxTokens: number
}

function loadStr(key: string, fallback: string): string {
  return localStorage.getItem(key) ?? fallback
}
function loadNum(key: string, fallback: number): number {
  const v = localStorage.getItem(key)
  return v !== null ? Number(v) : fallback
}
function loadBool(key: string, fallback: boolean): boolean {
  const v = localStorage.getItem(key)
  return v !== null ? v === 'true' : fallback
}

export const useLLMSettingsStore = defineStore('llmSettings', {
  state: (): LLMSettingsState => ({
    modelSource: (loadStr('llm-model-source', 'local-ollama') as ModelSource),

    lanIp: loadStr('llm-lan-ip', ''),
    lanPort: loadStr('llm-lan-port', ''),
    lanModel: loadStr('llm-lan-model', ''),

    ollamaIp: loadStr('llm-ollama-ip', '127.0.0.1'),
    ollamaPort: loadStr('llm-ollama-port', '11434'),
    ollamaModel: loadStr('llm-ollama-model', 'qwen2.5:0.5b'),

    cloudBaseUrl: loadStr('llm-cloud-base-url', CLOUD_PRESETS[0].baseUrl),
    cloudModel: loadStr('llm-cloud-model', ''),
    cloudApiKey: loadStr('llm-cloud-api-key', ''),
    cloudPresetIndex: loadNum('llm-cloud-preset-index', 0),

    enableThinking: loadBool('llm-enable-thinking', false),
    defaultMaxTokens: loadNum('llm-default-max-tokens', 2048)
  }),

  getters: {
    /** Compute the effective base URL for the selected source. */
    effectiveBaseUrl(state): string {
      switch (state.modelSource) {
        case 'lan-machine':
          return state.lanIp && state.lanPort
            ? `http://${state.lanIp}:${state.lanPort}/v1`
            : ''
        case 'local-ollama':
          return `http://${state.ollamaIp}:${state.ollamaPort}`
        case 'cloud':
          return state.cloudBaseUrl
      }
    },

    /** Compute the effective model name. */
    effectiveModel(state): string {
      switch (state.modelSource) {
        case 'lan-machine':
          return state.lanModel
        case 'local-ollama':
          return state.ollamaModel
        case 'cloud':
          return state.cloudModel
      }
    },

    /** Compute the provider string for the backend. */
    effectiveProvider(state): string {
      return state.modelSource === 'local-ollama' ? 'ollama' : 'openai_compatible'
    },

    /** Compute the effective allow remote config. */
    effectiveAllowRemote(state): boolean {
      return state.modelSource !== 'local-ollama'
    },

    /** Compatibility getter for ChatView.vue. Always false in the new design. */
    useLocalLLM(): boolean {
      return false
    },

    /** Compatibility getter for ChatView.vue. */
    localLLMModel(): string {
      return this.effectiveModel
    },

    /** Compatibility getter for ChatView.vue. */
    localLLMBaseUrl(): string {
      return this.effectiveBaseUrl
    },

    /** Compatibility getter for ChatView.vue. */
    localLLMTemperature(): number {
      return 0.8
    },

    /** Compatibility getter for ChatView.vue. */
    localLLMMaxTokens(): number {
      return this.defaultMaxTokens
    }
  },

  actions: {
    /** Persist a single key. */
    _save(key: string, value: string | number | boolean): void {
      localStorage.setItem(key, String(value))
    },

    setModelSource(source: ModelSource): void {
      this.modelSource = source
      this._save('llm-model-source', source)
    },

    // --- LAN ---
    setLanIp(v: string): void { this.lanIp = v; this._save('llm-lan-ip', v) },
    setLanPort(v: string): void { this.lanPort = v; this._save('llm-lan-port', v) },
    setLanModel(v: string): void { this.lanModel = v; this._save('llm-lan-model', v) },

    // --- Ollama ---
    setOllamaIp(v: string): void { this.ollamaIp = v; this._save('llm-ollama-ip', v) },
    setOllamaPort(v: string): void { this.ollamaPort = v; this._save('llm-ollama-port', v) },
    setOllamaModel(v: string): void { this.ollamaModel = v; this._save('llm-ollama-model', v) },

    // --- Cloud ---
    setCloudBaseUrl(v: string): void { this.cloudBaseUrl = v; this._save('llm-cloud-base-url', v) },
    setCloudModel(v: string): void { this.cloudModel = v; this._save('llm-cloud-model', v) },
    setCloudApiKey(v: string): void { this.cloudApiKey = v; this._save('llm-cloud-api-key', v) },
    setCloudPresetIndex(i: number): void {
      this.cloudPresetIndex = i
      this._save('llm-cloud-preset-index', i)
      if (i >= 0 && i < CLOUD_PRESETS.length) {
        this.setCloudBaseUrl(CLOUD_PRESETS[i].baseUrl)
      }
    },

    // --- Common ---
    setEnableThinking(v: boolean): void { this.enableThinking = v; this._save('llm-enable-thinking', v) },
    setDefaultMaxTokens(v: number): void { this.defaultMaxTokens = v; this._save('llm-default-max-tokens', v) },

    /**
     * Build the payload object that matches `AppSettingsUpdate` for saving to backend.
     */
    buildSavePayload(): Record<string, unknown> {
      const payload: Record<string, unknown> = {
        llm_provider: this.effectiveProvider,
        llm_base_url: this.effectiveBaseUrl,
        llm_model: this.effectiveModel,
        allow_remote_llm: this.effectiveAllowRemote,
        enable_thinking: this.enableThinking,
        default_max_tokens: this.defaultMaxTokens
      }
      if (this.modelSource === 'cloud' && this.cloudApiKey) {
        payload.llm_api_key = this.cloudApiKey
      }
      return payload
    },

    /**
     * Apply settings loaded from backend to the local store.
     * Called after GET /settings to sync.
     */
    applyFromBackend(settings: {
      llm_provider: string
      llm_base_url: string
      llm_model: string
      allow_remote_llm: boolean
      has_api_key: boolean
      enable_thinking: boolean
      default_max_tokens: number
    }): void {
      this.setEnableThinking(settings.enable_thinking)
      this.setDefaultMaxTokens(settings.default_max_tokens)

      // Infer model source from backend provider + allow_remote_llm
      if (settings.llm_provider === 'ollama') {
        // Parse URL to extract IP and port
        try {
          const url = new URL(settings.llm_base_url)
          this.setOllamaIp(url.hostname)
          this.setOllamaPort(url.port || '11434')
        } catch {
          // If URL parsing fails, just keep existing values
        }
        this.setOllamaModel(settings.llm_model)
        this.setModelSource('local-ollama')
      } else if (settings.allow_remote_llm && settings.has_api_key) {
        // Cloud model (remote + has API key)
        this.setCloudBaseUrl(settings.llm_base_url)
        this.setCloudModel(settings.llm_model)
        // Find matching preset
        const idx = CLOUD_PRESETS.findIndex((p) => settings.llm_base_url.startsWith(p.baseUrl))
        this.setCloudPresetIndex(idx)
        if (idx >= 0) {
          // Don't overwrite the baseUrl from preset
        }
        this.setModelSource('cloud')
      } else if (settings.allow_remote_llm) {
        // LAN machine (remote, no API key)
        try {
          const url = new URL(settings.llm_base_url)
          this.setLanIp(url.hostname)
          this.setLanPort(url.port || '8081')
        } catch {
          // keep existing
        }
        this.setLanModel(settings.llm_model)
        this.setModelSource('lan-machine')
      } else {
        // Default to local ollama
        try {
          const url = new URL(settings.llm_base_url)
          this.setOllamaIp(url.hostname)
          this.setOllamaPort(url.port || '11434')
        } catch {
          // keep existing
        }
        this.setOllamaModel(settings.llm_model)
        this.setModelSource('local-ollama')
      }
    },

    /** Reset all settings to defaults. */
    resetAll(): void {
      this.setModelSource('local-ollama')
      this.setLanIp('')
      this.setLanPort('')
      this.setLanModel('')
      this.setOllamaIp('127.0.0.1')
      this.setOllamaPort('11434')
      this.setOllamaModel('qwen2.5:0.5b')
      this.setCloudBaseUrl(CLOUD_PRESETS[0].baseUrl)
      this.setCloudModel('')
      this.setCloudApiKey('')
      this.setCloudPresetIndex(0)
      this.setEnableThinking(false)
      this.setDefaultMaxTokens(2048)
    }
  }
})
