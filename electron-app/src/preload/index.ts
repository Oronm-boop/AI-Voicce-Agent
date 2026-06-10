import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

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

// Custom APIs for renderer
const api = {
  selectWorkspace: (): Promise<string | null> => ipcRenderer.invoke('workspace:select'),
  openWorkspace: (workspacePath: string): Promise<void> =>
    ipcRenderer.invoke('workspace:open', workspacePath),
  localLLM: {
    complete: (params: LocalLLMCompleteParams): Promise<LocalLLMCompleteResult> =>
      ipcRenderer.invoke('local-llm:complete', params),
    completeStream: (params: LocalLLMCompleteParams): Promise<LocalLLMCompleteResult> =>
      ipcRenderer.invoke('local-llm:complete-stream', params),
    onStreamEvent: (callback: (event: LocalLLMStreamEvent) => void): (() => void) => {
      const handler = (_event: Electron.IpcRendererEvent, data: LocalLLMStreamEvent): void =>
        callback(data)
      ipcRenderer.on('local-llm:stream-event', handler)
      return () => {
        ipcRenderer.removeListener('local-llm:stream-event', handler)
      }
    }
  }
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}
