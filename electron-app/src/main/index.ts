import { app, shell, BrowserWindow, dialog, ipcMain, type OpenDialogOptions } from 'electron'
import { join } from 'path'
import { existsSync, statSync } from 'fs'
import { request as httpRequest, type IncomingMessage } from 'http'
import { spawn, type ChildProcess } from 'child_process'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'

const DEFAULT_AGENT_HOST = '127.0.0.1'
const DEFAULT_AGENT_PORT = 8099
const DEFAULT_AGENT_ENTRY = 'app.main:app'
const DEFAULT_AGENT_EXECUTABLE_NAME =
  process.platform === 'win32' ? 'local-agent-runtime.exe' : 'local-agent-runtime'
const DEFAULT_AGENT_READY_TIMEOUT_MS = 15000

const DEFAULT_MCP_HOST = '127.0.0.1'
const DEFAULT_MCP_PORT = 8000
const DEFAULT_MCP_EXECUTABLE_NAME =
  process.platform === 'win32' ? 'mcp-server.exe' : 'mcp-server'

let localAgentProcess: ChildProcess | null = null
let localAgentOwnedByApp = false
let mcpProcess: ChildProcess | null = null

const registerWorkspaceIpc = (): void => {
  ipcMain.handle('workspace:select', async (event): Promise<string | null> => {
    const options: OpenDialogOptions = {
      title: '选择工作空间',
      buttonLabel: '选择此文件夹',
      properties: ['openDirectory', 'createDirectory']
    }
    const ownerWindow = BrowserWindow.fromWebContents(event.sender)
    const result = ownerWindow
      ? await dialog.showOpenDialog(ownerWindow, options)
      : await dialog.showOpenDialog(options)

    if (result.canceled || result.filePaths.length === 0) {
      return null
    }

    return result.filePaths[0]
  })

  ipcMain.handle('workspace:open', async (_event, workspacePath: unknown): Promise<void> => {
    if (typeof workspacePath !== 'string' || !workspacePath.trim()) {
      throw new Error('请先选择工作空间。')
    }

    const normalizedPath = workspacePath.trim()
    if (!existsSync(normalizedPath)) {
      throw new Error('工作空间不存在。')
    }
    if (!statSync(normalizedPath).isDirectory()) {
      throw new Error('工作空间路径不是文件夹。')
    }

    const error = await shell.openPath(normalizedPath)
    if (error) {
      throw new Error(error)
    }
  })
}

interface LocalLLMCompleteParams {
  baseUrl: string
  prompt: string
  model?: string
  temperature?: number
  maxTokens?: number
}

interface LocalLLMCompleteResult {
  text: string
  model: string
  usage: {
    promptTokens: number
    completionTokens: number
    totalTokens: number
  }
}

