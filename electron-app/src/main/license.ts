import { app } from 'electron'
import { delimiter, dirname, join, resolve } from 'path'
import { appendFileSync, existsSync, mkdirSync } from 'fs'
import { spawn } from 'child_process'

const DLL_NAME = 'LicenseVallidator.dll'
const EXPORT_NAME = 'ParseAndVerifyLicense'
const RESULT_PREFIX = '__LICENSE_RESULT__'
const DEFAULT_LICENSE_IP = '127.0.0.1'
const DEFAULT_LICENSE_PORT = 7681
const DEFAULT_LICENSE_TIMEOUT_MS = 15000

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
    // Logging must never block license validation.
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
    join(appPath, '..', 'License', DLL_NAME),
    join(appPath, '..', 'License', 'dll', DLL_NAME),
    join(appPath, '..', '..', 'License', DLL_NAME),
    join(appPath, '..', '..', 'License', 'dll', DLL_NAME),
    join(__dirname, '..', '..', '..', 'License', DLL_NAME),
    join(process.cwd(), '..', 'License', DLL_NAME)
  ].filter((candidate): candidate is string => Boolean(candidate))
}

const resolveDllPath = (logFile: string | undefined): string | null => {
  for (const candidate of getDllCandidates()) {
    const dllPath = resolve(candidate)
    const exists = existsSync(dllPath)
    writeLog(logFile, `probe ${dllPath} exists=${exists}`)

    if (exists) {
      return dllPath
    }
  }

  return null
}

const prependDllDirToPath = (dllPath: string): void => {
  const dllDir = dirname(dllPath)
  const currentPath = process.env.PATH ?? ''
  const pathEntries = currentPath.split(delimiter)
  const alreadyPresent = pathEntries.some((entry) => entry.toLowerCase() === dllDir.toLowerCase())

  if (!alreadyPresent) {
    process.env.PATH = `${dllDir}${delimiter}${currentPath}`
  }
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
  const ok = Boolean(parseAndVerifyLicense(ip, Number(portText)));
  writeResult({ ok });
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

const parseWorkerResult = (stdout: string): { ok?: boolean; error?: string } | null => {
  const line = stdout
    .split(/\r?\n/)
    .reverse()
    .find((entry) => entry.startsWith(RESULT_PREFIX))

  if (!line) {
    return null
  }

  return JSON.parse(line.slice(RESULT_PREFIX.length)) as { ok?: boolean; error?: string }
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
    const child = spawn(process.execPath, ['-e', getWorkerScript(), dllPath, ip, String(port)], {
      cwd: process.resourcesPath,
      windowsHide: true,
      env: {
        ...process.env,
        ELECTRON_RUN_AS_NODE: '1',
        NODE_PATH: getChildNodePath()
      }
    })

    const timer = setTimeout(() => {
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
      reject(error)
    })

    child.on('exit', (code) => {
      if (settled) {
        return
      }

      settled = true
      clearTimeout(timer)

      if (stderr.trim()) {
        writeLog(logFile, `worker stderr: ${stderr.trim()}`)
      }

      try {
        const result = parseWorkerResult(stdout)
        if (!result) {
          reject(new Error(`License worker exited without a result. code=${code ?? 'null'}`))
          return
        }

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
    prependDllDirToPath(dllPath)

    const { ip, port } = getLicenseEndpoint()
    const timeoutMs = parseTimeout(process.env.LICENSE_CHECK_TIMEOUT_MS)
    writeLog(logFile, `calling ${EXPORT_NAME}("${ip}", ${port}) from ${dllPath}`)

    const ok = await runLicenseWorker(
      dllPath,
      ip,
      port,
      timeoutMs,
      logFile
    )
    writeLog(logFile, `${EXPORT_NAME} result=${ok}`)

    if (!ok) {
      return {
        ok: false,
        reason: 'License validation failed.',
        logFile
      }
    }

    return { ok: true, logFile }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const reason = `License validation error: ${message}`
    writeLog(logFile, reason)
    return { ok: false, reason, logFile }
  }
}
