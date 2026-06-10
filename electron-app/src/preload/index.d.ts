import { ElectronAPI } from '@electron-toolkit/preload'
import type { LocalLLMCompleteParams, LocalLLMCompleteResult, LocalLLMStreamEvent } from './index'

export interface ZenithApi {
  selectWorkspace: () => Promise<string | null>
  openWorkspace: (workspacePath: string) => Promise<void>
  localLLM: {
    complete: (params: LocalLLMCompleteParams) => Promise<LocalLLMCompleteResult>
    completeStream: (params: LocalLLMCompleteParams) => Promise<LocalLLMCompleteResult>
    onStreamEvent: (callback: (event: LocalLLMStreamEvent) => void) => () => void
  }
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: ZenithApi
  }
}