const registerLocalLLMIpc = (): void => {
  ipcMain.handle('local-llm:complete', async (_event, params: LocalLLMCompleteParams): Promise<LocalLLMCompleteResult> => {
    const { baseUrl, prompt, model, temperature, maxTokens } = params

    return new Promise((resolve, reject) => {
      const url = new URL(baseUrl.endsWith('/') ? `${baseUrl}completions` : `${baseUrl}/completions`)
      const body = JSON.stringify({
        prompt,
        model: model || 'default',
        temperature: temperature ?? 0.8,
        max_tokens: maxTokens ?? 2048
      })

      const req = httpRequest(
        {
          host: url.hostname,
          port: url.port || 80,
          path: url.pathname + url.search,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(body)
          },
          timeout: 120000
        },
        (res: IncomingMessage) => {
          let data = ''
          res.on('data', (chunk: Buffer) => {
            data += chunk.toString()
          })
          res.on('end', () => {
            try {
              const json = JSON.parse(data) as {
                choices?: Array<{ text: string }>
                model?: string
                usage?: {
                  prompt_tokens: number
                  completion_tokens: number
                  total_tokens: number
                }
              }
              resolve({
                text: json.choices?.[0]?.text || '',
                model: json.model || model || 'unknown',
                usage: {
                  promptTokens: json.usage?.prompt_tokens || 0,
                  completionTokens: json.usage?.completion_tokens || 0,
                  totalTokens: json.usage?.total_tokens || 0
                }
              })
            } catch (err) {
              reject(new Error(`Failed to parse LLM response: ${(err as Error).message}`))
            }
          })
          res.on('error', reject)
        }
      )

      req.on('error', reject)
      req.on('timeout', () => {
        req.destroy()
        reject(new Error('Local LLM request timed out'))
      })

      req.write(body)
      req.end()
    })
  })

  ipcMain.handle('local-llm:complete-stream', async (event, params: LocalLLMCompleteParams): Promise<LocalLLMCompleteResult> => {
    const { baseUrl, prompt, model, temperature, maxTokens } = params
    const sender = event.sender

    return new Promise((resolve, reject) => {
      const url = new URL(baseUrl.endsWith('/') ? `${baseUrl}completions` : `${baseUrl}/completions`)
      const body = JSON.stringify({
        prompt,
        model: model || 'default',
        temperature: temperature ?? 0.8,
        max_tokens: maxTokens ?? 2048,
        stream: true
      })

      const req = httpRequest(
        {
          host: url.hostname,
          port: url.port || 80,
          path: url.pathname + url.search,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(body)
          },
          timeout: 120000
        },
        (res: IncomingMessage) => {
          let buffer = ''
          let fullText = ''
          let modelName = model || 'unknown'
          const requestId = `local-${Date.now()}`

          sender.send('local-llm:stream-event', {
            type: 'start',
            request_id: requestId,
            model: modelName,
            provider: 'local-llm'
          })

          res.on('data', (chunk: Buffer) => {
            buffer += chunk.toString()
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              const trimmed = line.trim()
              if (!trimmed || !trimmed.startsWith('data:')) continue

              const data = trimmed.slice(5).trim()
              if (data === '[DONE]') continue

              try {
                const json = JSON.parse(data) as {
                  choices?: Array<{ text: string }>
                  model?: string
                  usage?: Record<string, number>
                }
                const delta = json.choices?.[0]?.text || ''
                if (delta) {
                  fullText += delta
                  sender.send('local-llm:stream-event', {
                    type: 'delta',
                    request_id: requestId,
                    delta,
                    model: json.model || modelName,
                    provider: 'local-llm'
                  })
                }
              } catch {
                // skip unparseable lines
              }
            }
          })

          res.on('end', () => {
            // flush remaining buffer
            if (buffer.trim()) {
              const trimmed = buffer.trim()
              if (trimmed.startsWith('data:')) {
                const data = trimmed.slice(5).trim()
                if (data !== '[DONE]') {
                  try {
                    const json = JSON.parse(data) as {
                      choices?: Array<{ text: string }>
                      model?: string
                    }
                    const delta = json.choices?.[0]?.text || ''
                    if (delta) {
                      fullText += delta
                      sender.send('local-llm:stream-event', {
                        type: 'delta',
                        request_id: requestId,
                        delta,
                        model: json.model || modelName,
                        provider: 'local-llm'
                      })
                    }
                  } catch {
                    // skip
                  }
                }
              }
            }

            sender.send('local-llm:stream-event', {
              type: 'done',
              request_id: requestId,
              reply: fullText,
              model: modelName,
              provider: 'local-llm'
            })

            resolve({
              text: fullText,
              model: modelName,
              usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 }
            })
          })

          res.on('error', (err) => {
            sender.send('local-llm:stream-event', {
              type: 'error',
              request_id: requestId,
              error: err.message
            })
            reject(err)
          })
        }
      )

      req.on('error', (err) => {
        sender.send('local-llm:stream-event', {
          type: 'error',
          request_id: `local-${Date.now()}`,
          error: err.message
        })
        reject(err)
      })
      req.on('timeout', () => {
        req.destroy()
        const timeoutError = new Error('Local LLM stream request timed out')
        sender.send('local-llm:stream-event', {
          type: 'error',
          request_id: `local-${Date.now()}`,
          error: timeoutError.message
        })
        reject(timeoutError)
      })

      req.write(body)
      req.end()
    })
  })
}

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

const resolveAgentDataDir = (): string =>
  process.env.LOCAL_AGENT_DATA_DIR || join(app.getPath('userData'), 'local-agent')

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

