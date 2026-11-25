/** Keep a tab selection in one URL-fragment segment so it can be shared and restored. */
export function useHashTab<T extends string>(
  values: readonly T[],
  fallback: T,
  segment = 0,
  legacyKey?: string
) {
  const route = useRoute()
  const router = useRouter()

  const readFromHash = (hash: string): T | null => {
    const fragment = hash.replace(/^#/, '')
    const value = fragment.split('/')[segment]
    const match = values.find((candidate) => candidate === value)
    if (match) return match

    // Accept links created by the previous query-style fragment format.
    const params = new URLSearchParams(fragment)
    const legacyValue = legacyKey ? params.get(legacyKey) : segment === 0 ? params.get('section') : null
    return values.find((candidate) => candidate === legacyValue) ?? null
  }

  const currentHash = () =>
    import.meta.client && window.location.hash ? window.location.hash : route.hash
  const activeFromHash = (hash: string) =>
    (import.meta.client ? readFromHash(window.location.hash) : null) ?? readFromHash(hash) ?? fallback
  // Keep the server and first client render identical; fragments are only
  // available in the browser, so apply them after hydration in onMounted.
  const active = ref<T>(fallback)

  watch(
    () => route.hash,
    (hash) => {
      active.value = activeFromHash(hash)
    }
  )

  onMounted(() => {
    active.value = activeFromHash(currentHash())
  })

  function select(value: T) {
    active.value = value
    if (!import.meta.client) return
    const segments = currentHash().replace(/^#/, '').split('/')
    while (segments.length <= segment) segments.push('')
    segments[segment] = value
    while (segments.length > 1 && !segments.at(-1)) segments.pop()
    const hash = `#${segments.join('/')}`
    if (currentHash() !== hash) void router.push({ hash })
  }

  return { active, select }
}
