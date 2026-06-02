import { app, shell, BrowserWindow } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { request as httpRequest } from 'http'
import { spawn, type ChildProcess } from 'child_process'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'

const DEFAULT_AGENT_HOST = '127.0.0.1'
const DEFAULT_AGENT_PORT = 8765
const DEFAULT_AGENT_ENTRY = 'app.main:app'
const DEFAULT_AGENT_EXECUTABLE_NAME =
  process.platform === 'win32' ? 'local-agent-runtime.exe' : 'local-agent-runtime'
const DEFAULT_AGENT_READY_TIMEOUT_MS = 15000

let localAgentProcess: ChildProcess | null = null
let localAgentOwnedByApp = false

const delay = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms)
  })

const parsePort = (value: string | undefined): number => {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : DEFAULT_AGENT_PORT
}

const agentHost = process.env.LOCAL_AGENT_HOST || DEFAULT_AGENT_HOST
const agentPort = parsePort(process.env.LOCAL_AGENT_PORT)
const agentEntry = process.env.LOCAL_AGENT_ENTRY || DEFAULT_AGENT_ENTRY

const isAutoStartEnabled = (): boolean => {
  const value = process.env.LOCAL_AGENT_AUTOSTART
  return value === undefined || value.toLowerCase() !== 'false'
}

const checkAgentHealth = (timeoutMs = 1500): Promise<boolean> =>
  new Promise((resolve) => {
    const req = httpRequest(
      {
        host: agentHost,
        port: agentPort,
        path: '/health',
        method: 'GET',
        timeout: timeoutMs
      },
      (res) => {
        const healthy = res.statusCode === 200
        res.resume()
        resolve(healthy)
      }
    )

    req.on('error', () => resolve(false))
    req.on('timeout', () => {
      req.destroy()
      resolve(false)
    })
    req.end()
  })

const resolveLocalAgentDir = (): string | null => {
  const customDir = process.env.LOCAL_AGENT_DIR?.trim()
  const candidates = [
    customDir,
    join(app.getAppPath(), '..', 'local-agent'),
    join(process.resourcesPath, 'local-agent'),
    join(process.resourcesPath, 'app.asar.unpacked', 'local-agent')
  ].filter((value): value is string => Boolean(value))

  for (const dir of candidates) {
    if (existsSync(join(dir, 'app', 'main.py'))) {
      return dir
    }
  }

  return null
}

const resolveLocalAgentExecutable = (): string | null => {
  const customExecutable = process.env.LOCAL_AGENT_EXECUTABLE?.trim()
  const candidates = [
    customExecutable,
    join(
      app.getAppPath(),
      '..',
      'local-agent',
      'dist',
      'local-agent-runtime',
      DEFAULT_AGENT_EXECUTABLE_NAME
    ),
    join(process.resourcesPath, 'local-agent', DEFAULT_AGENT_EXECUTABLE_NAME),
    join(
      process.resourcesPath,
      'app.asar.unpacked',
      'local-agent',
      DEFAULT_AGENT_EXECUTABLE_NAME
    )
  ].filter((value): value is string => Boolean(value))

  for (const executablePath of candidates) {
    if (existsSync(executablePath)) {
      return executablePath
    }
  }

  return null
}

const resolvePythonExecutable = (agentDir: string): string => {
  const customPython = process.env.LOCAL_AGENT_PYTHON?.trim()
  if (customPython) {
    return customPython
  }

  const candidates = [
    join(agentDir, '.venv', 'Scripts', 'python.exe'),
    join(agentDir, '.venv', 'bin', 'python')
  ]

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate
    }
  }

  return process.platform === 'win32' ? 'python.exe' : 'python3'
}

const stopLocalAgent = (): void => {
  if (!localAgentOwnedByApp || !localAgentProcess || localAgentProcess.killed) {
    return
  }
  localAgentProcess.kill()
  localAgentProcess = null
  localAgentOwnedByApp = false
}

const attachLocalAgentProcessListeners = (child: ChildProcess): void => {
  localAgentProcess = child
  localAgentOwnedByApp = true

  child.stdout?.on('data', (chunk: Buffer) => {
    const text = chunk.toString().trim()
    if (text) {
      console.log(`[local-agent] ${text}`)
    }
  })

  child.stderr?.on('data', (chunk: Buffer) => {
    const text = chunk.toString().trim()
    if (text) {
      console.error(`[local-agent] ${text}`)
    }
  })

  child.on('error', (error) => {
    console.error(`[local-agent] Failed to start: ${error.message}`)
  })

  child.on('exit', (code, signal) => {
    console.warn(`[local-agent] Exited (code=${code ?? 'null'}, signal=${signal ?? 'null'})`)
    if (localAgentProcess?.pid === child.pid) {
      localAgentProcess = null
      localAgentOwnedByApp = false
    }
  })
}

const waitForAgentReady = async (timeoutMs: number): Promise<boolean> => {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await checkAgentHealth()) {
      return true
    }

    if (localAgentProcess?.exitCode !== null || localAgentProcess?.killed) {
      return false
    }
    await delay(300)
  }
  return false
}

const ensureLocalAgentStarted = async (): Promise<void> => {
  if (!isAutoStartEnabled()) {
    console.log('[local-agent] Auto-start disabled by LOCAL_AGENT_AUTOSTART=false')
    return
  }

  if (await checkAgentHealth()) {
    console.log('[local-agent] Reusing existing backend process')
    return
  }

  const executablePath = resolveLocalAgentExecutable()
  if (executablePath) {
    const executableCwd = join(executablePath, '..')
    const args = ['--host', agentHost, '--port', String(agentPort)]
    console.log(`[local-agent] Starting packaged backend: ${executablePath} ${args.join(' ')}`)
    const child = spawn(executablePath, args, {
      cwd: executableCwd,
      windowsHide: true,
      env: {
        ...process.env
      }
    })
    attachLocalAgentProcessListeners(child)
  } else {
    const agentDir = resolveLocalAgentDir()
    if (!agentDir) {
      console.error(
        '[local-agent] Not found. Set LOCAL_AGENT_DIR or LOCAL_AGENT_EXECUTABLE.'
      )
      return
    }

    const pythonExecutable = resolvePythonExecutable(agentDir)
    const args = ['-m', 'uvicorn', agentEntry, '--host', agentHost, '--port', String(agentPort)]
    console.log(`[local-agent] Starting Python backend: ${pythonExecutable} ${args.join(' ')}`)
    const child = spawn(pythonExecutable, args, {
      cwd: agentDir,
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8'
      }
    })
    attachLocalAgentProcessListeners(child)
  }

  const ready = await waitForAgentReady(DEFAULT_AGENT_READY_TIMEOUT_MS)
  if (ready) {
    console.log(`[local-agent] Ready at http://${agentHost}:${agentPort}`)
  } else {
    console.error('[local-agent] Startup timeout or process exited before ready')
  }
}

function createWindow(): void {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 900,
    height: 670,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(async () => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.electron')

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  await ensureLocalAgentStarted()
  createWindow()

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopLocalAgent()
})

// In this file you can include the rest of your app"s specific main process
// code. You can also put them in separate files and require them here.
