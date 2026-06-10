<template>
  <div class="p-container-padding">
    <div class="max-w-4xl mx-auto space-y-8 pb-24">
      <div class="space-y-2">
        <h2 class="font-headline-md text-headline-md text-on-background tracking-tight">设置</h2>
        <p class="font-body-lg text-body-lg text-on-surface-variant">
          管理本地模型、语音偏好与隐私选项。
        </p>
      </div>

      <section class="bg-surface rounded-lg border border-surface-variant p-8 flex flex-col gap-6">
        <header class="flex items-center justify-between gap-4 border-b border-surface-variant pb-4">
          <div class="flex items-center gap-3">
            <MaterialIcon name="memory" :fill="1" :size="24" class="text-primary" />
            <h3 class="font-title-sm text-title-sm text-on-surface">本地模型</h3>
          </div>
          <button
            type="button"
            class="w-10 h-10 rounded-full border border-outline-variant bg-surface-container-lowest flex items-center justify-center text-primary hover:bg-surface-container"
            :disabled="loadingStatus"
            title="刷新模型状态"
            @click="refreshModelStatus"
          >
            <MaterialIcon name="refresh" class="text-[20px]" :class="{ 'animate-spin': loadingStatus }" />
          </button>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <label class="space-y-2">
            <span class="font-body-md text-body-md text-on-surface-variant block">模型服务地址</span>
            <input
              v-model.trim="llmBaseUrl"
              type="text"
              class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              placeholder="http://127.0.0.1:11434"
            />
          </label>

          <label class="space-y-2">
            <span class="font-body-md text-body-md text-on-surface-variant block">模型名称</span>
            <input
              v-model.trim="llmModel"
              type="text"
              class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              placeholder="qwen2.5:0.5b"
            />
          </label>

          <label class="space-y-4">
            <div class="flex justify-between items-center">
              <span class="font-body-md text-body-md text-on-surface-variant block">默认输出长度</span>
              <span class="font-body-md text-body-md text-primary font-medium">{{ defaultMaxTokens }}</span>
            </div>
            <input
              v-model.number="defaultMaxTokens"
              type="range"
              min="64"
              max="8192"
              step="64"
              class="w-full accent-primary"
            />
          </label>

          <div class="flex items-start justify-between gap-4 rounded-lg border border-outline-variant bg-surface-container-lowest p-4">
            <div>
              <h4 class="font-body-lg text-body-lg text-on-surface font-medium">Thinking 输出</h4>
              <p class="font-label-sm text-label-sm text-on-surface-variant mt-1">
                默认关闭，避免思考模型只返回思考内容。
              </p>
            </div>
            <ToggleSwitch v-model="enableThinking" />
          </div>
        </div>

        <div class="rounded-lg border border-outline-variant bg-surface-container-lowest p-4">
          <div class="flex items-center gap-2">
            <span
              class="w-2 h-2 rounded-full"
              :class="modelStatus?.available ? 'bg-primary' : 'bg-error'"
            ></span>
            <span class="font-body-md text-body-md text-on-surface">{{ modelStatusText }}</span>
          </div>
          <p class="font-label-sm text-label-sm text-on-surface-variant mt-2">
            模型配置集中保存在根目录 model_config.json。
          </p>
          <p v-if="modelStatus?.models.length" class="font-label-sm text-label-sm text-outline mt-2">
            已发现模型：{{ modelStatus.models.join('、') }}
          </p>
        </div>
      </section>

      <section class="bg-surface rounded-lg border border-surface-variant p-8 flex flex-col gap-6">
        <header class="flex items-center gap-3 border-b border-surface-variant pb-4">
          <MaterialIcon name="dns" :fill="1" :size="24" class="text-primary" />
          <h3 class="font-title-sm text-title-sm text-on-surface">本地大模型</h3>
        </header>

        <div class="space-y-4">
          <div class="flex items-center gap-4">
            <span class="font-body-md text-body-md text-on-surface-variant">模型提供方</span>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                value="local-agent"
                :checked="llmSettingsStore.provider === 'local-agent'"
                class="accent-primary"
                @change="llmSettingsStore.setProvider('local-agent')"
              />
              <span class="font-body-md text-body-md text-on-surface">内置后端</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                value="local-llm"
                :checked="llmSettingsStore.provider === 'local-llm'"
                class="accent-primary"
                @change="llmSettingsStore.setProvider('local-llm')"
              />
              <span class="font-body-md text-body-md text-on-surface">本地大模型</span>
            </label>
          </div>

          <template v-if="llmSettingsStore.provider === 'local-llm'">
            <label class="space-y-2 block">
              <span class="font-body-md text-body-md text-on-surface-variant block">API 地址 (Completions)</span>
              <input
                :value="llmSettingsStore.localLLMBaseUrl"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="http://192.168.0.105:8081/v1/"
                @input="(e) => llmSettingsStore.setLocalLLMBaseUrl((e.target as HTMLInputElement).value)"
              />
              <p class="font-label-sm text-label-sm text-outline mt-1">
                需要以 /v1/ 结尾，如 http://192.168.0.105:8081/v1/
              </p>
            </label>

            <label class="space-y-2 block">
              <span class="font-body-md text-body-md text-on-surface-variant block">模型名称</span>
              <input
                :value="llmSettingsStore.localLLMModel"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"
                @input="(e) => llmSettingsStore.setLocalLLMModel((e.target as HTMLInputElement).value)"
              />
            </label>

            <div class="grid grid-cols-2 gap-4">
              <label class="space-y-2 block">
                <span class="font-body-md text-body-md text-on-surface-variant block">Temperature</span>
                <input
                  :value="llmSettingsStore.localLLMTemperature"
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                  @input="(e) => llmSettingsStore.setLocalLLMTemperature(Number((e.target as HTMLInputElement).value))"
                />
              </label>
              <label class="space-y-2 block">
                <span class="font-body-md text-body-md text-on-surface-variant block">Max Tokens</span>
                <input
                  :value="llmSettingsStore.localLLMMaxTokens"
                  type="number"
                  min="64"
                  max="32768"
                  step="64"
                  class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                  @input="(e) => llmSettingsStore.setLocalLLMMaxTokens(Number((e.target as HTMLInputElement).value))"
                />
              </label>
            </div>

            <div class="rounded-lg border border-outline-variant bg-surface-container-lowest p-4">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-primary"></span>
                <span class="font-body-md text-body-md text-on-surface">
                  已配置：{{ llmSettingsStore.localLLMModel }} @ {{ llmSettingsStore.localLLMBaseUrl }}
                </span>
              </div>
              <p class="font-label-sm text-label-sm text-on-surface-variant mt-2">
                通过主进程代理调用，无跨域限制。API 需兼容 OpenAI Completions 格式 (/v1/completions)。
              </p>
            </div>
          </template>
        </div>
      </section>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-gutter">
        <section class="bg-surface rounded-lg border border-surface-variant p-8 flex flex-col gap-8">
          <header class="flex items-center gap-3 border-b border-surface-variant pb-4">
            <MaterialIcon name="record_voice_over" :fill="1" :size="24" class="text-primary" />
            <h3 class="font-title-sm text-title-sm text-on-surface">语音设置</h3>
          </header>

          <div class="space-y-6">
            <label class="space-y-2 block">
              <span class="font-body-md text-body-md text-on-surface-variant block">语音音色</span>
              <select
                v-model="voice"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary"
              >
                <option v-for="option in voiceOptions" :key="option" :value="option">{{ option }}</option>
              </select>
            </label>

            <label class="space-y-2 block">
              <span class="font-body-md text-body-md text-on-surface-variant block">唤醒词设定</span>
              <input
                v-model="wakeWord"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary"
              />
            </label>
          </div>
        </section>

        <section class="bg-surface rounded-lg border border-surface-variant p-8 flex flex-col gap-8">
          <header class="flex items-center gap-3 border-b border-surface-variant pb-4">
            <MaterialIcon name="shield" :fill="1" :size="24" class="text-primary" />
            <h3 class="font-title-sm text-title-sm text-on-surface">隐私与安全</h3>
          </header>

          <div class="space-y-6">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h4 class="font-body-lg text-body-lg text-on-surface font-medium">仅本地模型</h4>
                <p class="font-label-sm text-label-sm text-on-surface-variant mt-1">
                  {{ localOnlyText }}
                </p>
              </div>
              <ToggleSwitch :model-value="localOnlyEnabled" />
            </div>

            <label class="space-y-2 block">
              <span class="font-body-md text-body-md text-on-surface-variant block">会话历史自动清理</span>
              <select
                v-model="historyExpire"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary"
              >
                <option value="never">永不</option>
                <option value="7d">7 天后</option>
                <option value="30d">30 天后</option>
              </select>
            </label>
          </div>
        </section>
      </div>

      <p v-if="message" class="font-body-sm text-body-sm" :class="messageType === 'error' ? 'text-error' : 'text-primary'">
        {{ message }}
      </p>

      <div class="flex justify-end gap-4 pt-6 border-t border-surface-variant">
        <button
          type="button"
          class="px-6 py-3 font-title-sm text-title-sm bg-surface text-primary border border-outline-variant rounded-lg hover:bg-surface-container-low transition-colors"
          :disabled="saving"
          @click="resetDefaults"
        >恢复默认</button>
        <button
          type="button"
          class="px-6 py-3 font-title-sm text-title-sm bg-primary text-on-primary rounded-lg hover:bg-on-primary-fixed-variant transition-colors shadow-md disabled:opacity-50"
          :disabled="saving || !canSave"
          @click="saveSettings"
        >{{ saving ? '保存中...' : '保存设置' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import MaterialIcon from '@components/MaterialIcon.vue'
import ToggleSwitch from '@components/ToggleSwitch.vue'
import {
  getAppSettings,
  getModelsStatus,
  updateAppSettings,
  type AppSettingsResponse,
  type ModelStatusResponse
} from '@api/localAgent'
import { useLLMSettingsStore } from '@store/useLLMSettingsStore'

const voiceOptions = ['沉稳男声', '亲切女声', '中性合成'] as const
type VoiceOption = (typeof voiceOptions)[number]

const llmBaseUrl = ref('http://127.0.0.1:11434')
const llmModel = ref('qwen2.5:0.5b')
const enableThinking = ref(false)
const defaultMaxTokens = ref(2048)
const voice = ref<VoiceOption>('沉稳男声')
const wakeWord = ref('你好, Zenith')
const historyExpire = ref<'never' | '7d' | '30d'>('30d')
const loadingStatus = ref(false)
const saving = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error'>('success')
const modelStatus = ref<ModelStatusResponse | null>(null)
const loadedSettings = ref<AppSettingsResponse | null>(null)
const llmSettingsStore = useLLMSettingsStore()

const canSave = computed(() => llmBaseUrl.value.length > 0 && llmModel.value.length > 0)
const localOnlyEnabled = computed(() => !loadedSettings.value?.allow_remote_llm)
const localOnlyText = computed(() => {
  return localOnlyEnabled.value
    ? '大模型推理只允许访问 127.0.0.1、localhost 或 ::1。'
    : '已允许远程模型地址，API Key 请只放在 model_config.json 或环境变量中。'
})

const modelStatusText = computed(() => {
  if (!modelStatus.value) {
    return '模型状态未检查'
  }
  if (!modelStatus.value.available) {
    return `模型服务不可用：${modelStatus.value.error || '未连接'}`
  }
  if (!modelStatus.value.configured_model_present) {
    return `模型服务已连接，但未发现 ${modelStatus.value.configured_model}`
  }
  return `模型已就绪：${modelStatus.value.configured_model}`
})

const applySettings = (settings: AppSettingsResponse): void => {
  loadedSettings.value = settings
  llmBaseUrl.value = settings.llm_base_url
  llmModel.value = settings.llm_model
  enableThinking.value = settings.enable_thinking
  defaultMaxTokens.value = settings.default_max_tokens
}

const showMessage = (text: string, type: 'success' | 'error' = 'success'): void => {
  message.value = text
  messageType.value = type
}

const refreshModelStatus = async (): Promise<void> => {
  loadingStatus.value = true
  try {
    modelStatus.value = await getModelsStatus()
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    showMessage(`模型状态获取失败：${detail}`, 'error')
  } finally {
    loadingStatus.value = false
  }
}

const loadSettings = async (): Promise<void> => {
  try {
    applySettings(await getAppSettings())
    await refreshModelStatus()
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    showMessage(`设置加载失败：${detail}`, 'error')
  }
}

const resetDefaults = (): void => {
  llmBaseUrl.value = 'http://127.0.0.1:11434'
  llmModel.value = 'qwen2.5:0.5b'
  enableThinking.value = false
  defaultMaxTokens.value = 2048
  voice.value = '沉稳男声'
  wakeWord.value = '你好, Zenith'
  historyExpire.value = '30d'
}

const saveSettings = async (): Promise<void> => {
  saving.value = true
  message.value = ''
  try {
    const settings = await updateAppSettings({
      llm_base_url: llmBaseUrl.value,
      llm_model: llmModel.value,
      enable_thinking: enableThinking.value,
      default_max_tokens: defaultMaxTokens.value
    })
    applySettings(settings)
    await refreshModelStatus()
    showMessage('设置已保存')
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    showMessage(`设置保存失败：${detail}`, 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSettings()
})
</script>
