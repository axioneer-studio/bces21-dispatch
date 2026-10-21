<script setup lang="ts">
import type { DispatchSlot } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'
import { assignUser, unassignUser } from '~/composables/useDispatchApi'

const props = defineProps<{
  slot: DispatchSlot
  agents: Agent[]
  accent?: string
  removable?: boolean
}>()

const emit = defineEmits<{
  changed: []
}>()

const toast = useAppToast()

const assigned = computed(() =>
  [...props.slot.assignments]
    .sort((a, b) => a.order - b.order)
    .map((a) => props.agents.find((x) => x.id === a.user_id))
    .filter((a): a is Agent => Boolean(a))
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

  return messages[props.slot.kind] ?? 'Aucun agent assigné.'
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
  dropOver.value = false
  try {
    const raw = e.dataTransfer?.getData('application/json')
    if (!raw) return
    const payload = JSON.parse(raw) as { userId?: number }
    if (typeof payload.userId === 'number') {
      assignUser(props.slot.id, payload.userId)
        .then(() => emit('changed'))
        .catch(() => toast.error('Assignation impossible.'))
    }
  } catch {
    /* ignore */
  }
}

function unassign(agentId: number) {
  unassignUser(props.slot.id, agentId)
    .then(() => emit('changed'))
    .catch(() => toast.error('Désassignation impossible.'))
}
</script>

<template>
  <div
    class="sp"
    :style="{ '--sp-accent': accent ?? 'var(--dp-accent)' }"
    :data-drop-over="dropOver ? '1' : '0'"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <AgentTile
      v-for="a in assigned"
      :key="a.id"
      :agent="a"
      :agents="agents"
      tone="assigned"
      draggable
      :removable="removable !== false"
      @remove="unassign(a.id)"
    />
    <EmptySlotState v-if="!assigned.length" :message="emptyMessage" />
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
}

.sp[data-drop-over='1'] {
  background: var(--dp-accent-soft);
  outline: 2px dashed var(--sp-accent);
  outline-offset: -4px;
}

</style>
