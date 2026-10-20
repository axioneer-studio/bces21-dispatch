export interface DispatchLocation {
  id: string
  label: string
  emoji: string
}

export const INTERVENTION_LOCATIONS: DispatchLocation[] = [
  { id: 'hopital', label: 'HOPITAL', emoji: '🏥' },
  { id: 'galapagos', label: 'GALAPAGOS', emoji: '🌴' },
  { id: 'irm', label: 'IRM', emoji: '🎧' },
  { id: 'radio_room', label: 'Radio', emoji: '☢️' },
  { id: 'ope_1', label: 'Salle Opé 1', emoji: '🛏️' },
  { id: 'ope_2', label: 'Salle Opé 2', emoji: '🛏️' },
  { id: 'ope_3', label: 'Salle Opé 3', emoji: '🛏️' },
  { id: 'soin_intensif', label: 'Soin Intensif', emoji: '🛏️' },
  { id: 'gordo', label: 'Gordo', emoji: '🛏️' },
  { id: 'chianski', label: 'Chianski', emoji: '🛏️' },
  { id: 'chilliad', label: 'Chilliad', emoji: '🛏️' },
  { id: 'josiah', label: 'Josiah', emoji: '🛏️' }
]

export function findLocation(id: string | null | undefined): DispatchLocation | null {
  if (!id) return null
  return INTERVENTION_LOCATIONS.find((l) => l.id === id) ?? null
}