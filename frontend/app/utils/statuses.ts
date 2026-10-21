export interface DispatchStatus {
  id: string
  label: string
  emoji: string
}

export const INTERVENTION_STATUSES: DispatchStatus[] = [
  { id: 'inter_ambulance', label: 'Inter', emoji: '🚑' },
  { id: 'inter_helico', label: 'Inter', emoji: '🚁' },
  { id: 'inter_bateau', label: 'Inter', emoji: '⛵' },
  { id: 'pat', label: 'Pat', emoji: '👣' },
  { id: 'pat_avp', label: 'Pat AVP', emoji: '🤕' },
  { id: 'pat_airbag', label: 'Pat Airbag', emoji: '🎈' },
  { id: 'retour_0', label: 'Retour 0', emoji: '0️⃣' },
  { id: 'retour_1', label: 'Retour 1', emoji: '1️⃣' },
  { id: 'retour_2', label: 'Retour 2', emoji: '2️⃣' },
  { id: 'primo', label: 'Primo', emoji: '🚨' },
  { id: 'navette', label: 'Navette', emoji: '🚑' },
  { id: 'ope_crise', label: 'Opé crise', emoji: '🧑‍⚕️' },
  { id: 'bces', label: 'BCES', emoji: '🏥' },
  { id: 'lses', label: 'LSES', emoji: '🏥' },
  { id: 'hopital_central', label: 'Hopital Central', emoji: '🏥' },
  { id: 'patrouille', label: 'Patrouille', emoji: '🚑' },
  { id: 'patrouille_inter_service', label: 'Patrouille inter service', emoji: '🚑' },
  { id: 'patrouille_vm', label: 'Patrouille VM', emoji: '⭐' },
  { id: 'zombie', label: 'Zombie', emoji: '🔧' },
  { id: 'bennys', label: 'Bennys', emoji: '🔧' },
  { id: 'event', label: 'Event', emoji: '🎉' },
  { id: 'renfort_lses', label: 'Renfort LSES', emoji: '💪' },
  { id: 'enterrement', label: 'Enterrement', emoji: '🪦' },
  { id: 'tour_bces', label: 'Tour de BCES', emoji: '🏃🏻' },
  { id: 'au_coin', label: 'Au coin', emoji: '📐' },
  { id: 'prise_otage', label: "Prise d'otage", emoji: '🏦' },
  { id: 'envie_caner', label: 'Envie de caner', emoji: '☠️' }
]

export function findStatus(id: string | null | undefined): DispatchStatus | null {
  if (!id) return null
  return INTERVENTION_STATUSES.find((s) => s.id === id) ?? null
}