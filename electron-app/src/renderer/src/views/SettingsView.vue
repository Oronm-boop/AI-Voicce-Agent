<template>
  <div class="p-container-padding">
    <div class="max-w-4xl mx-auto space-y-8 pb-24">
      <div class="space-y-2">
        <h2 class="font-headline-md text-headline-md text-on-background tracking-tight">设置</h2>
        <p class="font-body-lg text-body-lg text-on-surface-variant">
          管理模型服务来源、语音偏好与隐私安全选项。
        </p>
      </div>

      <!-- Unified Model Config Section -->
      <section class="bg-surface rounded-lg border border-surface-variant p-8 flex flex-col gap-6 shadow-sm">
        <header class="flex items-center justify-between gap-4 border-b border-surface-variant pb-4">
          <div class="flex items-center gap-3">
            <MaterialIcon name="settings_suggest" :fill="1" :size="24" class="text-primary" />
            <h3 class="font-title-sm text-title-sm text-on-surface">大模型调用设置</h3>
          </div>
          <button
            type="button"
            class="w-10 h-10 rounded-full border border-outline-variant bg-surface-container-lowest flex items-center justify-center text-primary hover:bg-surface-container transition-all"
            :disabled="loadingStatus"
            title="刷新模型状态"
            @click="refreshModelStatus"
          >
            <MaterialIcon name="refresh" class="text-[20px]" :class="{ 'animate-spin': loadingStatus }" />
          </button>
        </header>

        <!-- Model Source Selector Cards -->
        <div class="space-y-3">
          <span class="font-body-md text-body-md text-on-surface-variant block font-medium">模型来源选择</span>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- LAN Machine Card -->
            <div
              class="border rounded-xl p-5 flex flex-col gap-3 cursor-pointer transition-all duration-200 select-none bg-surface-container-lowest"
              :class="modelSource === 'lan-machine'
                ? 'border-primary ring-2 ring-primary/20 bg-primary/[0.03]'
                : 'border-outline-variant hover:border-outline hover:bg-surface-container-low'"
              @click="modelSource = 'lan-machine'"
            >
              <div class="flex items-center justify-between">
                <MaterialIcon
                  name="dns"
                  :size="28"
                  :class="modelSource === 'lan-machine' ? 'text-primary' : 'text-on-surface-variant'"
                />
                <span
                  v-if="modelSource === 'lan-machine'"
                  class="w-2 h-2 rounded-full bg-primary"
                ></span>
              </div>
              <div>
                <h4 class="font-body-lg text-body-lg text-on-surface font-semibold">局域网 AI 一体机</h4>
                <p class="font-label-sm text-label-sm text-on-surface-variant mt-1 leading-normal">
                  适用于局域网内部部署的专用硬件大模型设备，支持自定义 IP 与端口。
                </p>
              </div>
            </div>

            <!-- Local Ollama Card -->
            <div
              class="border rounded-xl p-5 flex flex-col gap-3 cursor-pointer transition-all duration-200 select-none bg-surface-container-lowest"
              :class="modelSource === 'local-ollama'
                ? 'border-primary ring-2 ring-primary/20 bg-primary/[0.03]'
                : 'border-outline-variant hover:border-outline hover:bg-surface-container-low'"
              @click="modelSource = 'local-ollama'"
            >
              <div class="flex items-center justify-between">
                <MaterialIcon
                  name="memory"
                  :size="28"
                  :class="modelSource === 'local-ollama' ? 'text-primary' : 'text-on-surface-variant'"
                />
                <span
                  v-if="modelSource === 'local-ollama'"
                  class="w-2 h-2 rounded-full bg-primary"
                ></span>
              </div>
              <div>
                <h4 class="font-body-lg text-body-lg text-on-surface font-semibold">本地 Ollama</h4>
                <p class="font-label-sm text-label-sm text-on-surface-variant mt-1 leading-normal">
                  适用于本机运行的 Ollama 实例，延迟低且完全本地隐私。
                </p>
              </div>
            </div>

            <!-- Cloud Card -->
            <div
              class="border rounded-xl p-5 flex flex-col gap-3 cursor-pointer transition-all duration-200 select-none bg-surface-container-lowest"
              :class="modelSource === 'cloud'
                ? 'border-primary ring-2 ring-primary/20 bg-primary/[0.03]'
                : 'border-outline-variant hover:border-outline hover:bg-surface-container-low'"
              @click="modelSource = 'cloud'"
            >
              <div class="flex items-center justify-between">
                <MaterialIcon
                  name="cloud"
                  :size="28"
                  :class="modelSource === 'cloud' ? 'text-primary' : 'text-on-surface-variant'"
                />
                <span
                  v-if="modelSource === 'cloud'"
                  class="w-2 h-2 rounded-full bg-primary"
                ></span>
              </div>
              <div>
                <h4 class="font-body-lg text-body-lg text-on-surface font-semibold">云端大模型</h4>
                <p class="font-label-sm text-label-sm text-on-surface-variant mt-1 leading-normal">
                  提供商托管的云端大模型 API 访问，支持快捷服务商预设，需填 API Key。
                </p>
               </div>
            </div>
          </div>
        </div>

        <!-- Forms Container -->
        <div class="border-t border-surface-variant pt-6">
          <!-- LAN Machine Form -->
          <div v-if="modelSource === 'lan-machine'" class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <label class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">局域网 IP 地址</span>
              <input
                v-model.trim="lanIp"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="如: 192.168.0.105"
              />
            </label>
            <label class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">服务   端口</span>
              <input
                v-model.trim="lanPort"
                type="tvext"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="如: 8081"
              />
            </label>
            <label class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">一体机模型名称</span>
              <input
                v-model.trim="lanModel"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="如: Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"
              />
            </label>
          </div>

          <!-- Local Ollama Form -->
          <div v-else-if="modelSource === 'local-ollama'" class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <label class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">本地 IP 地址</span>
              <input
                v-model.trim="ollamaIp"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="127.0.0.1"
              />
            </label>
            <label class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">Ollama 端口</span>
              <input
                v-model.trim="ollamaPort"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="11434"
              />
            </label>
            <label class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">本地模型名称</span>
              <input
                v-model.trim="ollamaModel"
                type="text"
                class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="如: qwen2.5:0.5b"
              />
            </label>
          </div>

          <!-- Cloud Form -->
          <div v-else-if="modelSource === 'cloud'" class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <!-- Provider URL -->
              <div class="space-y-2 flex flex-col justify-end">
                <span class="font-body-md text-body-md text-on-surface-variant block">服务商 API 地址 (Completions)</span>
                <input
                  v-model.trim="cloudBaseUrl"
                  type="text"
                  class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                  placeholder="如: https://api.deepseek.com/v1"
                />
              </div>

              <!-- Model Name -->
              <div class="space-y-2 flex flex-col justify-end">
                <span class="font-body-md text-body-md text-on-surface-variant block">云端模型名称</span>
                <input
                  v-model.trim="cloudModel"
                  type="text"
                  class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                  placeholder="如: deepseek-chat"
                />
              </div>
            </div>

            <!-- Presets tag row -->
            <div class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">常见服务商快捷预设</span>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="(preset, idx) in CLOUD_PRESETS"
                  :key="preset.label"
                  type="button"
                  class="px-3.5 py-1.5 text-[13px] rounded-full border transition-all duration-200"
                  :class="cloudPresetIndex === idx
                    ? 'bg-primary border-primary text-on-primary font-medium shadow-sm'
                    : 'border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:border-outline hover:bg-surface-container-low'"
                  @click="selectCloudPreset(idx)"
                >
                  {{ preset.label }}
                </button>
                <button
                  type="button"
                  class="px-3.5 py-1.5 text-[13px] rounded-full border transition-all duration-200"
                  :class="cloudPresetIndex === -1
                    ? 'bg-primary border-primary text-on-primary font-medium shadow-sm'
                    : 'border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:border-outline hover:bg-surface-container-low'"
                  @click="selectCloudPreset(-1)"
                >
                  自定义
                </button>
              </div>
            </div>

            <!-- API Key Input -->
            <div class="space-y-2">
              <span class="font-body-md text-body-md text-on-surface-variant block">API Key</span>
              <div class="relative">
                <input
                  v-model="cloudApiKey"
                  :type="showApiKey ? 'text' : 'password'"
                  class="w-full bg-surface-bright border border-surface-variant rounded-lg pl-4 pr-12 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                  :placeholder="hasSavedApiKey ? '•••••••• (已保存，如需修改请在此处输入新 Key)' : '请输入 API Key'"
                />
                <button
                  type="button"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-primary transition-colors flex items-center justify-center w-8 h-8 rounded-full"
                  @click="showApiKey = !showApiKey"
                >
                  <MaterialIcon :name="showApiKey ? 'visibility_off' : 'visibility'" :size="20" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Global LLM common settings (Thinking & output limit) -->
        <div class="border-t border-surface-variant pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
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

        <!-- Status Panel -->
        <div class="rounded-lg border border-outline-variant bg-surface-container-lowest p-4">
          <div class="flex items-center gap-2">
            <span
              class="w-2 h-2 rounded-full"
              :class="modelStatus?.available ? 'bg-primary animate-pulse' : 'bg-error'"
            ></span>
            <span class="font-body-md text-body-md text-on-surface font-medium">{{ modelStatusText }}</span>
          </div>
          <p class="font-label-sm text-label-sm text-on-surface-variant mt-2 leading-relaxed">
            模型配置集中保存在根目录 model_config.json。
          </p>
          <p v-if="modelStatus?.models.length" class="font-label-sm text-label-sm text-outline mt-2 leading-normal">
            已发现模型：{{ modelStatus.models.join('、') }}
          </p>
        </div>
      </section>

      <!-- Voice preferences & privacy sections -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-gutter">
        <section class="bg-surface rounded-lg border border-surface-variant p-8 flex flex-col gap-8 shadow-sm">
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

        <section class="bg-surface rounded-lg border border-surface-variant p-8 flex flex-col gap-8 shadow-sm">
          <header class="flex items-center gap-3 border-b border-surface-variant pb-4">
            <MaterialIcon name="shield" :fill="1" :size="24" class="text-primary" />
            <h3 class="font-title-sm text-title-sm text-on-surface">隐私与安全</h3>
          </header>

          <div class="space-y-6">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h4 class="font-body-lg text-body-lg text-on-surface font-medium">仅本地模型</h4>
                <p class="font-label-sm text-label-sm text-on-surface-variant mt-1 leading-normal">
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

      <!-- Feedback Messages -->
      <p v-if="message" class="font-body-sm text-body-sm px-2 animate-fade-in-up" :class="messageType === 'error' ? 'text-error' : 'text-primary'">
        {{ message }}
      </p>

      <!-- Action Footer -->
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
import { useLLMSettingsStore, CLOUD_PRESETS, type ModelSource } from '@store/useLLMSettingsStore'

