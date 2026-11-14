<script setup lang="ts">
import type { DispatchSlot } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'
import { sortAgentsByGradeAndArrival } from '~/utils/agent'

const props = defineProps<{
  slot?: DispatchSlot
  pool?: Agent[]
  agents: Agent[]
  accent?: string
}>()

const emit = defineEmits<{
  'employee-drop': [employeeId: number, slotId: number | null]
  'employee-remove': [employeeId: number, slotId: number]
}>()

const assigned = computed(() => {
  const byEmployee = new Map(
    (props.slot?.assignments ?? []).map((assignment) => [assignment.employee_id, assignment])
  )
  return sortAgentsByGradeAndArrival(
    (props.slot?.assignments ?? [])
      .map((assignment) => props.agents.find((agent) => agent.id === assignment.employee_id))
      .filter((agent): agent is Agent => Boolean(agent))
  ).sort((a, b) => {
    // La case centrale respecte l'ordre d'affectation (order), pas le tri par grade.
    if (props.slot?.kind === 'centrale') {
      const orderA = byEmployee.get(a.id)?.order ?? 0
      const orderB = byEmployee.get(b.id)?.order ?? 0
      return orderA - orderB
    }
    return 0
  })
})

const isPool = computed(() => props.pool !== undefined)
const displayedAgents = computed(() =>
  // La case centrale respecte l'ordre d'affectation (order) tel quel.
  props.pool !== undefined || props.slot?.kind !== 'centrale'
    ? sortAgentsByGradeAndArrival(props.pool ?? assigned.value)
    : assigned.value
)
const emptyMessage = computed(() => {
  const messages: Record<string, string> = {
    hopital: "Personne n'est à l’hôpital.",
    astreinte: "Personne n'est d’astreinte.",
    conges: "Personne n'est en congé.",
    ipt: "Personne n'est en IPT.",
    'astreinte-fin': "Personne n'est en astreinte de fin de service.",
    pause: "Personne n'est en pause."
  }

  return props.slot ? messages[props.slot.kind] ?? 'Aucun agent assigné.' : 'Aucun employé hors service.'
})

const dropOver = ref<boolean>(false)

function onDragOver(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  dropOver.value = true
}

function onDragLeave() {
  dropOver.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  dropOver.value = false
  const transfer = e.dataTransfer
  if (!transfer) return
  let employeeId: number | null = null
  try {
    const raw = transfer.getData('application/json')
    if (raw) {
      const payload = JSON.parse(raw) as { employeeId?: number }
      if (typeof payload.employeeId === 'number') employeeId = payload.employeeId
    }
  } catch {
    employeeId = null
  }
  if (employeeId === null) {
    const plainTextId = Number(transfer.getData('text/plain'))
    if (Number.isInteger(plainTextId) && plainTextId > 0) employeeId = plainTextId
  }
  if (employeeId === null) return
  emit('employee-drop', employeeId, props.slot?.id ?? null)
}

function unassign(agentId: number) {
  if (!props.slot) return
  emit('employee-remove', agentId, props.slot.id)
}
</script>

<template>
  <div
    class="sp"
    :class="{ 'sp--pool': isPool }"
    :style="{ '--sp-accent': accent ?? 'var(--dp-accent)' }"
    :data-drop-over="dropOver ? '1' : '0'"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <AgentTile
      v-for="a in displayedAgents"
      :key="a.id"
      :agent="a"
      :agents="agents"
      tone="assigned"
      draggable

    />
    <EmptySlotState
      v-if="!displayedAgents.length"
      :message="isPool ? 'Tout le monde est en service.' : emptyMessage"
    />
  </div>
</template>

<style scoped>
.sp {
  --sp-accent: var(--dp-accent);
  flex: 1;
  min-height: 0;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 4px;
  padding: 5px;
  background: var(--dp-panel-2);
  border: 1px solid var(--dp-line);
  transition: background 0.12s ease;
  overflow: auto;
}

.sp[data-drop-over='1'] {
  background: var(--dp-accent-soft);
  outline: 2px dashed var(--sp-accent);
  outline-offset: -4px;
}

.sp--pool[data-drop-over='1'] {
  background: var(--dp-warn-soft);
  outline-color: var(--dp-warn-line);
}

</style>
