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
  employee_id: number
  order: number
  created_at: string
}

export interface DispatchRadio {
  id: number
  serial: string
  employee_id: number | null
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
  note: string
}

interface PendingEmployeeMove {
  slotId: number | null
  assignment: DispatchAssignment | null
  previousSlotId: number | null
  previousAssignment: DispatchAssignment | null
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
    state: emptyState(),
    note: ''
  }))
  const pendingMoves = useState<Record<string, PendingEmployeeMove>>(
    'dispatch-pending-moves',
    () => ({})
  )

  const connected = useState<boolean>('dispatch-connected', () => false)
  const snapshotRef: Ref<DispatchSnapshot | null> = snapshot

  function applyPendingMoves(data: DispatchSnapshot, acknowledge = true): DispatchSnapshot {
    const pending = { ...pendingMoves.value }
    if (acknowledge) {
      for (const [employeeId, move] of Object.entries(pending)) {
        const actualSlotId =
          data.slots.find((slot) =>
            slot.assignments.some((assignment) => assignment.employee_id === Number(employeeId))
          )?.id ?? null
        if (actualSlotId === move.slotId) delete pending[employeeId]
      }
      pendingMoves.value = pending
    }

    return {
      ...data,
      slots: data.slots.map((slot) => ({
        ...slot,
        assignments: slot.assignments.filter(
          (assignment) => !pending[assignment.employee_id]
        )
      })).map((slot) => {
        const additions = Object.entries(pending)
          .flatMap(([, move]) =>
            move.slotId === slot.id && move.assignment ? [move.assignment] : []
          )
        return additions.length
          ? { ...slot, assignments: [...slot.assignments, ...additions] }
          : slot
      })
    }
  }

  function applySnapshot(data: DispatchSnapshot) {
    snapshot.value = applyPendingMoves(data)
  }

  function applyResetSnapshot(data: DispatchSnapshot) {
    pendingMoves.value = {}
    snapshot.value = data
  }

  function beginEmployeeMove(employeeId: number, slotId: number | null) {
    const source = snapshot.value.slots.find((slot) =>
      slot.assignments.some((assignment) => assignment.employee_id === employeeId)
    )
    const existing = source?.assignments.find((assignment) => assignment.employee_id === employeeId)
    let assignment: DispatchAssignment | null = null
    if (slotId !== null) {
      const target = snapshot.value.slots.find((slot) => slot.id === slotId)
      if (!target) return
      assignment = {
        id: existing?.id ?? -employeeId,
        slot_id: slotId,
        employee_id: employeeId,
        order: target.assignments.filter((item) => item.employee_id !== employeeId).length,
        created_at: existing?.created_at ?? new Date().toISOString()
      }
    }
    pendingMoves.value = {
      ...pendingMoves.value,
      [employeeId]: {
        slotId,
        assignment,
        previousSlotId: source?.id ?? null,
        previousAssignment: existing ?? null
      }
    }
    snapshot.value = applyPendingMoves(snapshot.value)
  }

  function completeEmployeeMove(employeeId: number, slot: DispatchSlot) {
    const pending = { ...pendingMoves.value }
    const move = pending[employeeId]
    if (move?.slotId !== null && move?.slotId !== undefined) {
      const serverAssignment = slot.assignments.find(
        (assignment) => assignment.employee_id === employeeId
      )
      if (serverAssignment) pending[employeeId] = { ...move, assignment: serverAssignment }
    }
    pendingMoves.value = pending
    const slots = snapshot.value.slots.map((current) =>
      current.id === slot.id ? slot : current
    )
    snapshot.value = applyPendingMoves({ ...snapshot.value, slots }, false)
  }

  function cancelEmployeeMove(employeeId: number) {
    const pending = { ...pendingMoves.value }
    const move = pending[employeeId]
    delete pending[employeeId]
    pendingMoves.value = pending
    const previousSlotId = move?.previousSlotId
    const previousAssignment = move?.previousAssignment
    if (previousSlotId !== null && previousSlotId !== undefined && previousAssignment) {
      const slots = snapshot.value.slots.map((slot) =>
        slot.id === previousSlotId
          ? {
              ...slot,
              assignments: [
                ...slot.assignments.filter((assignment) => assignment.employee_id !== employeeId),
                previousAssignment
              ]
            }
          : {
              ...slot,
              assignments: slot.assignments.filter((assignment) => assignment.employee_id !== employeeId)
            }
      )
      snapshot.value = { ...snapshot.value, slots }
    } else {
      snapshot.value = {
        ...snapshot.value,
        slots: snapshot.value.slots.map((slot) => ({
          ...slot,
          assignments: slot.assignments.filter((assignment) => assignment.employee_id !== employeeId)
        }))
      }
    }
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
    applyResetSnapshot,
    beginEmployeeMove,
    completeEmployeeMove,
    cancelEmployeeMove,
    setConnected
  }
}