const voiceOptions = ['沉稳男声', '亲切女声', '中性合成'] as const
type VoiceOption = (typeof voiceOptions)[number]

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

// --- Form States ---
const modelSource = ref<ModelSource>('local-ollama')

const lanIp = ref('')
const lanPort = ref('')
const lanModel = ref('')

const ollamaIp = ref('127.0.0.1')
const ollamaPort = ref('11434')
const ollamaModel = ref('qwen2.5:0.5b')

const cloudBaseUrl = ref('')
const cloudModel = ref('')
const cloudApiKey = ref('')
const cloudPresetIndex = ref(0)
const showApiKey = ref(false)
const hasSavedApiKey = ref(false)

const enableThinking = ref(false)
const defaultMaxTokens = ref(2048)

// Validation
const canSave = computed(() => {
  if (modelSource.value === 'lan-machine') {
    return lanIp.value.trim().length > 0 && lanPort.value.trim().length > 0 && lanModel.value.trim().length > 0
  }
  if (modelSource.value === 'local-ollama') {
    return ollamaIp.value.trim().length > 0 && ollamaPort.value.trim().length > 0 && ollamaModel.value.trim().length > 0
  }
  if (modelSource.value === 'cloud') {
    const hasUrlAndModel = cloudBaseUrl.value.trim().length > 0 && cloudModel.value.trim().length > 0
    const keyOk = cloudApiKey.value.length > 0 || hasSavedApiKey.value
    return hasUrlAndModel && keyOk
  }
  return false
})

