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
    const fetchError = err as { statusCode?: number; status?: number }
    const errorCode = fetchError.statusCode === 429 || fetchError.status === 429
      ? 'discord_rate_limited'
      : 'discord_failed'
    event.node.res.writeHead(302, { 'Location': `/?error=${errorCode}` })
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
  // Sur localhost (dev), Domain=localhost permet au cookie d'être envoyé
  // aussi au backend (localhost:8000) depuis le frontend (localhost:3000).
  // En production, Domain=.axioneer.com permet au cookie d'être envoyé
  // aussi au backend API (api.bces.axioneer.com) depuis le frontend
  // (bces.axioneer.com), notamment pour le WebSocket.
  // SameSite=None + Secure est requis en HTTPS pour que le cookie soit
  // envoyé sur les connexions cross-site (WebSocket vers api.bces.axioneer.com).
  const host = event.node.req.headers.host || ''
  const isLocalhost =
    host.startsWith('localhost') ||
    host.startsWith('127.0.0.1') ||
    host.startsWith('::1')
  const isHttps =
    event.node.req.headers['x-forwarded-proto'] === 'https'
  const sameSite = isHttps ? 'None' : 'Lax'
  const secure = isHttps ? '; Secure' : ''
  const domainAttr = isLocalhost
    ? '; Domain=localhost'
    : '; Domain=.axioneer.com'
  if (data?.token) {
    // Transmet aussi le token en paramètre d'URL pour que le frontend
    // puisse l'utiliser pour l'authentification WebSocket (cross-origin).
    const redirectWithToken = `${redirectUrl}${
      redirectUrl.includes('?') ? '&' : '?'
    }token=${encodeURIComponent(data.token)}`
    const sessionCookie =
      `bces_session=${data.token}; Path=/; HttpOnly; ` +
      `SameSite=${sameSite}${secure}${domainAttr}; Max-Age=${14 * 24 * 60 * 60}`
    event.node.res.writeHead(302, {
      'Location': redirectWithToken,
      'Set-Cookie': sessionCookie,
    })
    event.node.res.end()
    return
  }

  const clearedSessionCookie =
    `bces_session=; Path=/; HttpOnly; ` +
    `SameSite=${sameSite}${secure}${domainAttr}; Max-Age=0`
  const clearedStateCookie = state
    ? `bces_oauth_state_${state}=; Path=/; HttpOnly; ` +
      `SameSite=${sameSite}${secure}${domainAttr}; Max-Age=0`
    : ''
  event.node.res.writeHead(302, {
    'Location': redirectUrl,
    'Set-Cookie': clearedStateCookie
      ? [clearedSessionCookie, clearedStateCookie]
      : clearedSessionCookie
  })
  event.node.res.end()
})
