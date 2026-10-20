export interface Agent {
  id: number
  discord_id: string
  discord_username: string
  discord_avatar: string | null
  prenom_rp: string | null
  nom_rp: string | null
  phone: string | null
  status: string
  competencies: string[]
}

export function agentFirstName(a: Agent): string {
  return a.prenom_rp || a.discord_username
}

/** Prénom + initiale du nom uniquement s'il y a un homonyme. */
export function agentDisplayName(a: Agent, allAgents?: Agent[]): string {
  const first = agentFirstName(a)
  const last = a.nom_rp || ''
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
  if (!a.discord_avatar) return null
  return `https://cdn.discordapp.com/avatars/${a.discord_id}/${a.discord_avatar}.png?size=80`
}