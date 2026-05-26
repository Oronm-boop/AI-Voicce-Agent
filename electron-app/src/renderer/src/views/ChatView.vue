<template>
  <div class="flex flex-col h-full">
    <div class="flex-1 overflow-y-auto flex flex-col items-center pb-32">
      <div class="w-full max-w-3xl px-6 py-8 flex flex-col gap-6 mt-8">
        <template v-for="msg in messages" :key="msg.id">
          <!-- AI 消息 -->
          <div v-if="msg.role === 'ai'" class="flex items-start gap-4">
            <div
              class="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center flex-shrink-0 border border-outline-variant"
            >
              <MaterialIcon name="smart_toy" class="text-primary" />
            </div>
            <div
              class="bg-surface-container-lowest border border-outline-variant p-5 rounded-lg shadow-sm w-full"
            >
              <p class="font-body-lg text-body-lg text-on-surface">{{ msg.text }}</p>
            </div>
          </div>

          <!-- 用户消息 -->
          <div v-else class="flex items-start gap-4 flex-row-reverse">
            <div
              class="w-10 h-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0 text-on-primary"
            >
              <MaterialIcon name="person" />
            </div>
            <div class="bg-primary-container p-5 rounded-lg w-auto max-w-[80%]">
              <p class="font-body-lg text-body-lg text-on-primary">{{ msg.text }}</p>
            </div>
          </div>
        </template>
      </div>

      <!-- 语音交互区 -->
      <div class="mt-auto mb-12 flex flex-col items-center w-full max-w-2xl px-6">
        <VoiceWave class="mb-6" :active="listening" />

        <div class="flex items-center gap-2 mb-8">
          <span
            class="w-2 h-2 rounded-full bg-primary"
            :class="{ 'animate-pulse': listening }"
          ></span>
          <span class="font-body-md text-body-md text-secondary">
            {{ listening ? '正在倾听...' : '点击麦克风开始对话' }}
          </span>
        </div>

        <button
          class="w-20 h-20 rounded-full bg-surface-container-lowest border border-outline-variant flex items-center justify-center shadow-[0_10px_30px_rgba(0,0,0,0.04)] hover:bg-surface-container-low transition-colors group"
          :class="{ '!bg-primary !border-primary': listening }"
          @click="toggleListening"
        >
          <MaterialIcon
            :name="listening ? 'mic' : 'mic_none'"
            :fill="listening ? 1 : 0"
            :size="32"
            class="group-hover:scale-110 transition-transform"
            :class="listening ? 'text-on-primary' : 'text-primary'"
          />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MaterialIcon from '@components/MaterialIcon.vue'
import VoiceWave from '@components/VoiceWave.vue'

interface Message {
  id: number
  role: 'ai' | 'user'
  text: string
}

const messages = ref<Message[]>([
  { id: 1, role: 'ai', text: '您好。我已准备就绪，可以协助您处理今天的任务。请随时开始对话。' },
  { id: 2, role: 'user', text: '帮我总结一下昨天会议的关键点，并更新到任务列表里。' }
])

const listening = ref(true)
const toggleListening = (): void => {
  listening.value = !listening.value
}
</script>
