import { ElectronAPI } from '@electron-toolkit/preload'

export interface ZenithApi {
  selectWorkspace: () => Promise<string | null>
  openWorkspace: (workspacePath: string) => Promise<void>
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: ZenithApi
  }
}
