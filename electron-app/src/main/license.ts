import { app } from 'electron'
import { appendFileSync, existsSync, mkdirSync, statSync } from 'fs'
import { delimiter, dirname, join, resolve } from 'path'
import { spawn } from 'child_process'

const DLL_NAME = 'LicenseVallidator.dll'
const EXPORT_NAME = 'ParseAndVerifyLicense'
const RESULT_PREFIX = '__LICENSE_RESULT__'
const DEFAULT_LICENSE_IP = '127.0.0.1'
const DEFAULT_LICENSE_PORT = 7681
const DEFAULT_LICENSE_TIMEOUT_MS = 15000
const LICENSE_RUNTIME_SIDECAR_FILES = [
  'libcrypto-3-x64.dll',
  'libssl-3-x64.dll',
  'uv.dll',
  'websockets.dll',
  'zlib1.dll'
]

export interface LicenseResult {
  ok: boolean
  reason?: string
  logFile?: string
}

const resolveLogFile = (): string | undefined => {
  try {
    const logDir = app.getPath('userData')
    if (!existsSync(logDir)) {
      mkdirSync(logDir, { recursive: true })
    }
    return join(logDir, 'license-check.log')
  } catch {
    return undefined
  }
}

const writeLog = (logFile: string | undefined, message: string): void => {
  const line = `[${new Date().toISOString()}] ${message}`
  console.log(`[license] ${message}`)

  if (!logFile) {
    return
  }

  try {
    appendFileSync(logFile, `${line}\n`, 'utf-8')
  } catch {
    // License logging must never block validation.
  }
}

const normalizePath = (value: string | undefined): string | undefined => {
  const trimmed = value?.trim()
  return trimmed ? resolve(trimmed) : undefined
}

const getDllCandidates = (): string[] => {
  const customDllPath = normalizePath(process.env.LICENSE_DLL_PATH)
  const customDllDir = normalizePath(process.env.LICENSE_DLL_DIR)
  const appPath = app.getAppPath()

  return [
    customDllPath,
    customDllDir ? join(customDllDir, DLL_NAME) : undefined,
    join(process.resourcesPath, 'license', DLL_NAME),
    join(process.resourcesPath, 'app.asar.unpacked', 'license', DLL_NAME),
    join(appPath, 'License', DLL_NAME),
    join(process.cwd(), 'License', DLL_NAME),
    join(appPath, '..', 'License', DLL_NAME),
    join(appPath, '..', '..', 'License', DLL_NAME),
    join(__dirname, '..', '..', '..', 'License', DLL_NAME)
  ].filter((candidate): candidate is string => Boolean(candidate))
}

