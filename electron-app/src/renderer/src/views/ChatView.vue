<template>
  <div class="flex flex-col h-full">
    <div ref="messageListRef" class="flex-1 overflow-y-auto flex flex-col items-center pb-20">
      <div class="w-full max-w-3xl px-6 py-8 flex flex-col gap-6 mt-8">
        <template v-for="msg in messages" :key="msg.id">
          <div v-if="msg.role === 'ai'" class="flex items-start gap-4">
            <div
              class="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center flex-shrink-0 border border-outline-variant"
            >
              <MaterialIcon name="smart_toy" class="text-primary" />
            </div>
            <div
              class="bg-surface-container-lowest border border-outline-variant p-5 rounded-lg shadow-sm w-full"
            >
              <p class="font-body-lg text-body-lg text-on-surface whitespace-pre-wrap">
                {{ msg.text }}
              </p>
            </div>
          </div>

          <div v-else class="flex items-start gap-4 flex-row-reverse">
            <div
              class="w-10 h-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0 text-on-primary"
            >
              <MaterialIcon name="person" />
            </div>
            <div class="bg-primary-container p-5 rounded-lg w-auto max-w-[80%]">
              <p class="font-body-lg text-body-lg text-on-primary whitespace-pre-wrap">
                {{ msg.text }}
              </p>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div class="w-full border-t border-outline-variant bg-surface-container-lowest/70">
      <div class="mx-auto max-w-3xl px-6 py-6 flex flex-col gap-4">
        <VoiceWave class="mb-1" :active="listening" />

        <div class="flex items-center gap-2">
          <span
            class="w-2 h-2 rounded-full bg-primary"
            :class="{ 'animate-pulse': listening }"
          ></span>
          <span class="font-body-md text-body-md text-secondary">
            {{ listening ? '正在倾听...' : '点击麦克风开始对话' }}
          </span>
          <span class="font-body-sm text-body-sm text-outline ml-2">
            {{ modelStatusText }}
          </span>
        </div>

        <form class="w-full flex items-end gap-3" @submit.prevent="handleSubmit">
          <button
            type="button"
            class="w-12 h-12 rounded-full bg-surface-container-lowest border border-outline-variant flex items-center justify-center shadow-sm hover:bg-surface-container-low transition-colors group flex-shrink-0"
            :class="{ '!bg-primary !border-primary': listening }"
            @click="toggleListening"
          >
            <MaterialIcon
              :name="listening ? 'mic' : 'mic_none'"
              :fill="listening ? 1 : 0"
              :size="24"
              class="group-hover:scale-110 transition-transform"
              :class="listening ? 'text-on-primary' : 'text-primary'"
            />
          </button>

          <textarea
            v-model="inputText"
            class="flex-1 rounded-lg border border-outline-variant bg-surface-container-highest px-4 py-3 text-body-md text-on-surface resize-none focus:outline-none focus:ring-2 focus:ring-primary/30"
            rows="2"
            placeholder="输入你的问题，按 Enter 发送，Shift+Enter 换行"
            :disabled="sending"
            @keydown="handleKeydown"
          ></textarea>

          <button
            type="submit"
            class="w-12 h-12 rounded-full bg-primary text-on-primary flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="sending || !canSend"
          >
            <MaterialIcon :name="sending ? 'hourglass_top' : 'send'" :size="22" />
          </button>
        </form>

        <p v-if="errorMessage" class="font-body-sm text-body-sm text-error">{{ errorMessage }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import MaterialIcon from '@components/MaterialIcon.vue'
import VoiceWave from '@components/VoiceWave.vue'
import {
  getModelsStatus,
  sendChatStream,
  type ChatStreamEvent,
  type ModelStatusResponse
} from '@api/localAgent'

interface Message {
  id: string
  role: 'ai' | 'user'
  text: string
}

const messages = ref<Message[]>([
  { id: 'msg-1', role: 'ai', text: '您好。我已准备就绪，可以协助您处理今天的任务。请随时开始对话。' }
])

const listening = ref(false)
const inputText = ref('')
const sending = ref(false)
const errorMessage = ref('')
const messageListRef = ref<HTMLElement | null>(null)
const status = ref<ModelStatusResponse | null>(null)

let seed = 2
const createMessageId = (): string => {
  const id = `msg-${seed}`
  seed += 1
  return id
}

const canSend = computed(() => inputText.value.trim().length > 0)

const modelStatusText = computed(() => {
  if (!status.value) {
    return '模型状态检查中...'
  }
  if (!status.value.available) {
    return 'Ollama 未连接'
  }
  if (!status.value.configured_model_present) {
    return `模型未就绪：${status.value.configured_model}`
  }
  return `当前模型：${status.value.configured_model}`
})

const scrollToBottom = async (): Promise<void> => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const appendMessage = async (role: Message['role'], text: string): Promise<void> => {
  messages.value.push({ id: createMessageId(), role, text })
  await scrollToBottom()
}

const updateMessageText = (id: string, text: string): void => {
  const target = messages.value.find((message) => message.id === id)
  if (!target) {
    return
  }
  target.text = text
  void scrollToBottom()
}

const checkModelStatus = async (): Promise<void> => {
  try {
    status.value = await getModelsStatus()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `模型状态获取失败：${message}`
  }
}

const handleSubmit = async (): Promise<void> => {
  if (sending.value || !canSend.value) {
    return
  }

  const prompt = inputText.value.trim()
  inputText.value = ''
  errorMessage.value = ''
  sending.value = true

  await appendMessage('user', prompt)
  const assistantMessageId = createMessageId()
  messages.value.push({ id: assistantMessageId, role: 'ai', text: '正在生成...' })
  await scrollToBottom()

  let streamedReply = ''

  try {
    const response = await sendChatStream(
      {
        prompt,
        max_tokens: 256
      },
      (event: ChatStreamEvent) => {
        if (event.type === 'delta' && event.delta) {
          streamedReply += event.delta
          updateMessageText(assistantMessageId, streamedReply)
        }

        if (event.type === 'done') {
          streamedReply = event.reply ?? streamedReply
          updateMessageText(assistantMessageId, streamedReply)
        }
      }
    )

    if (!streamedReply) {
      streamedReply = response.reply
      updateMessageText(assistantMessageId, streamedReply)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `请求失败：${message}`
    if (!streamedReply) {
      updateMessageText(assistantMessageId, `本地模型调用失败：${message}`)
    }
  } finally {
    sending.value = false
  }
}

const handleKeydown = async (event: KeyboardEvent): Promise<void> => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    await handleSubmit()
  }
}

const toggleListening = (): void => {
  listening.value = !listening.value
}

onMounted(async () => {
  await checkModelStatus()
  await scrollToBottom()
})
</script>
