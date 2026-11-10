import type { DispatchRadio } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'

/**
 * Rang dans la Direction d'après le nom du grade, ou `null` hors Direction.
 * 0 = Directeur, 1 = Directeur Adjoint. Insensible à la casse, aux accents
 * et aux tirets (« Directeur-adjoint », « directrice adjointe »…).
 */
export function directionRank(gradeName: string | null | undefined): number | null {
  if (!gradeName) return null
  const name = gradeName
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[-_]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (name === 'directeur' || name === 'directrice') return 0
  if (name === 'directeur adjoint' || name === 'directrice adjointe') return 1
  return null
}

/** Ordre des numéros de série : chiffres puis lettres, sans tenir compte de la casse. */
export function compareSerials(a: string, b: string): number {
  return (
    a.localeCompare(b, 'fr', { sensitivity: 'base' })
    || (a < b ? -1 : a > b ? 1 : 0)
  )
}

export interface RadioSections {
  /** Radios des Directeurs puis des Directeurs Adjoints (par ancienneté). */
  direction: DispatchRadio[]
  /** Radios affectées puis libres, chacune triée par numéro de série. */
  normal: DispatchRadio[]
}

export function splitRadios(radios: DispatchRadio[], agents: Agent[]): RadioSections {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  const holder = (radio: DispatchRadio) =>
    radio.employee_id === null ? null : agentsById.get(radio.employee_id) ?? null

  const direction: { radio: DispatchRadio; agent: Agent; rank: number }[] = []
  const normal: DispatchRadio[] = []
  for (const radio of radios) {
    const agent = holder(radio)
    const rank = directionRank(agent?.grade_name)
    if (agent && rank !== null) direction.push({ radio, agent, rank })
    else normal.push(radio)
  }

  direction.sort((a, b) =>
    a.rank - b.rank
    // Ancienneté : arrivée la plus ancienne d'abord, date inconnue en dernier.
    || (a.agent.arrival_date ?? '9999-12-31').localeCompare(b.agent.arrival_date ?? '9999-12-31')
    || a.agent.first_name.localeCompare(b.agent.first_name, 'fr')
    || compareSerials(a.radio.serial, b.radio.serial)
    || a.radio.id - b.radio.id
  )

  // Une radio dont l'employé n'est plus dans la liste compte comme affectée :
  // l'affectation existe côté serveur.
  normal.sort((a, b) =>
    Number(a.employee_id === null) - Number(b.employee_id === null)
    || compareSerials(a.serial, b.serial)
    || a.id - b.id
  )

  return { direction: direction.map((item) => item.radio), normal }
}
