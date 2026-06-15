import { app } from 'electron'
import { join } from 'path'
import { existsSync, mkdirSync, appendFileSync, readdirSync } from 'fs'
import { is } from '@electron-toolkit/utils'

const DLL_NAME = 'LicenseVallidator.dll'
const EXPORT_NAME = 'ParseAndVerifyLicense'
const DEVICE_INFO_EXPORT = 'GetDeviceInfo'

// 参数随便传：DLL 内部已写死，仅取返回值判断是否授权
const DUMMY_IP = '127.0.0.1'
const DUMMY_PORT = 7681

export interface LicenseResult {
  ok: boolean
  reason?: string
  logFile?: string
}

const resolveLogFile = (): string => {
  try {
    const dir = app.getPath('userData')
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }
    return join(dir, 'license-check.log')
  } catch {
    return join(app.getPath('temp'), 'license-check.log')
  }
}

const writeLog = (logFile: string, message: string): void => {
  const line = `[${new Date().toISOString()}] ${message}\n`
  try {
    appendFileSync(logFile, line, 'utf-8')
  } catch {
    // 日志写入失败不应阻断校验流程
  }
  console.log(`[license] ${message}`)
}

const writeSection = (logFile: string, title: string): void => {
  writeLog(logFile, `── ${title} ${'─'.repeat(Math.max(0, 50 - title.length))}`)
}

const logEnvironment = (logFile: string): void => {
  writeSection(logFile, '运行环境')
  writeLog(logFile, `platform=${process.platform}, arch=${process.arch}`)
  writeLog(logFile, `dev=${is.dev}, electron=${process.versions.electron}, node=${process.versions.node}`)
  writeLog(logFile, `appPath=${app.getAppPath()}`)
  writeLog(logFile, `resourcesPath=${process.resourcesPath}`)
  writeLog(logFile, `userData=${app.getPath('userData')}`)
  writeLog(logFile, `LICENSE_DLL_DIR=${process.env.LICENSE_DLL_DIR ?? '(未设置)'}`)
}

const logDllCandidates = (logFile: string): string | null => {
  writeSection(logFile, 'DLL 路径探测')

  const candidates = [
    { label: 'LICENSE_DLL_DIR', path: process.env.LICENSE_DLL_DIR?.trim() },
    { label: 'resources/license', path: join(process.resourcesPath, 'license') },
    { label: 'dev: ../License/dll', path: join(app.getAppPath(), '..', 'License', 'dll') },
    { label: 'dev: ../../License/dll', path: join(app.getAppPath(), '..', '..', 'License', 'dll') }
  ]

  let resolvedDir: string | null = null

  for (const { label, path } of candidates) {
    if (!path) {
      writeLog(logFile, `[${label}] 跳过（路径为空）`)
      continue
    }

    const dllPath = join(path, DLL_NAME)
    const dirExists = existsSync(path)
    const dllExists = existsSync(dllPath)
    writeLog(
      logFile,
      `[${label}] dir=${path}, dirExists=${dirExists}, dllExists=${dllExists}`
    )

    if (dllExists && !resolvedDir) {
      resolvedDir = path
      writeLog(logFile, `[${label}] ✓ 命中`)
    }
  }

  return resolvedDir
}

