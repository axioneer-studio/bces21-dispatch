export interface Agent {
  id: number
  first_name: string
  last_name: string
  phone: string | null
  email: string | null
  arrival_date: string | null
  competencies: string[]
  is_active: boolean
  account_user_id: number | null
  account_username: string | null
  grade_id: number | null
  grade_name: string | null
  grade_level: number | null
  grade_color: string | null
  grade_permissions: string[]
  discord_id?: string | null
  discord_avatar?: string | null
}

export function sortAgentsByGradeAndArrival(agents: Agent[]): Agent[] {
  return [...agents].sort((a, b) => {
    const gradeOrder =
      (a.grade_level ?? Number.MAX_SAFE_INTEGER) -
      (b.grade_level ?? Number.MAX_SAFE_INTEGER)
    if (gradeOrder !== 0) return gradeOrder

    const arrivalOrder =
      (a.arrival_date ?? '9999-12-31').localeCompare(b.arrival_date ?? '9999-12-31')
    if (arrivalOrder !== 0) return arrivalOrder

    return (
      a.first_name.localeCompare(b.first_name, 'fr') ||
      a.last_name.localeCompare(b.last_name, 'fr') ||
      a.id - b.id
    )
  })
}

export function agentFirstName(a: Agent): string {
  return a.first_name || a.account_username || 'Employé'
}

/** Prénom + initiale du nom uniquement s'il y a un homonyme. */
export function agentDisplayName(a: Agent, allAgents?: Agent[]): string {
  const first = agentFirstName(a)
  const last = a.last_name || ''
  if (!last || !allAgents) return first
  const sameFirst = allAgents.filter(
    (x) => agentFirstName(x).toLowerCase() === first.toLowerCase()
  )
  if (sameFirst.length <= 1) return first
  return `${first} ${last.charAt(0).toUpperCase()}.`
}

/**
 * Numéro d'appel : toujours au format `555-XXXX`.
 * - `5551234`, `555-1234`, `555 1234` → `555-1234`
 * - autres longueurs → last 4 masqués (`…1234`) pour rester compact
 */
export function agentCallsign(a: Agent): string {
  const raw = (a.phone || '').trim()
  if (!raw) return '—'
  const digits = raw.replace(/\D/g, '')
  if (digits.length < 4) return raw
  const last4 = digits.slice(-4)
  if (digits.length === 7) return `555-${last4}`
  return `…${last4}`
}

export function agentAvatarUrl(a: Agent): string | null {
  if (!a.discord_avatar || !a.discord_id) return null
  return `https://cdn.discordapp.com/avatars/${a.discord_id}/${a.discord_avatar}.png?size=80`
}