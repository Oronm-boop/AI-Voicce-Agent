import { spawn } from 'child_process'
import process from 'process'

const MCP_COMMAND = 'uvx'
const MCP_ARGS = [
  'windows-mcp',
  'serve',
  '--transport', 'streamable-http',
  '--host', '127.0.0.1',
  '--port', '8000'
]

console.log('[dev] Starting Windows-MCP server...')
const mcp = spawn(MCP_COMMAND, MCP_ARGS, {
  stdio: 'inherit',
  shell: true
})

mcp.on('error', (err) => {
  console.warn('[dev] Windows-MCP failed to start:', err.message)
  console.warn('[dev] Continuing without Windows-MCP — computer control will not work.')
})

console.log('[dev] Starting electron-vite dev server...')
const vite = spawn('npx', ['electron-vite', 'dev'], {
  stdio: 'inherit',
  shell: true
})

vite.on('exit', (code) => {
  console.log(`[dev] electron-vite exited (code ${code}), stopping Windows-MCP...`)
  mcp.kill()
  process.exit(code ?? 0)
})

const cleanup = () => {
  mcp.kill()
  process.exit()
}

process.on('SIGINT', cleanup)
process.on('SIGTERM', cleanup)
