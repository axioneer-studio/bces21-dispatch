export type ToastType = 'info' | 'success' | 'error' | 'warning'

export interface ToastInput {
  type?: ToastType
  message: string
  title?: string
  duration?: number
}

export interface Toast extends Required<Omit<ToastInput, 'title'>> {
  id: number
  title: string | null
  createdAt: number
  paused: boolean
}

const DEFAULT_DURATION = 5000
const MAX_TOASTS = 6

interface ToastEntry {
  toast: Toast
  remainingMs: number
  expiresAt: number | null
  timerId: ReturnType<typeof setTimeout> | null
}

const ENTRIES = new Map<number, ToastEntry>()
let nextId = 1

export const useToastStore = () => {
  const toasts = useState<Toast[]>('toasts', () => [])

  function push(input: ToastInput): number {
    const id = nextId++
    const toast: Toast = {
      id,
      type: input.type ?? 'info',
      message: input.message,
      title: input.title ?? null,
      duration: input.duration ?? DEFAULT_DURATION,
      createdAt: Date.now(),
      paused: false
    }
    const evicted = toasts.value.slice(0, Math.max(0, toasts.value.length - MAX_TOASTS + 1))
    for (const stale of evicted) {
      const entry = ENTRIES.get(stale.id)
      if (entry?.timerId !== null && entry?.timerId !== undefined) clearTimeout(entry.timerId)
      ENTRIES.delete(stale.id)
    }
    toasts.value = [...toasts.value.slice(-MAX_TOASTS + 1), toast]

    if (import.meta.client && toast.duration > 0) {
      const entry: ToastEntry = {
        toast,
        remainingMs: toast.duration,
        expiresAt: Date.now() + toast.duration,
        timerId: null
      }
      ENTRIES.set(id, entry)
      scheduleDismiss(entry)
    }

    return id
  }

  function scheduleDismiss(entry: ToastEntry) {
    if (entry.timerId !== null) clearTimeout(entry.timerId)
    entry.timerId = setTimeout(() => {
      entry.timerId = null
      dismiss(entry.toast.id)
    }, entry.remainingMs)
  }

  function dismiss(id: number) {
    const entry = ENTRIES.get(id)
    if (entry?.timerId !== null && entry.timerId !== undefined) {
      clearTimeout(entry.timerId)
    }
    ENTRIES.delete(id)
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function pause(id: number) {
    const entry = ENTRIES.get(id)
    if (!entry || entry.toast.paused || entry.timerId === null) return
    clearTimeout(entry.timerId)
    entry.timerId = null
    const remaining = Math.max(0, (entry.expiresAt ?? Date.now()) - Date.now())
    entry.remainingMs = remaining
    entry.toast.paused = true
    sync()
  }

  function resume(id: number) {
    const entry = ENTRIES.get(id)
    if (!entry || !entry.toast.paused) return
    entry.toast.paused = false
    entry.expiresAt = Date.now() + entry.remainingMs
    sync()
    scheduleDismiss(entry)
  }

  function sync() {
    toasts.value = [...toasts.value]
  }

  function clear() {
    for (const entry of ENTRIES.values()) {
      if (entry.timerId !== null) clearTimeout(entry.timerId)
    }
    ENTRIES.clear()
    toasts.value = []
  }

  return { toasts, push, dismiss, pause, resume, clear }
}