const localOnlyEnabled = computed(() => modelSource.value === 'local-ollama')
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

const selectCloudPreset = (idx: number): void => {
  cloudPresetIndex.value = idx
  if (idx >= 0 && idx < CLOUD_PRESETS.length) {
    cloudBaseUrl.value = CLOUD_PRESETS[idx].baseUrl
  }
}

const applySettings = (settings: AppSettingsResponse): void => {
  loadedSettings.value = settings
  hasSavedApiKey.value = settings.has_api_key

  // Apply to local store first
  llmSettingsStore.applyFromBackend(settings)

  // Copy from store to local form state
  modelSource.value = llmSettingsStore.modelSource

  lanIp.value = llmSettingsStore.lanIp
  lanPort.value = llmSettingsStore.lanPort
  lanModel.value = llmSettingsStore.lanModel

  ollamaIp.value = llmSettingsStore.ollamaIp
  ollamaPort.value = llmSettingsStore.ollamaPort
  ollamaModel.value = llmSettingsStore.ollamaModel

  cloudBaseUrl.value = llmSettingsStore.cloudBaseUrl
  cloudModel.value = llmSettingsStore.cloudModel
  cloudPresetIndex.value = llmSettingsStore.cloudPresetIndex
  cloudApiKey.value = '' // never prefilled from backend for security

  enableThinking.value = llmSettingsStore.enableThinking
  defaultMaxTokens.value = llmSettingsStore.defaultMaxTokens
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
  modelSource.value = 'local-ollama'
  lanIp.value = ''
  lanPort.value = ''
  lanModel.value = ''
  ollamaIp.value = '127.0.0.1'
  ollamaPort.value = '11434'
  ollamaModel.value = 'qwen2.5:0.5b'
  cloudBaseUrl.value = CLOUD_PRESETS[0].baseUrl
  cloudModel.value = ''
  cloudApiKey.value = ''
  cloudPresetIndex.value = 0
  enableThinking.value = false
  defaultMaxTokens.value = 2048

  voice.value = '沉稳男声'
  wakeWord.value = '你好, Zenith'
  historyExpire.value = '30d'
  showMessage('已恢复默认配置值（点击保存后生效）')
}

