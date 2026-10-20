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

const toast = useToast()

const assigned = computed(() =>
  [...props.slot.assignments]
    .sort((a, b) => a.order - b.order)
    .map((a) => props.agents.find((x) => x.id === a.user_id))
    .filter((a): a is Agent => Boolean(a))
)

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
      :removable="removable !== false"
      @remove="unassign(a.id)"
    />
    <div v-if="!assigned.length" class="sp__empty">Vide</div>
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

.sp__empty {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  color: var(--dp-text-dim);
  font-size: 10px;
  font-style: italic;
}
</style>