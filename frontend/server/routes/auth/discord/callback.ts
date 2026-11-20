import { getQuery, sendRedirect, setHeader } from 'h3'
import { $fetch } from 'ofetch'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const code = query.code as string | undefined
  const state = query.state as string | undefined
  const error = query.error as string | undefined

  if (error) {
    return sendRedirect(event, `/?error=${error}`, 302)
  }

  if (!code || !state) {
    return sendRedirect(event, '/?error=missing_code', 302)
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
    return sendRedirect(event, '/?error=discord_failed', 302)
  }

  const data = (response.data ?? response._data) as {
    redirect?: string
    message?: string
    token?: string
  } | undefined
  const redirectUrl = data?.redirect || '/dispatch'

  // Pose le cookie de session depuis le token retourné par l'API
  // Domain=localhost permet de partager le cookie entre :3000 et :8000
  if (data?.token) {
    setHeader(
      event,
      'set-cookie',
      `bces_session=${data.token}; Domain=localhost; Path=/; HttpOnly; SameSite=Lax; Max-Age=${
        14 * 24 * 60 * 60
      }`
    )
  }

  return sendRedirect(event, redirectUrl, 302)
})
