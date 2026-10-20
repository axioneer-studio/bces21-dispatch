import type { Ref } from 'vue'

export type DispatchKind = 'centrale' | 'hopital' | 'intervention' | 'consultation'

export interface DispatchSlot {
  id: number
  kind: DispatchKind
  title: string | null
  status: string | null
  zip_code: string | null
  location: string | null
  type_label: string | null
  order: number
  assignments: DispatchAssignment[]
  created_at: string
  updated_at: string
}

export interface DispatchAssignment {
  id: number
  slot_id: number
  user_id: number
  order: number
  created_at: string
}

export interface DispatchRadio {
  id: number
  serial: string
  doctor_id: number | null
  is_on: boolean
  is_loading: boolean
  frequency: string
  common_frequency: string
  is_direction: boolean
  order: number
  updated_at: string
}

export interface DispatchState {
  hospital_status: 'ouvert' | 'ferme' | 'nuit'
  lses_status: string
  safd_status: string
  freq_147: string
  freq_570: string
  radio_codes: string
  updated_at: string
}

export interface DispatchSnapshot {
  slots: DispatchSlot[]
  radios: DispatchRadio[]
  state: DispatchState
}

const emptyState = (): DispatchState => ({
  hospital_status: 'ouvert',
  lses_status: 'ferme',
  safd_status: 'disponible',
  freq_147: '147',
  freq_570: '570',
  radio_codes: '',
  updated_at: new Date().toISOString()
})

export const useDispatchStore = () => {
  const snapshot = useState<DispatchSnapshot>('dispatch-snapshot', () => ({
    slots: [],
    radios: [],
    state: emptyState()
  }))

  const connected = useState<boolean>('dispatch-connected', () => false)
  const snapshotRef: Ref<DispatchSnapshot | null> = snapshot

  function applySnapshot(data: DispatchSnapshot) {
    snapshot.value = data
  }

  function setConnected(v: boolean) {
    connected.value = v
  }

  const slots = computed(() => snapshot.value.slots)
  const radios = computed(() => snapshot.value.radios)
  const state = computed(() => snapshot.value.state)
  const centrale = computed(() => slots.value.find((s) => s.kind === 'centrale') ?? null)
  const hopital = computed(() => slots.value.find((s) => s.kind === 'hopital') ?? null)
  const interventions = computed(() =>
    slots.value
      .filter((s) => s.kind === 'intervention' || s.kind === 'consultation')
      .sort((a, b) => a.order - b.order)
  )

  return {
    snapshot,
    snapshotRef,
    slots,
    radios,
    state,
    centrale,
    hopital,
    interventions,
    connected,
    applySnapshot,
    setConnected
  }
}