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
            @click="toggleListening"
          >
            <MaterialIcon
              :name="transcribing ? 'hourglass_top' : listening ? 'mic' : 'mic_none'"
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
            :disabled="sending || transcribing"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import MaterialIcon from '@components/MaterialIcon.vue'
import VoiceWave from '@components/VoiceWave.vue'
import {
  getModelsStatus,
  sendChatStream,
  transcribeVoice,
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
const transcribing = ref(false)
const inputText = ref('')
const sending = ref(false)
const ttsEnabled = ref(true)
const speaking = ref(false)
const errorMessage = ref('')
const messageListRef = ref<HTMLElement | null>(null)
const status = ref<ModelStatusResponse | null>(null)

let seed = 2
let activeMicStream: MediaStream | null = null
let audioContext: AudioContext | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let processorNode: ScriptProcessorNode | null = null
let recordedSamples: Float32Array[] = []
let recordedSampleCount = 0
let recordingSampleRate = 16000
let activeUtterance: SpeechSynthesisUtterance | null = null

const targetRecordingSampleRate = 16000

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

const inputStatusText = computed(() => {
  if (transcribing.value) {
    return '正在识别...'
  }
  if (listening.value) {
    return '正在倾听...'
  }
  return '点击麦克风开始对话'
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

const handleSubmit = async (): Promise<void> => {
  if (sending.value || !canSend.value) {
    return
  }

  const prompt = inputText.value.trim()
  inputText.value = ''
  errorMessage.value = ''
  sending.value = true
  stopSpeaking()

  await appendMessage('user', prompt)
  const assistantMessageId = createMessageId()
  messages.value.push({ id: assistantMessageId, role: 'ai', text: '正在生成...' })
  await scrollToBottom()

  let streamedReply = ''

  try {
    const response = await sendChatStream(
      {
        prompt
      },
      (event: ChatStreamEvent) => {
        if (event.type === 'workflow' && event.message && !streamedReply) {
          updateMessageText(assistantMessageId, event.message)
        }

        if (event.type === 'delta' && event.delta) {
          streamedReply += event.delta
          updateMessageText(assistantMessageId, streamedReply)
        }

        if (event.type === 'done') {
          streamedReply = event.reply ?? streamedReply
          updateMessageText(assistantMessageId, streamedReply)
          speakText(streamedReply)
        }

        if (event.type === 'tasks' && event.tasks_created?.length) {
          const suffix = `\n\n已创建 ${event.tasks_created.length} 个任务，可在任务看板查看。`
          updateMessageText(assistantMessageId, `${streamedReply}${suffix}`)
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

const resetRecordingBuffers = (): void => {
  recordedSamples = []
  recordedSampleCount = 0
}

const mergeRecordingSamples = (): Float32Array => {
  const merged = new Float32Array(recordedSampleCount)
  let offset = 0
  for (const chunk of recordedSamples) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  return merged
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

const handleRecordingComplete = async (): Promise<void> => {
  const sourceSampleRate = recordingSampleRate
  const samples = mergeRecordingSamples()
  const wavSamples = resampleAudio(samples, sourceSampleRate, targetRecordingSampleRate)
  const audio = encodeWav(wavSamples, targetRecordingSampleRate)
  resetRecordingBuffers()
  stopAudioGraph()
  stopMicTracks()

  if (!samples.length || !audio.size) {
    errorMessage.value = '没有采集到有效音频。'
    return
  }

  transcribing.value = true
  try {
    const result = await transcribeVoice(audio)
    if (result.transcript) {
      inputText.value = result.transcript
      errorMessage.value = ''
    } else {
      errorMessage.value = result.message
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `语音识别失败：${message}`
  } finally {
    transcribing.value = false
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
    resetRecordingBuffers()
    activeMicStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioContext = new AudioContextCtor()
    recordingSampleRate = audioContext.sampleRate
    sourceNode = audioContext.createMediaStreamSource(activeMicStream)
    processorNode = audioContext.createScriptProcessor(4096, 1, 1)
    processorNode.onaudioprocess = (event) => {
      const output = event.outputBuffer.getChannelData(0)
      output.fill(0)

      if (!listening.value) {
        return
      }

      const input = event.inputBuffer.getChannelData(0)
      const chunk = new Float32Array(input)
      recordedSamples.push(chunk)
      recordedSampleCount += chunk.length
    }
    sourceNode.connect(processorNode)
    processorNode.connect(audioContext.destination)
    await audioContext.resume()
    listening.value = true
    errorMessage.value = ''
  } catch (error) {
    stopAudioGraph()
    stopMicTracks()
    resetRecordingBuffers()
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `麦克风启动失败：${message}`
  }
}

const toggleListening = async (): Promise<void> => {
  if (transcribing.value) {
    return
  }
  if (listening.value) {
    listening.value = false
    await handleRecordingComplete()
    return
  }
  await startListening()
}

onMounted(async () => {
  await checkModelStatus()
  await scrollToBottom()
})

onBeforeUnmount(() => {
  stopSpeaking()
  stopAudioGraph()
  stopMicTracks()
  resetRecordingBuffers()
})
</script>