// ── MCP Server ──────────────────────────────────────────────────────────────

const resolveMcpExecutable = (): string | null => {
  const candidates = [
    join(process.resourcesPath, 'mcp-server', DEFAULT_MCP_EXECUTABLE_NAME),
    join(
      process.resourcesPath,
      'app.asar.unpacked',
      'mcp-server',
      DEFAULT_MCP_EXECUTABLE_NAME
    ),
    join(app.getAppPath(), '..', 'mcp-server', DEFAULT_MCP_EXECUTABLE_NAME)
  ]
  for (const p of candidates) {
    if (existsSync(p)) {
      return p
    }
  }
  return null
}

const stopMcpServer = (): void => {
  if (mcpProcess && !mcpProcess.killed) {
    mcpProcess.kill()
    mcpProcess = null
  }
}

const startMcpServer = async (): Promise<void> => {
  // In dev mode, the MCP server is started by scripts/dev.mjs
  if (is.dev) {
    return
  }

  const executablePath = resolveMcpExecutable()
  if (!executablePath) {
    console.warn('[mcp] Bundled mcp-server executable not found — skipping MCP startup.')
    console.warn('[mcp] Computer-control features will be unavailable.')
    return
  }

  const args = [
    'serve',
    '--transport',
    'streamable-http',
    '--host',
    DEFAULT_MCP_HOST,
    '--port',
    String(DEFAULT_MCP_PORT)
  ]

  console.log(`[mcp] Starting MCP server: ${executablePath} ${args.join(' ')}`)
  const child = spawn(executablePath, args, {
    cwd: join(executablePath, '..'),
    windowsHide: true,
    env: { ...process.env }
  })

  mcpProcess = child

  child.stdout?.on('data', (chunk: Buffer) => {
    const text = chunk.toString().trim()
    if (text) console.log(`[mcp] ${text}`)
  })

  child.stderr?.on('data', (chunk: Buffer) => {
    const text = chunk.toString().trim()
    if (text) console.error(`[mcp] ${text}`)
  })

  child.on('error', (error) => {
    console.error(`[mcp] Failed to start: ${error.message}`)
  })

  child.on('exit', (code, signal) => {
    console.warn(`[mcp] Exited (code=${code ?? 'null'}, signal=${signal ?? 'null'})`)
    if (mcpProcess?.pid === child.pid) {
      mcpProcess = null
    }
  })
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

  const executablePath = is.dev ? null : resolveLocalAgentExecutable()
  const agentDataDir = resolveAgentDataDir()
  if (executablePath) {
    const executableCwd = join(executablePath, '..')
    const args = ['--host', agentHost, '--port', String(agentPort)]
    console.log(`[local-agent] Starting packaged backend: ${executablePath} ${args.join(' ')}`)
    const child = spawn(executablePath, args, {
      cwd: executableCwd,
      windowsHide: true,
      env: {
        ...process.env,
        DATA_DIR: agentDataDir
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
        PYTHONIOENCODING: 'utf-8',
        DATA_DIR: agentDataDir
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

const loadURLWithRetry = async (
  window: BrowserWindow,
  url: string,
  maxRetries = 10,
  retryDelayMs = 500
): Promise<void> => {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await window.loadURL(url)
      return
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      if (attempt < maxRetries) {
        console.log(
          `[dev] Waiting for dev server (attempt ${attempt}/${maxRetries}): ${message}`
        )
        await delay(retryDelayMs)
      } else {
        throw err
      }
    }
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
    const devUrl = process.env['ELECTRON_RENDERER_URL']
    console.log(`[dev] Loading dev server at ${devUrl}`)
    loadURLWithRetry(mainWindow, devUrl).catch((err) => {
      console.error(`[dev] Failed to load ${devUrl} after retries:`, err)
      // Fallback: try loading the built file
      mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
    })
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.aivoice.app')
  registerWorkspaceIpc()
  registerLocalLLMIpc()

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Start backend services in parallel
  await Promise.all([ensureLocalAgentStarted(), startMcpServer()])
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
  stopMcpServer()
})

// In this file you can include the rest of your app"s specific main process
// code. You can also put them in separate files and require them here.
