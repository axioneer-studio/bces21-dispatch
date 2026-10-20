import type { DispatchSnapshot } from './useDispatchStore'

const PING_INTERVAL_MS = 25_000
const MAX_BACKOFF_MS = 30_000
/** Codes 1008 (policy) et 4401 → refus d'auth : ne pas réessayer en boucle. */
const AUTH_CLOSE_CODES = new Set([1008, 4401, 4403])

export const useDispatchSocket = () => {
  const { applySnapshot, setConnected } = useDispatchStore()
  const config = useRuntimeConfig()

  let socket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null
  let attempt = 0
  let alive = true
  /**bloque toute reconnexion après un refus d'authentification. */
  let authBlocked = false

  /**
   * On passe par le même origine que la page (proxy Nitro `/api/ws/**`) afin que
   * le cookie `bces_session` parte dans la requête d'upgrade. Utiliser
   * directement `apiBase` (ex. http://localhost:8000) poserait des problems de
   * cookie inter-ports selon le navigateur.
   */
  function buildUrl(): string {
    if (typeof window === 'undefined') return ''
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/api/ws/dispatch`
  }

  function clearTimers() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = null
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    attempt += 1
    // Backoff exponentiel plafonné : 1s, 2s, 4s, 8s… 30s max.
    const delay = Math.min(1000 * 2 ** (attempt - 1), MAX_BACKOFF_MS)
    reconnectTimer = setTimeout(() => {
      if (alive && !authBlocked) connect()
    }, delay)
  }

  function connect() {
    if (!import.meta.client) return
    if (authBlocked) return
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return
    }

    try {
      socket = new WebSocket(buildUrl())
    } catch {
      scheduleReconnect()
      return
    }

    socket.onopen = () => {
      attempt = 0
      setConnected(true)
      if (pingTimer) clearInterval(pingTimer)
      pingTimer = setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
      }, PING_INTERVAL_MS)
    }

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as {
          type: string
          data: DispatchSnapshot
        }
        if (msg.type === 'snapshot' && msg.data) {
          applySnapshot(msg.data)
        }
      } catch {
        /* message illisible : ignoré */
      }
    }

    socket.onerror = () => {
      // onerror est toujours suivi de onclose, la reconnexion y est gérée.
      setConnected(false)
    }

    socket.onclose = (event) => {
      setConnected(false)
      if (pingTimer) {
        clearInterval(pingTimer)
        pingTimer = null
      }
      socket = null
      if (AUTH_CLOSE_CODES.has(event.code)) {
        authBlocked = true
        return
      }
      if (alive) scheduleReconnect()
    }
  }

  function disconnect() {
    alive = false
    clearTimers()
    if (socket) {
      socket.onclose = null
      socket.close()
      socket = null
    }
  }

  return { connect, disconnect }
}