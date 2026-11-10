import type { DispatchRadio } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'

export type RadioStatus = 'on' | 'standby' | 'off'

/** ON : disponible ; Indisponible (`standby`) : en service mais indisponible à la radio. */
export function radioStatus(radio: Pick<DispatchRadio, 'is_on' | 'is_loading'>): RadioStatus {
  if (radio.is_on) return 'on'
  if (radio.is_loading) return 'standby'
  return 'off'
}

/** Radio Direction : son porteur a un grade coché « Fait partie de la Direction ». */
export function isDirectionRadio(radio: DispatchRadio, agentsById: Map<number, Agent>): boolean {
  if (radio.employee_id === null) return false
  return Boolean(agentsById.get(radio.employee_id)?.grade_is_direction)
}

export interface RadioSections {
  /** Radios des membres de la Direction, dans l'ordre des grades de la RH puis par ancienneté. */
  direction: DispatchRadio[]
  /** Autres radios : affectées puis libres, chacune par numéro de série. */
  normal: DispatchRadio[]
}

/**
 * Le Dispatch ne reçoit que des numéros masqués : l'ordre par numéro de série
 * est celui du serveur, conservé ici comme dernier critère.
 */
export function splitRadios(radios: DispatchRadio[], agents: Agent[]): RadioSections {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  const serialRank = new Map(radios.map((radio, index) => [radio.id, index]))
  const bySerial = (a: DispatchRadio, b: DispatchRadio) =>
    (serialRank.get(a.id) ?? 0) - (serialRank.get(b.id) ?? 0)
  const holder = (radio: DispatchRadio) =>
    radio.employee_id === null ? null : agentsById.get(radio.employee_id) ?? null

  const direction = radios.filter((radio) => isDirectionRadio(radio, agentsById))
  const normal = radios.filter((radio) => !isDirectionRadio(radio, agentsById))

  direction.sort((a, b) => {
    const agentA = holder(a)
    const agentB = holder(b)
    // Grade le plus haut (niveau le plus petit) d'abord ; sans grade ni porteur en dernier.
    return (
      (agentA?.grade_level ?? Number.MAX_SAFE_INTEGER) - (agentB?.grade_level ?? Number.MAX_SAFE_INTEGER)
      || (agentA?.arrival_date ?? '9999-12-31').localeCompare(agentB?.arrival_date ?? '9999-12-31')
      || bySerial(a, b)
    )
  })

  // Une radio dont l'employé n'est plus dans la liste compte comme affectée :
  // l'affectation existe côté serveur.
  normal.sort((a, b) =>
    Number(a.employee_id === null) - Number(b.employee_id === null) || bySerial(a, b)
  )

  return { direction, normal }
}
