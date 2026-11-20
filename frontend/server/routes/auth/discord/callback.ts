import { getQuery } from 'h3'
import { $fetch } from 'ofetch'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const code = query.code as string | undefined
  const state = query.state as string | undefined
  const error = query.error as string | undefined

  if (error) {
    event.node.res.writeHead(302, { 'Location': `/?error=${error}` })
    event.node.res.end()
    return
  }

  if (!code || !state) {
    event.node.res.writeHead(302, { 'Location': '/?error=missing_code' })
    event.node.res.end()
    return
  }

  const config = useRuntimeConfig()
  const apiBase = String(config.public.apiBase || 'http://localhost:8000').replace(/\/$/, '')

  // Transmet les cookies (dont le cookie d'état OAuth) au backend
  const headers = event.node.req.headers
  let response: any
  try {
    response = await $fetch.raw(`${apiBase}/api/auth/discord/exchange`, {
      method: 'POST',
      body: { code, state },
      headers: {
        cookie: headers.cookie,
      },
    })
  } catch (err) {
    event.node.res.writeHead(302, { 'Location': '/?error=discord_failed' })
    event.node.res.end()
    return
  }

  const data = (response.data ?? response._data) as {
    redirect?: string
    message?: string
    token?: string
  } | undefined
  const redirectUrl = data?.redirect || '/dispatch'

  // Pose le cookie de session et redirige dans une seule réponse HTTP.
  // Domain=localhost permet au cookie d'être envoyé aussi au backend
  // (localhost:8000) depuis le frontend (localhost:3000), notamment pour
  // le WebSocket qui se connecte directement au backend.
  if (data?.token) {
    event.node.res.writeHead(302, {
      'Location': redirectUrl,
      'Set-Cookie': `bces_session=${data.token}; Domain=localhost; Path=/; HttpOnly; SameSite=Lax; Max-Age=${
        14 * 24 * 60 * 60
      }`,
    })
    event.node.res.end()
    return
  }

  event.node.res.writeHead(302, { 'Location': redirectUrl })
  event.node.res.end()
})
