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
            {{ inputStatusText }}
          </span>
          <span class="font-body-sm text-body-sm text-outline ml-2">
            {{ modelStatusText }}
          </span>
          <div class="ml-auto flex items-center gap-1">
            <button
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-outline hover:text-primary hover:bg-surface-container"
              :class="{ 'text-primary': ttsEnabled }"
              :title="ttsEnabled ? '关闭播报' : '开启播报'"
              @click="toggleTts"
            >
              <MaterialIcon :name="ttsEnabled ? 'volume_up' : 'volume_off'" class="text-[20px]" />
            </button>
            <button
              v-if="speaking"
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-outline hover:text-primary hover:bg-surface-container"
              title="停止播报"
              @click="stopSpeaking"
            >
              <MaterialIcon name="stop_circle" class="text-[20px]" />
            </button>
          </div>
        </div>

        <form class="w-full flex items-end gap-3" @submit.prevent="handleSubmit">
          <button
            type="button"
            class="w-12 h-12 rounded-full bg-surface-container-lowest border border-outline-variant flex items-center justify-center shadow-sm hover:bg-surface-container-low transition-colors group flex-shrink-0"
            :class="{ '!bg-primary !border-primary': listening }"
            :title="voiceButtonTitle"
            @click="toggleListening"
          >
            <MaterialIcon
              :name="voiceButtonIcon"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MaterialIcon from '@components/MaterialIcon.vue'
import VoiceWave from '@components/VoiceWave.vue'
import { useConversationStore, type ChatMessage } from '@store/useConversationStore'
import {
  getModelsStatus,
  sendChatStream,
  transcribeVoice,
  type ChatRequest,
  type ChatStreamEvent,
  type ModelStatusResponse
} from '@api/localAgent'

const route = useRoute()
const router = useRouter()
const conversationStore = useConversationStore()
const messages = computed(() => conversationStore.activeMessages)
const listening = ref(false)
const transcribing = ref(false)
const inputText = ref('')
const sending = ref(false)
const ttsEnabled = ref(true)
const speaking = ref(false)
const errorMessage = ref('')
const messageListRef = ref<HTMLElement | null>(null)
const status = ref<ModelStatusResponse | null>(null)
const hearingSpeech = ref(false)
const queuedVoicePromptCount = ref(0)
const pendingVoicePromptText = ref('')

let activeMicStream: MediaStream | null = null
let audioContext: AudioContext | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let processorNode: ScriptProcessorNode | null = null
let recordingSampleRate = 16000
let activeUtterance: SpeechSynthesisUtterance | null = null
let speechSegmentActive = false
let speechSegmentSamples: Float32Array[] = []
let speechSegmentSampleCount = 0
let speechSegmentMs = 0
let speechSegmentSpeechMs = 0
let speechSegmentSilenceMs = 0
let preSpeechSamples: Float32Array[] = []
let preSpeechSampleCount = 0
let activeTranscriptionCount = 0
let transcriptionChain: Promise<void> = Promise.resolve()
let voicePromptQueue: string[] = []
let pendingVoicePromptParts: string[] = []
let drainingVoicePromptQueue = false

const targetRecordingSampleRate = 16000
const voiceActivityThreshold = 0.018
const silenceToSubmitMs = 900
const minSpeechMs = 450
const maxSpeechSegmentMs = 12000
const preSpeechMs = 250
const voiceExecutionKeyword = '执行'

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

const inputStatusText = computed(() => {
  if (hearingSpeech.value) {
    return '听到语音，正在识别并暂存'
  }
  if (transcribing.value) {
    return '正在识别语音片段...'
  }
  if (listening.value && sending.value) {
    return '正在执行语音命令...'
  }
  if (queuedVoicePromptCount.value > 0) {
    return `还有 ${queuedVoicePromptCount.value} 条语音命令排队`
  }
  if (pendingVoicePromptText.value) {
    return '已暂存语音命令，说“执行”后开始执行'
  }
  if (listening.value) {
    return '实时语音已开启，说出命令后用“执行”确认'
  }
  return '点击麦克风开始对话'
})

const voiceButtonIcon = computed(() => {
  if (transcribing.value && !listening.value) {
    return 'hourglass_top'
  }
  if (hearingSpeech.value) {
    return 'graphic_eq'
  }
  return listening.value ? 'mic' : 'mic_none'
})