const resolveDllPath = (logFile: string | undefined): string | null => {
  const seen = new Set<string>()

  for (const candidate of getDllCandidates()) {
    const dllPath = resolve(candidate)
    const key = dllPath.toLowerCase()
    if (seen.has(key)) {
      continue
    }
    seen.add(key)

    const exists = existsSync(dllPath)
    writeLog(logFile, `probe dll path="${dllPath}" exists=${exists}`)

    if (!exists) {
      continue
    }

    try {
      const stats = statSync(dllPath)
      writeLog(
        logFile,
        `selected dll path="${dllPath}" size=${stats.size} modified=${stats.mtime.toISOString()}`
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      writeLog(logFile, `selected dll path="${dllPath}" stat failed: ${message}`)
    }

    logRuntimeSidecarFiles(dllPath, logFile)
    return dllPath
  }

  return null
}

const logRuntimeSidecarFiles = (dllPath: string, logFile: string | undefined): void => {
  const dllDir = dirname(dllPath)

  for (const fileName of LICENSE_RUNTIME_SIDECAR_FILES) {
    const sidecarPath = join(dllDir, fileName)
    const exists = existsSync(sidecarPath)

    if (!exists) {
      writeLog(logFile, `runtime sidecar path="${sidecarPath}" exists=false`)
      continue
    }

    try {
      const stats = statSync(sidecarPath)
      writeLog(
        logFile,
        `runtime sidecar path="${sidecarPath}" exists=true size=${stats.size} modified=${stats.mtime.toISOString()}`
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      writeLog(logFile, `runtime sidecar path="${sidecarPath}" stat failed: ${message}`)
    }
  }
}

const prependDllDirToPath = (dllPath: string, logFile: string | undefined): void => {
  const dllDir = dirname(dllPath)
  const currentPath = process.env.PATH ?? ''
  const pathEntries = currentPath.split(delimiter)
  const alreadyPresent = pathEntries.some((entry) => entry.toLowerCase() === dllDir.toLowerCase())

  if (alreadyPresent) {
    writeLog(logFile, `dll directory already in PATH: ${dllDir}`)
    return
  }

  process.env.PATH = `${dllDir}${delimiter}${currentPath}`
  writeLog(logFile, `prepended dll directory to PATH: ${dllDir}`)
}

const parsePort = (value: string | undefined): number => {
  const port = Number(value)
  return Number.isInteger(port) && port > 0 && port <= 65535 ? port : DEFAULT_LICENSE_PORT
}

const parseTimeout = (value: string | undefined): number => {
  const timeoutMs = Number(value)
  return Number.isInteger(timeoutMs) && timeoutMs > 0
    ? timeoutMs
    : DEFAULT_LICENSE_TIMEOUT_MS
}

const getLicenseEndpoint = (): { ip: string; port: number } => ({
  ip: process.env.LICENSE_SERVER_IP?.trim() || process.env.LICENSE_IP?.trim() || DEFAULT_LICENSE_IP,
  port: parsePort(process.env.LICENSE_SERVER_PORT || process.env.LICENSE_PORT)
})

const getWorkerScript = (): string => `
const RESULT_PREFIX = ${JSON.stringify(RESULT_PREFIX)};
const EXPORT_NAME = ${JSON.stringify(EXPORT_NAME)};

const writeResult = (payload) => {
  process.stdout.write(RESULT_PREFIX + JSON.stringify(payload) + '\\n');
};

try {
  const [dllPath, ip, portText] = process.argv.slice(1);
  const koffi = require('koffi');
  const lib = koffi.load(dllPath);
  const parseAndVerifyLicense = lib.func(
    'bool __stdcall ' + EXPORT_NAME + '(const char *ip, int port)'
  );
  const startedAt = Date.now();
  const ok = Boolean(parseAndVerifyLicense(ip, Number(portText)));
  writeResult({ ok, durationMs: Date.now() - startedAt });
  process.exit(ok ? 0 : 2);
} catch (error) {
  writeResult({
    ok: false,
    error: error && (error.stack || error.message) ? error.stack || error.message : String(error)
  });
  process.exit(1);
}
`

const getChildNodePath = (): string => {
  const nodePaths = [
    join(app.getAppPath(), 'node_modules'),
    join(process.resourcesPath, 'app.asar.unpacked', 'node_modules'),
    process.env.NODE_PATH
  ].filter((value): value is string => Boolean(value))

  return nodePaths.join(delimiter)
}

const parseWorkerResult = (
  stdout: string
): { ok?: boolean; error?: string; durationMs?: number } | null => {
  const line = stdout
    .split(/\r?\n/)
    .reverse()
    .find((entry) => entry.startsWith(RESULT_PREFIX))

  if (!line) {
    return null
  }

  return JSON.parse(line.slice(RESULT_PREFIX.length)) as {
    ok?: boolean
    error?: string
    durationMs?: number
  }
}

const runLicenseWorker = (
  dllPath: string,
  ip: string,
  port: number,
  timeoutMs: number,
  logFile: string | undefined
): Promise<boolean> =>
  new Promise((resolve, reject) => {
    let settled = false
    let stdout = ''
    let stderr = ''
    const childNodePath = getChildNodePath()
    const workerCwd = dirname(dllPath)
    const startedAt = Date.now()

    writeLog(
      logFile,
      `spawning license worker execPath="${process.execPath}" cwd="${workerCwd}" timeoutMs=${timeoutMs}`
    )
    writeLog(logFile, `worker NODE_PATH="${childNodePath}"`)

    const child = spawn(process.execPath, ['-e', getWorkerScript(), dllPath, ip, String(port)], {
      cwd: workerCwd,
      windowsHide: true,
      env: {
        ...process.env,
        ELECTRON_RUN_AS_NODE: '1',
        NODE_PATH: childNodePath
      }
    })

    writeLog(logFile, `license worker pid=${child.pid ?? 'unknown'}`)

    const timer = setTimeout(() => {
      if (settled) {
        return
      }
      settled = true
      child.kill()
      reject(new Error(`License validation timed out after ${timeoutMs}ms.`))
    }, timeoutMs)

    child.stdout?.on('data', (chunk: Buffer) => {
      stdout += chunk.toString('utf-8')
    })

    child.stderr?.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf-8')
    })

    child.on('error', (error) => {
      if (settled) {
        return
      }
      settled = true
      clearTimeout(timer)
      writeLog(logFile, `license worker spawn error: ${error.message}`)
      reject(error)
    })

    child.on('exit', (code, signal) => {
      if (settled) {
        return
      }

      settled = true
      clearTimeout(timer)

      const elapsedMs = Date.now() - startedAt
      writeLog(
        logFile,
        `license worker exited code=${code ?? 'null'} signal=${signal ?? 'null'} elapsedMs=${elapsedMs}`
      )

      if (stderr.trim()) {
        writeLog(logFile, `license worker stderr: ${stderr.trim()}`)
      }

      try {
        const result = parseWorkerResult(stdout)
        if (!result) {
          const trimmedStdout = stdout.trim()
          if (trimmedStdout) {
            writeLog(logFile, `license worker stdout without marker: ${trimmedStdout}`)
          }
          reject(new Error(`License worker exited without a result. code=${code ?? 'null'}`))
          return
        }

        writeLog(
          logFile,
          `license worker result ok=${Boolean(result.ok)} durationMs=${result.durationMs ?? 'unknown'}`
        )

        if (result.error) {
          reject(new Error(result.error))
          return
        }

        resolve(Boolean(result.ok))
      } catch (error) {
        reject(error)
      }
    })
  })