const logDllDirectory = (logFile: string, dllDir: string): void => {
  writeSection(logFile, 'DLL 目录内容')
  writeLog(logFile, `dllDir=${dllDir}`)

  try {
    const files = readdirSync(dllDir).sort()
    writeLog(logFile, `文件数=${files.length}`)
    for (const file of files) {
      writeLog(logFile, `  - ${file}`)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    writeLog(logFile, `读取目录失败: ${message}`)
  }
}

const logPathUpdate = (logFile: string, dllDir: string): void => {
  writeSection(logFile, 'PATH 更新')
  if (process.platform !== 'win32') {
    writeLog(logFile, '非 Windows 平台，跳过 PATH 更新')
    return
  }

  const pathBefore = process.env.PATH ?? ''
  const alreadyInPath = pathBefore.split(';').some((p) => p.toLowerCase() === dllDir.toLowerCase())
  writeLog(logFile, `dllDir 已在 PATH 中: ${alreadyInPath}`)

  if (!alreadyInPath) {
    process.env.PATH = `${dllDir};${pathBefore}`
    writeLog(logFile, `已将 dllDir 前置到 PATH`)
  }
}

interface DeviceInfo {
  vendor: string
  name: string
  macs: string
}

const tryGetDeviceInfo = (lib: { func: (sig: string) => unknown }, logFile: string): DeviceInfo | null => {
  writeSection(logFile, '设备信息 (GetDeviceInfo)')

  try {
    const getDeviceInfo = lib.func(
      `bool __stdcall ${DEVICE_INFO_EXPORT}(char *vendor, char *name, char *macs)`
    ) as (vendor: Buffer, name: Buffer, macs: Buffer) => boolean

    const vendorBuf = Buffer.alloc(256)
    const nameBuf = Buffer.alloc(256)
    const macsBuf = Buffer.alloc(1024)

    const ok = getDeviceInfo(vendorBuf, nameBuf, macsBuf)
    const vendor = vendorBuf.toString('utf-8').replace(/\0.*$/, '').trim()
    const name = nameBuf.toString('utf-8').replace(/\0.*$/, '').trim()
    const macs = macsBuf.toString('utf-8').replace(/\0.*$/, '').trim()

    writeLog(logFile, `GetDeviceInfo 返回: ${ok}`)
    writeLog(logFile, `  vendor=${vendor || '(空)'}`)
    writeLog(logFile, `  name=${name || '(空)'}`)
    writeLog(logFile, `  macs=${macs || '(空)'}`)

    return { vendor, name, macs }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    writeLog(logFile, `GetDeviceInfo 调用失败（非致命）: ${message}`)
    return null
  }
}

export const verifyLicense = async (): Promise<LicenseResult> => {
  const startedAt = Date.now()
  const logFile = resolveLogFile()

  writeLog(logFile, '')
  writeLog(logFile, '══════════════════════════════════════════════════')
  writeLog(logFile, '开始授权校验')
  writeLog(logFile, '══════════════════════════════════════════════════')

  logEnvironment(logFile)

  const dllDir = logDllCandidates(logFile)
  if (!dllDir) {
    const reason = `未找到授权组件 ${DLL_NAME}`
    writeSection(logFile, '校验结果')
    writeLog(logFile, `结果=失败, 原因=${reason}`)
    writeLog(logFile, `耗时=${Date.now() - startedAt}ms`)
    return { ok: false, reason, logFile }
  }

  const dllPath = join(dllDir, DLL_NAME)
  logDllDirectory(logFile, dllDir)
  logPathUpdate(logFile, dllDir)

  try {
    writeSection(logFile, '加载 DLL')
    writeLog(logFile, `dllPath=${dllPath}`)
    writeLog(logFile, `导出函数=${EXPORT_NAME}`)

    const loadStartedAt = Date.now()
    // koffi 为原生模块，main 进程已外部化（externalizeDepsPlugin）
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const koffi = require('koffi')
    const lib = koffi.load(dllPath)
    writeLog(logFile, `koffi.load 完成, 耗时=${Date.now() - loadStartedAt}ms`)

    tryGetDeviceInfo(lib, logFile)

    writeSection(logFile, '调用 ParseAndVerifyLicense')
    const parseAndVerifyLicense = lib.func(
      `bool __stdcall ${EXPORT_NAME}(const char *ip, int port)`
    ) as (ip: string, port: number) => boolean

    writeLog(logFile, `入参: ip="${DUMMY_IP}", port=${DUMMY_PORT}`)
    const callStartedAt = Date.now()
    const raw = parseAndVerifyLicense(DUMMY_IP, DUMMY_PORT)
    const callDuration = Date.now() - callStartedAt

    const ok = Boolean(raw)
    writeLog(logFile, `返回值: raw=${raw}, type=${typeof raw}, boolean=${ok}`)
    writeLog(logFile, `调用耗时=${callDuration}ms`)

    writeSection(logFile, '校验结果')
    if (ok) {
      writeLog(logFile, '结果=通过')
      writeLog(logFile, `总耗时=${Date.now() - startedAt}ms`)
      return { ok: true, logFile }
    }

    const reason = '授权校验未通过（ParseAndVerifyLicense 返回 false）'
    writeLog(logFile, `结果=失败, 原因=${reason}`)
    writeLog(logFile, `提示: 可能原因包括 License 缺失/过期/设备不匹配/连接失败等，请对照 DLL 错误码排查`)
    writeLog(logFile, `总耗时=${Date.now() - startedAt}ms`)
    return { ok: false, reason, logFile }
  } catch (error) {
    writeSection(logFile, '异常信息')
    const message = error instanceof Error ? error.message : String(error)
    const stack = error instanceof Error ? error.stack : undefined
    writeLog(logFile, `message=${message}`)
    if (stack) {
      for (const line of stack.split('\n')) {
        writeLog(logFile, `  ${line.trim()}`)
      }
    }

    const reason = `授权校验异常: ${message}`
    writeLog(logFile, `结果=失败, 原因=${reason}`)
    writeLog(logFile, `总耗时=${Date.now() - startedAt}ms`)
    return { ok: false, reason, logFile }
  }
}
