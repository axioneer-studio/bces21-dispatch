import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const logoPath = join(process.cwd(), 'public', 'images', 'logo.png')
const logoBuffer = readFileSync(logoPath)

export default defineEventHandler((event) => {
  setHeader(event, 'Content-Type', 'image/png')
  setHeader(event, 'Cache-Control', 'public, max-age=86400')
  return logoBuffer
})