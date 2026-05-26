<template>
  <div class="p-container-padding">
    <div class="max-w-4xl mx-auto space-y-12 pb-24">
      <div class="space-y-2">
        <h2 class="font-headline-md text-headline-md text-on-background tracking-tight">设置</h2>
        <p class="font-body-lg text-body-lg text-on-surface-variant">
          管理您的个人偏好、系统配置与隐私选项。
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-gutter">
        <!-- 语音设置 -->
        <section
          class="col-span-1 lg:col-span-2 bg-surface rounded-xl border border-surface-variant p-8 flex flex-col gap-8 shadow-[0_10px_30px_rgba(0,0,0,0.02)] transition-colors hover:bg-surface-bright"
        >
          <header class="flex items-center gap-3 border-b border-surface-variant pb-4">
            <MaterialIcon
              name="record_voice_over"
              :fill="1"
              :size="24"
              class="text-primary"
            />
            <h3 class="font-title-sm text-title-sm text-on-surface">语音设置</h3>
          </header>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
            <!-- 音色 -->
            <div class="space-y-3">
              <label class="font-body-md text-body-md text-on-surface-variant block">语音音色</label>
              <div class="flex p-1 bg-surface-container-low rounded-lg border border-surface-variant">
                <button
                  v-for="v in voiceOptions"
                  :key="v"
                  type="button"
                  class="flex-1 py-2 font-body-md text-body-md rounded-md transition-colors"
                  :class="
                    voice === v
                      ? 'bg-surface text-primary shadow-sm border border-outline-variant font-medium'
                      : 'text-on-surface-variant hover:text-primary'
                  "
                  @click="voice = v"
                >{{ v }}</button>
              </div>
            </div>

            <!-- 唤醒词 -->
            <div class="space-y-3">
              <label class="font-body-md text-body-md text-on-surface-variant block">唤醒词设定</label>
              <div class="relative">
                <input
                  v-model="wakeWord"
                  type="text"
                  class="w-full bg-surface-bright border border-surface-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
                />
                <MaterialIcon
                  name="edit"
                  :size="20"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none"
                />
              </div>
            </div>

            <!-- 语速 -->
            <div class="space-y-4 md:col-span-2 max-w-md">
              <div class="flex justify-between items-center">
                <label class="font-body-md text-body-md text-on-surface-variant block">语速调节</label>
                <span class="font-body-md text-body-md text-primary font-medium">{{ speed.toFixed(1) }}x</span>
              </div>
              <div class="relative w-full h-2 bg-surface-container-high rounded-full">
                <div
                  class="absolute left-0 top-0 h-full bg-primary rounded-full"
                  :style="{ width: speedPercent + '%' }"
                ></div>
                <input
                  v-model.number="speed"
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
              </div>
              <div
                class="flex justify-between font-label-sm text-label-sm text-outline px-1"
              >
                <span>较慢</span>
                <span>适中</span>
                <span>较快</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 隐私与安全 -->
        <section
          class="col-span-1 bg-surface rounded-xl border border-surface-variant p-8 flex flex-col gap-8 shadow-[0_10px_30px_rgba(0,0,0,0.02)] transition-colors hover:bg-surface-bright"
        >
          <header class="flex items-center gap-3 border-b border-surface-variant pb-4">
            <MaterialIcon name="shield" :fill="1" :size="24" class="text-primary" />
            <h3 class="font-title-sm text-title-sm text-on-surface">隐私与安全</h3>
          </header>

          <div class="space-y-6 flex-1">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h4 class="font-body-lg text-body-lg text-on-surface font-medium">端到端数据加密</h4>
                <p class="font-label-sm text-label-sm text-on-surface-variant mt-1">
                  所有对话与文件将在传输及静息状态下加密保护。
                </p>
              </div>
              <ToggleSwitch v-model="encryption" />
            </div>

            <div class="flex items-start justify-between gap-4 pt-2">
              <div>
                <h4 class="font-body-lg text-body-lg text-on-surface font-medium">会话历史自动清理</h4>
                <p class="font-label-sm text-label-sm text-on-surface-variant mt-1">
                  设置超过指定时间的对话记录自动销毁。
                </p>
              </div>
              <select
                v-model="historyExpire"
                class="bg-surface-bright border border-surface-variant rounded-lg px-3 py-2 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary mt-1 min-w-[120px]"
              >
                <option value="never">永不</option>
                <option value="7d">7天后</option>
                <option value="30d">30天后</option>
              </select>
            </div>
          </div>
        </section>

        <!-- 系统集成 -->
        <section
          class="col-span-1 bg-surface rounded-xl border border-surface-variant p-8 flex flex-col gap-8 shadow-[0_10px_30px_rgba(0,0,0,0.02)] transition-colors hover:bg-surface-bright"
        >
          <header class="flex items-center gap-3 border-b border-surface-variant pb-4">
            <MaterialIcon name="integration_instructions" :size="24" class="text-primary" />
            <h3 class="font-title-sm text-title-sm text-on-surface">系统集成</h3>
          </header>

          <div class="space-y-6 flex-1">
            <div class="space-y-2">
              <label class="font-body-md text-body-md text-on-surface-variant block">全局 API 密钥</label>
              <div class="flex gap-2">
                <input
                  :type="showApiKey ? 'text' : 'password'"
                  :value="apiKey"
                  readonly
                  class="flex-1 bg-surface-bright border border-surface-variant rounded-lg px-4 py-2 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary font-mono tracking-wider"
                />
                <button
                  type="button"
                  class="px-4 py-2 bg-surface-container-low border border-surface-variant rounded-lg text-on-surface hover:bg-surface-container transition-colors"
                  @click="showApiKey = !showApiKey"
                >
                  <MaterialIcon
                    :name="showApiKey ? 'visibility_off' : 'visibility'"
                    :size="20"
                    class="align-middle"
                  />
                </button>
              </div>
            </div>

            <div
              class="p-4 bg-surface-container-lowest border border-outline-variant rounded-lg flex items-center justify-between"
            >
              <div class="flex items-center gap-4">
                <div
                  class="w-10 h-10 bg-surface-container rounded-full flex items-center justify-center"
                >
                  <MaterialIcon name="mail" :size="20" class="text-on-surface-variant" />
                </div>
                <div>
                  <h4 class="font-body-md text-body-md text-on-surface font-medium">企业邮箱</h4>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span
                      class="w-2 h-2 rounded-full"
                      :class="emailConnected ? 'bg-primary' : 'bg-error'"
                    ></span>
                    <span class="font-label-sm text-label-sm text-on-surface-variant">
                      {{ emailConnected ? '已连接' : '未连接' }}
                    </span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                class="font-body-md text-body-md px-4 py-2 bg-surface text-primary border border-outline-variant rounded-lg hover:bg-surface-container-low transition-colors"
                @click="emailConnected = !emailConnected"
              >{{ emailConnected ? '断开' : '连接' }}</button>
            </div>
          </div>
        </section>
      </div>

      <div class="flex justify-end gap-4 pt-6 border-t border-surface-variant">
        <button
          type="button"
          class="px-6 py-3 font-title-sm text-title-sm bg-surface text-primary border border-outline-variant rounded-lg hover:bg-surface-container-low transition-colors"
          @click="resetDefaults"
        >恢复默认</button>
        <button
          type="button"
          class="px-6 py-3 font-title-sm text-title-sm bg-primary text-on-primary rounded-lg hover:bg-on-primary-fixed-variant transition-colors shadow-md"
          @click="saveSettings"
        >保存设置</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import MaterialIcon from '@components/MaterialIcon.vue'
import ToggleSwitch from '@components/ToggleSwitch.vue'

const voiceOptions = ['沉稳男声', '亲切女声', '中性合成'] as const
type VoiceOption = (typeof voiceOptions)[number]

const voice = ref<VoiceOption>('沉稳男声')
const wakeWord = ref('你好, Zenith')
const speed = ref(1.0)
const encryption = ref(true)
const historyExpire = ref<'never' | '7d' | '30d'>('30d')
const apiKey = ref('sk-zenith-1234567890abcdef')
const showApiKey = ref(false)
const emailConnected = ref(false)

const speedPercent = computed(() => ((speed.value - 0.5) / 1.5) * 100)

const resetDefaults = (): void => {
  voice.value = '沉稳男声'
  wakeWord.value = '你好, Zenith'
  speed.value = 1.0
  encryption.value = true
  historyExpire.value = '30d'
  showApiKey.value = false
  emailConnected.value = false
}

const saveSettings = (): void => {
  console.log('[Settings] saved', {
    voice: voice.value,
    wakeWord: wakeWord.value,
    speed: speed.value,
    encryption: encryption.value,
    historyExpire: historyExpire.value,
    emailConnected: emailConnected.value
  })
}
</script>