export const verifyLicense = async (): Promise<LicenseResult> => {
  const logFile = resolveLogFile()
  writeLog(logFile, 'starting license validation')
  writeLog(
    logFile,
    `runtime platform=${process.platform} arch=${process.arch} electron=${process.versions.electron ?? 'unknown'} node=${process.versions.node}`
  )
  writeLog(
    logFile,
    `paths appPath="${app.getAppPath()}" resourcesPath="${process.resourcesPath}" cwd="${process.cwd()}"`
  )

  if (process.platform !== 'win32') {
    const reason = 'License validator DLL is only supported on Windows.'
    writeLog(logFile, reason)
    return { ok: false, reason, logFile }
  }

  const dllPath = resolveDllPath(logFile)
  if (!dllPath) {
    const reason = `Cannot find ${DLL_NAME}.`
    writeLog(logFile, reason)
    return { ok: false, reason, logFile }
  }

  try {
    prependDllDirToPath(dllPath, logFile)

    const { ip, port } = getLicenseEndpoint()
    const timeoutMs = parseTimeout(process.env.LICENSE_CHECK_TIMEOUT_MS)
    writeLog(logFile, `calling ${EXPORT_NAME}("${ip}", ${port}) from "${dllPath}"`)

    const ok = await runLicenseWorker(dllPath, ip, port, timeoutMs, logFile)
    writeLog(logFile, `${EXPORT_NAME} returned ${ok}`)

    if (!ok) {
      return {
        ok: false,
        reason: 'License validation failed.',
        logFile
      }
    }

    writeLog(logFile, 'license validation passed')
    return { ok: true, logFile }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const reason = `License validation error: ${message}`
    writeLog(logFile, reason)
    return { ok: false, reason, logFile }
  }
}
