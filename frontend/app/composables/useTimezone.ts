const FORMATTER_CACHE = new Map<string, Intl.DateTimeFormat>()

const MINUS_SIGN = '\u2212'

function formatter(
  tz: string,
  options: Intl.DateTimeFormatOptions
): Intl.DateTimeFormat {
  const key = JSON.stringify({ tz, options })
  let f = FORMATTER_CACHE.get(key)
  if (!f) {
    f = new Intl.DateTimeFormat('fr-FR', { ...options, timeZone: tz })
    FORMATTER_CACHE.set(key, f)
  }
  return f
}

export function detectBrowserTimezone(): string | null {
  if (typeof Intl === 'undefined') return null
  try {
    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone
    return detected || null
  } catch {
    return null
  }
}

export function getOffsetHours(timezone: string, date: Date = new Date()): number {
  const utc = new Date(date.toLocaleString('en-US', { timeZone: 'UTC' }))
  const local = new Date(date.toLocaleString('en-US', { timeZone: timezone }))
  return Math.round((local.getTime() - utc.getTime()) / 3_600_000)
}

export function formatOffset(timezone: string, date: Date = new Date()): string {
  const hours = getOffsetHours(timezone, date)
  if (hours === 0) return 'UTC'
  const abs = Math.abs(hours)
  const sign = hours > 0 ? '+' : MINUS_SIGN
  if (Number.isInteger(hours)) return `UTC${sign}${abs}`
  const integerAbs = Math.floor(abs)
  const minutes = Math.round((abs - integerAbs) * 60)
  return `UTC${sign}${integerAbs}:${minutes.toString().padStart(2, '0')}`
}

export function formatTzLabel(timezone: string, date: Date = new Date()): string {
  return `${timezone} (${formatOffset(timezone, date)})`
}

export function useTimezone() {
  const config = useRuntimeConfig()
  const fallbackTz = String(config.public.timezone || 'Europe/Paris')

  const tz = ref<string>(fallbackTz)
  const isMounted = ref<boolean>(false)

  if (import.meta.client) {
    const detected = detectBrowserTimezone()
    if (detected) tz.value = detected
  }

  function formatDate(value: string | number | Date | null | undefined): string | null {
    if (value === null || value === undefined || value === '') return null
    const date = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(date.getTime())) return null
    return formatter(tz.value, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    }).format(date)
  }

  function formatTime(value: string | number | Date | null | undefined): string | null {
    if (value === null || value === undefined || value === '') return null
    const date = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(date.getTime())) return null
    return formatter(tz.value, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).format(date)
  }

  function formatDateTimeWithOffset(
    value: string | number | Date | null | undefined,
    reference: Date = new Date()
  ): { date: string; time: string; offset: string; label: string } | null {
    if (value === null || value === undefined || value === '') return null
    const date = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(date.getTime())) return null
    return {
      date: formatDate(date) as string,
      time: formatTime(date) as string,
      offset: formatOffset(tz.value, reference),
      label: formatTzLabel(tz.value, reference)
    }
  }

  onMounted(() => {
    isMounted.value = true
  })

  return {
    tz,
    isMounted,
    formatDate,
    formatTime,
    formatOffset: (date: Date = new Date()) => formatOffset(tz.value, date),
    formatTzLabel: (date: Date = new Date()) => formatTzLabel(tz.value, date),
    formatDateTimeWithOffset
  }
}