const voiceButtonTitle = computed(() =>
  listening.value ? '停止实时语音' : '开启实时语音'
)

const scrollToBottom = async (): Promise<void> => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const appendMessage = async (
  role: ChatMessage['role'],
  text: string
): Promise<ChatMessage> => {
  const message = conversationStore.appendMessage(role, text)
  await scrollToBottom()
  return message
}

const updateMessageText = (id: string, text: string, conversationId?: string): void => {
  conversationStore.updateMessageText(id, text, conversationId)
  void scrollToBottom()
}

const buildChatRequestMessages = (): ChatRequest['messages'] =>
  messages.value
    .filter((message, index) => {
      if (index === 0 && message.role === 'ai') {
        return false
      }

      return Boolean(message.text.trim()) && message.text !== '正在生成...'
    })
    .map((message) => ({
      role: message.role === 'ai' ? 'assistant' : 'user',
      content: message.text
    }))

const syncConversationFromRoute = async (): Promise<void> => {
  const routeConversationId = route.query.conversationId
  if (
    typeof routeConversationId === 'string' &&
    conversationStore.selectConversation(routeConversationId)
  ) {
    await scrollToBottom()
    return
  }

  const conversationId = conversationStore.ensureConversation()
  if (route.name === 'Chat' && routeConversationId !== conversationId) {
    await router.replace({ name: 'Chat', query: { conversationId } })
    return
  }

  await scrollToBottom()
}

const checkModelStatus = async (): Promise<void> => {
  try {
    status.value = await getModelsStatus()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `模型状态获取失败：${message}`
  }
}

const stopSpeaking = (): void => {
  if (!window.speechSynthesis) {
    return
  }
  window.speechSynthesis.cancel()
  activeUtterance = null
  speaking.value = false
}

const speakText = (text: string): void => {
  if (!ttsEnabled.value || !text.trim() || !window.speechSynthesis) {
    return
  }

  stopSpeaking()
  const utterance = new SpeechSynthesisUtterance(text.trim().slice(0, 1000))
  utterance.lang = 'zh-CN'
  utterance.rate = 1
  utterance.onstart = () => {
    speaking.value = true
  }
  utterance.onend = () => {
    if (activeUtterance === utterance) {
      activeUtterance = null
      speaking.value = false
    }
  }
  utterance.onerror = () => {
    if (activeUtterance === utterance) {
      activeUtterance = null
      speaking.value = false
    }
  }
  activeUtterance = utterance
  window.speechSynthesis.speak(utterance)
}

const toggleTts = (): void => {
  ttsEnabled.value = !ttsEnabled.value
  if (!ttsEnabled.value) {
    stopSpeaking()
  }
}

const submitPrompt = async (prompt: string): Promise<void> => {
  const normalizedPrompt = prompt.trim()
  if (sending.value || !normalizedPrompt) {
    return
  }

  errorMessage.value = ''
  sending.value = true
  stopSpeaking()

  await appendMessage('user', normalizedPrompt)
  const conversationId = conversationStore.activeConversationId
  const requestMessages = buildChatRequestMessages()
  const assistantMessage = await appendMessage('ai', '正在生成...')
  const assistantMessageId = assistantMessage.id

  let streamedReply = ''

  try {
    const response = await sendChatStream(
      {
        messages: requestMessages
      },
      (event: ChatStreamEvent) => {
        if (event.type === 'workflow' && event.message && !streamedReply) {
          updateMessageText(assistantMessageId, event.message, conversationId)
        }

        if (event.type === 'delta' && event.delta) {
          streamedReply += event.delta
          updateMessageText(assistantMessageId, streamedReply, conversationId)
        }

        if (event.type === 'done') {
          streamedReply = event.reply ?? streamedReply
          updateMessageText(assistantMessageId, streamedReply, conversationId)
          speakText(streamedReply)
        }

        if (event.type === 'computer_actions') {
          const actionText =
            event.message ||
            event.computer_actions?.map((action) => action.message).join('\n') ||
            ''
          if (actionText && !streamedReply) {
            updateMessageText(assistantMessageId, actionText, conversationId)
          }
        }

        if (event.type === 'file_actions') {
          const actionText =
            event.message ||
            event.file_actions?.map((action) => action.message).join('\n') ||
            ''
          if (actionText && !streamedReply) {
            updateMessageText(assistantMessageId, actionText, conversationId)
          }
        }

        if (event.type === 'tasks' && event.tasks_created?.length) {
          const suffix = `\n\n已创建 ${event.tasks_created.length} 个任务，可在任务看板查看。`
          updateMessageText(assistantMessageId, `${streamedReply}${suffix}`, conversationId)
        }
      }
    )

    if (!streamedReply) {
      streamedReply = response.reply
      updateMessageText(assistantMessageId, streamedReply, conversationId)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `请求失败：${message}`
    if (!streamedReply) {
      updateMessageText(assistantMessageId, `本地模型调用失败：${message}`, conversationId)
    }
  } finally {
    sending.value = false
  }
}

const handleSubmit = async (): Promise<void> => {
  if (sending.value || !canSend.value) {
    return
  }

  const prompt = inputText.value.trim()
  inputText.value = ''
  await submitPrompt(prompt)
}

const handleKeydown = async (event: KeyboardEvent): Promise<void> => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    await handleSubmit()
  }
}

