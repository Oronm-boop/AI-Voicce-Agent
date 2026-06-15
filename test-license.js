const path = require('path')
const fs = require('fs')

const DLL_NAME = 'LicenseVallidator.dll'
const EXPORT_NAME = 'ParseAndVerifyLicense'
const DUMMY_IP = '127.0.0.1'
const DUMMY_PORT = 7681

const licenseDir = path.join(__dirname, 'License', 'dll')
const dllPath = path.join(licenseDir, DLL_NAME)

if (!fs.existsSync(dllPath)) {
  console.error(`未找到 DLL: ${dllPath}`)
  process.exit(1)
}

process.env.PATH = `${licenseDir};${process.env.PATH ?? ''}`

const koffiPath = path.join(__dirname, 'electron-app', 'node_modules', 'koffi')
const koffi = require(koffiPath)

const lib = koffi.load(dllPath)
const parseAndVerifyLicense = lib.func(
  `bool __stdcall ${EXPORT_NAME}(const char *ip, int port)`
)

const raw = parseAndVerifyLicense(DUMMY_IP, DUMMY_PORT)

console.log('DUMMY_IP:', DUMMY_IP)
console.log('DUMMY_PORT:', DUMMY_PORT)
console.log('raw result:', raw)
console.log('ok:', Boolean(raw))
