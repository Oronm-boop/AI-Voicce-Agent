import { app } from 'electron'
import { join } from 'path'
import { existsSync, appendFileSync, mkdirSync } from 'fs'
import { is } from '@electron-toolkit/utils'

export interface LicenseResult {
  ok: boolean
  reason?: string
  logFile?: string
}

const DLL_NAME = 'LicenseVallidator.dll'
const EXPORT_NAME = 'ParseAndVerifyLicense'

// 参数随意，DLL 内部已写死真实校验逻辑（见 License/LicenseParser.h）
const DUMMY_IP = '127.0.0.1'
const DUMMY_PORT = 7681

let logFilePath: string | null = null

const formatTimestamp = (): string => {
  const now = new Date()
  const pad = (value: number): string => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

const resolveLogFilePath = (): string => {
  if (logFilePath) {
    return logFilePath
  }

  const logDir = join(app.getPath('userData'), 'logs')
  mkdirSync(logDir, { recursive: true })
  logFilePath = join(logDir, 'license-check.log')
  return logFilePath
}

/** 开发/测试环境均写入控制台与本地日志文件，便于排查授权问题 */
const writeLicenseLog = (level: 'info' | 'warn' | 'error', message: string): void => {
  const line = `[${formatTimestamp()}] [license] [${level.toUpperCase()}] ${message}`
  const logFn =
    level === 'error' ? console.error : level === 'warn' ? console.warn : console.log
  logFn(line)

  try {
    appendFileSync(resolveLogFilePath(), `${line}\n`, 'utf8')
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error)
    console.error(`[license] 写入日志文件失败: ${errMsg}`)
  }
}

/**
 * 解析存放授权 DLL 及其依赖（uv/websockets/libssl/libcrypto/zlib）的目录。
 * 开发环境指向仓库内的 License/dll，打包环境指向 extraResources 复制出的 license 目录。
 */
const resolveLicenseDir = (): { dir: string | null; checked: string[] } => {
  const candidates = [
    is.dev ? join(app.getAppPath(), '..', 'License', 'dll') : null,
    join(process.resourcesPath, 'license'),
    join(app.getAppPath(), '..', 'License', 'dll')
  ].filter((value): value is string => Boolean(value))

  const checked: string[] = []
  for (const dir of candidates) {
    const dllPath = join(dir, DLL_NAME)
    const exists = existsSync(dllPath)
    checked.push(`${dir} -> ${exists ? 'found' : 'missing'}`)
    if (exists) {
      return { dir, checked }
    }
  }

  return { dir: null, checked }
}

/**
 * 调用 LicenseVallidator.dll 的 ParseAndVerifyLicense 进行授权校验。
 * 任何加载/调用异常都按未授权处理（fail-closed），保证授权闸门有效。
 */
export const verifyLicense = async (): Promise<LicenseResult> => {
  const logFile = resolveLogFilePath()
  writeLicenseLog('info', '========== 开始授权校验 ==========')
  writeLicenseLog('info', `运行环境: ${is.dev ? 'development' : 'production'}`)
  writeLicenseLog('info', `app.getAppPath(): ${app.getAppPath()}`)
  writeLicenseLog('info', `process.resourcesPath: ${process.resourcesPath}`)
  writeLicenseLog('info', `process.cwd(): ${process.cwd()}`)
  writeLicenseLog('info', `日志文件: ${logFile}`)

  if (process.env.LICENSE_SKIP === '1') {
    writeLicenseLog('warn', 'LICENSE_SKIP=1，跳过授权校验（仅用于本地调试）')
    return { ok: true, reason: 'skipped', logFile }
  }

  const { dir: licenseDir, checked } = resolveLicenseDir()
  writeLicenseLog('info', `DLL 搜索路径:\n  ${checked.join('\n  ')}`)

  if (!licenseDir) {
    const reason = `未找到 ${DLL_NAME}，无法完成授权校验`
    writeLicenseLog('error', reason)
    return { ok: false, reason, logFile }
  }

  writeLicenseLog('info', `使用授权目录: ${licenseDir}`)

  // 把 DLL 目录加入 PATH，确保依赖 DLL 能被 Windows 加载器找到
  const pathSep = process.platform === 'win32' ? ';' : ':'
  process.env.PATH = `${licenseDir}${pathSep}${process.env.PATH ?? ''}`
  writeLicenseLog('info', `已将授权目录加入 PATH 前缀: ${licenseDir}`)

  const dllPath = join(licenseDir, DLL_NAME)
  writeLicenseLog('info', `准备加载 DLL: ${dllPath}`)

  try {
    // 延迟到运行时 require，避免开发期类型/打包阶段对原生模块的额外依赖
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const koffi = require('koffi')
    writeLicenseLog('info', 'koffi 模块加载成功')

    const lib = koffi.load(dllPath)
    writeLicenseLog('info', `${DLL_NAME} 加载成功`)

    const parseAndVerifyLicense = lib.func(
      `bool __stdcall ${EXPORT_NAME}(const char *ip, int port)`
    )
    writeLicenseLog('info', `已解析导出函数: ${EXPORT_NAME}`)

    writeLicenseLog(
      'info',
      `调用 ${EXPORT_NAME}(ip="${DUMMY_IP}", port=${DUMMY_PORT}) ...`
    )
    const startedAt = Date.now()
    const rawResult = parseAndVerifyLicense(DUMMY_IP, DUMMY_PORT)
    const elapsedMs = Date.now() - startedAt

    writeLicenseLog('info', `${EXPORT_NAME} 原始返回值: ${String(rawResult)} (类型: ${typeof rawResult})`)
    writeLicenseLog('info', `${EXPORT_NAME} 调用耗时: ${elapsedMs}ms`)

    const ok = Boolean(rawResult)
    if (ok) {
      writeLicenseLog('info', '授权校验通过')
      writeLicenseLog('info', '========== 授权校验结束 ==========')
      return { ok: true, logFile }
    }

    const reason = '授权校验未通过（ParseAndVerifyLicense 返回 false）'
    writeLicenseLog('error', reason)
    writeLicenseLog('info', '========== 授权校验结束 ==========')
    return { ok: false, reason, logFile }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const stack = error instanceof Error ? error.stack : undefined
    writeLicenseLog('error', `调用 ${EXPORT_NAME} 异常: ${message}`)
    if (stack) {
      writeLicenseLog('error', `异常堆栈:\n${stack}`)
    }
    writeLicenseLog('info', '========== 授权校验结束 ==========')
    return { ok: false, reason: message, logFile }
  }
}