const stopMicTracks = (): void => {
  activeMicStream?.getTracks().forEach((track) => track.stop())
  activeMicStream = null
}

const stopAudioGraph = (): void => {
  processorNode?.disconnect()
  sourceNode?.disconnect()
  if (audioContext) {
    void audioContext.close()
  }
  processorNode = null
  sourceNode = null
  audioContext = null
}

const mergeAudioSamples = (chunks: Float32Array[], sampleCount: number): Float32Array => {
  const merged = new Float32Array(sampleCount)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  return merged
}

const resetPreSpeechBuffer = (): void => {
  preSpeechSamples = []
  preSpeechSampleCount = 0
}

const resetSpeechSegment = (): void => {
  speechSegmentActive = false
  speechSegmentSamples = []
  speechSegmentSampleCount = 0
  speechSegmentMs = 0
  speechSegmentSpeechMs = 0
  speechSegmentSilenceMs = 0
  hearingSpeech.value = false
}

const resetSpeechBuffers = (): void => {
  resetPreSpeechBuffer()
  resetSpeechSegment()
}

const resampleAudio = (
  samples: Float32Array,
  sourceSampleRate: number,
  targetSampleRate: number
): Float32Array => {
  if (sourceSampleRate === targetSampleRate) {
    return samples
  }

  const ratio = sourceSampleRate / targetSampleRate
  const targetLength = Math.max(1, Math.round(samples.length / ratio))
  const resampled = new Float32Array(targetLength)

  for (let i = 0; i < targetLength; i += 1) {
    const sourceIndex = i * ratio
    const leftIndex = Math.floor(sourceIndex)
    const rightIndex = Math.min(leftIndex + 1, samples.length - 1)
    const fraction = sourceIndex - leftIndex
    const left = samples[leftIndex] || 0
    const right = samples[rightIndex] || 0
    resampled[i] = left + (right - left) * fraction
  }

  return resampled
}

const writeAscii = (view: DataView, offset: number, value: string): void => {
  for (let i = 0; i < value.length; i += 1) {
    view.setUint8(offset + i, value.charCodeAt(i))
  }
}

const encodeWav = (samples: Float32Array, sampleRate: number): Blob => {
  const bytesPerSample = 2
  const headerBytes = 44
  const buffer = new ArrayBuffer(headerBytes + samples.length * bytesPerSample)
  const view = new DataView(buffer)

  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * bytesPerSample, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * bytesPerSample, true)
  view.setUint16(32, bytesPerSample, true)
  view.setUint16(34, 8 * bytesPerSample, true)
  writeAscii(view, 36, 'data')
  view.setUint32(40, samples.length * bytesPerSample, true)

  let offset = headerBytes
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample))
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
    offset += bytesPerSample
  }

  return new Blob([view], { type: 'audio/wav' })
}

const setTranscribingCount = (delta: number): void => {
  activeTranscriptionCount = Math.max(0, activeTranscriptionCount + delta)
  transcribing.value = activeTranscriptionCount > 0
}

