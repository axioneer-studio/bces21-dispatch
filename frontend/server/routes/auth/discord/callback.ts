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
  // Pas de Domain explicite : le cookie est scopé à l'hôte courant, ce qui
  // fonctionne sur localhost:3000 → localhost:8000 en dev, et sur le domaine
  // courant en prod (le cookie est transmis par le proxy Nuxt au backend).
  if (data?.token) {
    event.node.res.writeHead(302, {
      'Location': redirectUrl,
      'Set-Cookie': `bces_session=${data.token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${
        14 * 24 * 60 * 60
      }`,
    })
    event.node.res.end()
    return
  }

  event.node.res.writeHead(302, { 'Location': redirectUrl })
  event.node.res.end()
})