const saveSettings = async (): Promise<void> => {
  saving.value = true
  message.value = ''
  try {
    // 1. Sync local form states to Pinia store so store getters work correctly
    llmSettingsStore.setModelSource(modelSource.value)
    if (modelSource.value === 'lan-machine') {
      llmSettingsStore.setLanIp(lanIp.value)
      llmSettingsStore.setLanPort(lanPort.value)
      llmSettingsStore.setLanModel(lanModel.value)
    } else if (modelSource.value === 'local-ollama') {
      llmSettingsStore.setOllamaIp(ollamaIp.value)
      llmSettingsStore.setOllamaPort(ollamaPort.value)
      llmSettingsStore.setOllamaModel(ollamaModel.value)
    } else if (modelSource.value === 'cloud') {
      llmSettingsStore.setCloudBaseUrl(cloudBaseUrl.value)
      llmSettingsStore.setCloudModel(cloudModel.value)
      llmSettingsStore.setCloudPresetIndex(cloudPresetIndex.value)
      if (cloudApiKey.value) {
        llmSettingsStore.setCloudApiKey(cloudApiKey.value)
      }
    }
    llmSettingsStore.setEnableThinking(enableThinking.value)
    llmSettingsStore.setDefaultMaxTokens(defaultMaxTokens.value)

    // 2. Build backend update payload
    const payload = llmSettingsStore.buildSavePayload()

    // 3. Save to backend api
    const settings = await updateAppSettings(payload)
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