const normalizeVoiceKeywordCandidate = (text: string): string =>
  text.replace(/[\s,.!?;:'"，。！？；：、…“”‘’（）()【】《》〈〉\[\]]/g, '').trim()

const isVoiceExecutionTrigger = (text: string): boolean =>
  normalizeVoiceKeywordCandidate(text) === voiceExecutionKeyword

const clearPendingVoicePrompt = (): void => {
  pendingVoicePromptParts = []
  pendingVoicePromptText.value = ''
}

const appendPendingVoicePrompt = (prompt: string): void => {
  const normalizedPrompt = prompt.trim()
  if (!normalizedPrompt) {
    return
  }

  pendingVoicePromptParts.push(normalizedPrompt)
  pendingVoicePromptText.value = pendingVoicePromptParts.join('\n')
}

const executePendingVoicePrompt = (): boolean => {
  const prompt = pendingVoicePromptText.value.trim()
  if (!prompt) {
    errorMessage.value = '已收到“执行”，但还没有识别到待执行内容。'
    return false
  }

  clearPendingVoicePrompt()
  enqueueVoicePrompt(prompt)
  return true
}

const handleVoiceTranscript = (transcript: string): boolean => {
  const normalizedTranscript = transcript.trim()
  if (!normalizedTranscript) {
    return false
  }

  if (isVoiceExecutionTrigger(normalizedTranscript)) {
    return executePendingVoicePrompt()
  }

  appendPendingVoicePrompt(normalizedTranscript)
  return true
}

const calculateRms = (samples: Float32Array): number => {
  let sum = 0
  for (const sample of samples) {
    sum += sample * sample
  }
  return Math.sqrt(sum / Math.max(1, samples.length))
}

const pushPreSpeechChunk = (chunk: Float32Array): void => {
  preSpeechSamples.push(chunk)
  preSpeechSampleCount += chunk.length

  const maxPreSpeechSamples = Math.round((recordingSampleRate * preSpeechMs) / 1000)
  while (preSpeechSampleCount > maxPreSpeechSamples && preSpeechSamples.length > 0) {
    const removed = preSpeechSamples.shift()
    preSpeechSampleCount -= removed?.length || 0
  }
}

const appendSpeechSegmentChunk = (
  chunk: Float32Array,
  speechDetected: boolean,
  durationMs: number
): void => {
  speechSegmentSamples.push(chunk)
  speechSegmentSampleCount += chunk.length
  speechSegmentMs += durationMs

  if (speechDetected) {
    speechSegmentSpeechMs += durationMs
    speechSegmentSilenceMs = 0
    return
  }

  speechSegmentSilenceMs += durationMs
}

const beginSpeechSegment = (
  chunk: Float32Array,
  durationMs: number,
  speechDetected: boolean
): void => {
  if (speaking.value) {
    stopSpeaking()
  }

  speechSegmentActive = true
  speechSegmentSamples = [...preSpeechSamples]
  speechSegmentSampleCount = preSpeechSampleCount
  speechSegmentMs = (preSpeechSampleCount / recordingSampleRate) * 1000
  speechSegmentSpeechMs = 0
  speechSegmentSilenceMs = 0
  resetPreSpeechBuffer()
  hearingSpeech.value = true
  appendSpeechSegmentChunk(chunk, speechDetected, durationMs)
}

const finishSpeechSegment = (force = false): void => {
  if (!speechSegmentActive) {
    return
  }

  const samples = mergeAudioSamples(speechSegmentSamples, speechSegmentSampleCount)
  const sampleRate = recordingSampleRate
  const speechMs = speechSegmentSpeechMs
  const minimumSpeechMs = force ? Math.min(minSpeechMs, 180) : minSpeechMs
  resetSpeechSegment()

  if (!samples.length || speechMs < minimumSpeechMs) {
    return
  }

  queueSpeechSegment(samples, sampleRate)
}

const processSpeechSegment = async (
  samples: Float32Array,
  sourceSampleRate: number
): Promise<void> => {
  const wavSamples = resampleAudio(samples, sourceSampleRate, targetRecordingSampleRate)
  const audio = encodeWav(wavSamples, targetRecordingSampleRate)

  if (!audio.size) {
    return
  }

  setTranscribingCount(1)
  try {
    const result = await transcribeVoice(audio)
    const transcript = result.transcript.trim()
    if (transcript) {
      if (handleVoiceTranscript(transcript)) {
        errorMessage.value = ''
      }
    } else if (result.status === 'not_configured') {
      errorMessage.value = result.message
    } else {
      errorMessage.value = result.message
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `语音识别失败：${message}`
  } finally {
    setTranscribingCount(-1)
  }
}

const queueSpeechSegment = (samples: Float32Array, sampleRate: number): void => {
  transcriptionChain = transcriptionChain
    .catch(() => undefined)
    .then(() => processSpeechSegment(samples, sampleRate))
}

const enqueueVoicePrompt = (prompt: string): void => {
  const normalizedPrompt = prompt.trim()
  if (!normalizedPrompt) {
    return
  }

  voicePromptQueue.push(normalizedPrompt)
  queuedVoicePromptCount.value = voicePromptQueue.length
  void drainVoicePromptQueue()
}

const drainVoicePromptQueue = async (): Promise<void> => {
  if (drainingVoicePromptQueue) {
    return
  }

  drainingVoicePromptQueue = true
  try {
    while (voicePromptQueue.length > 0) {
      if (sending.value) {
        await new Promise((resolve) => window.setTimeout(resolve, 150))
        continue
      }

      const prompt = voicePromptQueue.shift()
      queuedVoicePromptCount.value = voicePromptQueue.length
      if (prompt) {
        await submitPrompt(prompt)
      }
    }
  } finally {
    drainingVoicePromptQueue = false
    queuedVoicePromptCount.value = voicePromptQueue.length
  }
}

const handleAudioProcess = (event: AudioProcessingEvent): void => {
  const output = event.outputBuffer.getChannelData(0)
  output.fill(0)

  if (!listening.value) {
    return
  }

  const input = event.inputBuffer.getChannelData(0)
  const chunk = new Float32Array(input)
  const durationMs = (chunk.length / recordingSampleRate) * 1000
  const speechDetected = calculateRms(chunk) >= voiceActivityThreshold

  if (!speechSegmentActive) {
    if (speechDetected) {
      beginSpeechSegment(chunk, durationMs, speechDetected)
      return
    }

    pushPreSpeechChunk(chunk)
    return
  }

  appendSpeechSegmentChunk(chunk, speechDetected, durationMs)
  hearingSpeech.value = true

  if (
    speechSegmentSilenceMs >= silenceToSubmitMs ||
    speechSegmentMs >= maxSpeechSegmentMs
  ) {
    finishSpeechSegment()
  }
}

const startListening = async (): Promise<void> => {
  stopSpeaking()

  const AudioContextCtor =
    window.AudioContext ||
    (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext

  if (!navigator.mediaDevices?.getUserMedia || !AudioContextCtor) {
    errorMessage.value = '当前环境不支持麦克风录音。'
    return
  }

  try {
    resetSpeechBuffers()
    activeMicStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1
      }
    })
    audioContext = new AudioContextCtor()
    recordingSampleRate = audioContext.sampleRate
    sourceNode = audioContext.createMediaStreamSource(activeMicStream)
    processorNode = audioContext.createScriptProcessor(4096, 1, 1)
    processorNode.onaudioprocess = handleAudioProcess
    sourceNode.connect(processorNode)
    processorNode.connect(audioContext.destination)
    await audioContext.resume()
    listening.value = true
    errorMessage.value = ''
  } catch (error) {
    stopAudioGraph()
    stopMicTracks()
    resetSpeechBuffers()
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `麦克风启动失败：${message}`
  }
}

const stopContinuousListening = (): void => {
  const wasListening = listening.value
  listening.value = false
  if (wasListening) {
    finishSpeechSegment(true)
  }
  stopAudioGraph()
  stopMicTracks()
  resetPreSpeechBuffer()
  hearingSpeech.value = false
}

const toggleListening = async (): Promise<void> => {
  if (listening.value) {
    stopContinuousListening()
    return
  }
  await startListening()
}

watch(
  () => route.query.conversationId,
  () => {
    void syncConversationFromRoute()
  }
)

onMounted(async () => {
  await syncConversationFromRoute()
  await checkModelStatus()
  await scrollToBottom()
})

onBeforeUnmount(() => {
  stopSpeaking()
  stopContinuousListening()
  resetSpeechBuffers()
})
</script>
