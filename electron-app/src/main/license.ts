import { app } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { is } from '@electron-toolkit/utils'

export interface LicenseResult {
  ok: boolean
  reason?: string
}

const DLL_NAME = 'LicenseVallidator.dll'
const EXPORT_NAME = 'ParseAndVerifyLicense'

// 参数随意，DLL 内部已写死真实校验逻辑（见 License/LicenseParser.h）
const DUMMY_IP = '127.0.0.1'
const DUMMY_PORT = 7681

/**
 * 解析存放授权 DLL 及其依赖（uv/websockets/libssl/libcrypto/zlib）的目录。
 * 开发环境指向仓库内的 License/dll，打包环境指向 extraResources 复制出的 license 目录。
 */
const resolveLicenseDir = (): string | null => {
  const candidates = [
    is.dev ? join(app.getAppPath(), '..', 'License', 'dll') : null,
    join(process.resourcesPath, 'license'),
    join(app.getAppPath(), '..', 'License', 'dll')
  ].filter((value): value is string => Boolean(value))

  for (const dir of candidates) {
    if (existsSync(join(dir, DLL_NAME))) {
      return dir
    }
  }
  return null
}

/**
 * 调用 LicenseVallidator.dll 的 ParseAndVerifyLicense 进行授权校验。
 * 任何加载/调用异常都按未授权处理（fail-closed），保证授权闸门有效。
 */
export const verifyLicense = async (): Promise<LicenseResult> => {
  if (process.env.LICENSE_SKIP === '1') {
    console.warn('[license] LICENSE_SKIP=1，跳过授权校验（仅用于本地调试）')
    return { ok: true, reason: 'skipped' }
  }

  const licenseDir = resolveLicenseDir()
  if (!licenseDir) {
    const reason = `未找到 ${DLL_NAME}，无法完成授权校验`
    console.error(`[license] ${reason}`)
    return { ok: false, reason }
  }

  // 把 DLL 目录加入 PATH，确保依赖 DLL 能被 Windows 加载器找到
  process.env.PATH = `${licenseDir}${process.platform === 'win32' ? ';' : ':'}${process.env.PATH ?? ''}`

  const dllPath = join(licenseDir, DLL_NAME)

  try {
    // 延迟到运行时 require，避免开发期类型/打包阶段对原生模块的额外依赖
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const koffi = require('koffi')
    const lib = koffi.load(dllPath)
    const parseAndVerifyLicense = lib.func(
      `bool __stdcall ${EXPORT_NAME}(const char *ip, int port)`
    )

    const ok = Boolean(parseAndVerifyLicense(DUMMY_IP, DUMMY_PORT))
    console.log(`[license] ${EXPORT_NAME} 返回: ${ok}`)
    return ok ? { ok: true } : { ok: false, reason: '授权校验未通过' }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.error(`[license] 调用 ${EXPORT_NAME} 失败: ${message}`)
    return { ok: false, reason: message }
  }
}
