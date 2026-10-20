<script setup lang="ts">
import type { DispatchSlot } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'
import { assignUser, deleteSlot, unassignUser, updateSlot } from '~/composables/useDispatchApi'

const props = defineProps<{
  slot: DispatchSlot
  agents: Agent[]
  fixed?: boolean
  label?: string
}>()

const emit = defineEmits<{
  removed: [slotId: number]
}>()

const toast = useToast()
const dropOver = ref<boolean>(false)

function setStatus(statusId: string | null) {
  updateSlot(props.slot.id, { status: statusId ?? 'a_prendre' }).catch(() => {
    toast.error('Mise à jour impossible.')
  })
}

function setZip(zip: string | null) {
  updateSlot(props.slot.id, { zip_code: zip }).catch(() => {
    toast.error('Mise à jour impossible.')
  })
}

function remove() {
  if (props.fixed) return
  deleteSlot(props.slot.id)
    .then(() => emit('removed', props.slot.id))
    .catch(() => toast.error('Suppression impossible.'))
}

const assigned = computed(() =>
  [...props.slot.assignments]
    .sort((a, b) => a.order - b.order)
    .map((a) => props.agents.find((x) => x.id === a.user_id))
    .filter((a): a is Agent => Boolean(a))
)

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
      assignUser(props.slot.id, payload.userId).catch(() =>
        toast.error('Assignation impossible.')
      )
    }
  } catch {
    /* ignore */
  }
}

function unassign(agentId: number) {
  unassignUser(props.slot.id, agentId).catch(() =>
    toast.error('Désassignation impossible.')
  )
}
</script>

<template>
  <div
    class="iv"
    :data-drop-over="dropOver ? '1' : '0'"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div class="iv__bar">
      <span class="iv__label">{{ label ?? slot.title ?? 'Intervention' }}</span>
      <ZipPicker
        :model-value="slot.zip_code"
        placeholder="ZIP"
        @update:model-value="setZip"
      />
      <StatusPicker :model-value="slot.status" @update:model-value="setStatus" />
      <button
        v-if="!fixed"
        type="button"
        class="iv__x"
        aria-label="Supprimer"
        title="Supprimer"
        @click="remove"
      >
        <Icon name="lucide:x" size="12" />
      </button>
    </div>

    <div class="iv__drop">
      <AgentTile
        v-for="a in assigned"
        :key="a.id"
        :agent="a"
        :agents="agents"
        tone="assigned"
        :removable="!fixed"
        @remove="unassign(a.id)"
      />
      <div v-if="!assigned.length" class="iv__hint">
        <Icon name="lucide:mouse-pointer-click" size="11" />
        Glisse des agents ici
      </div>
    </div>
  </div>
</template>

<style scoped>
.iv {
  /* Largeur = 1 tuile (96px) + marges internes + bordure gauche.
     Les interventions défilent donc horizontalement, comme sur la Sheet. */
  width: 106px;
  min-width: 106px;
  flex: 0 0 106px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: var(--dp-panel);
  border: 1px solid var(--dp-line);
  border-left: 3px solid var(--dp-accent-line);
  transition: background 0.12s ease, border-color 0.12s ease;
}

.iv[data-drop-over='1'] {
  background: var(--dp-accent-soft);
  border-color: var(--dp-accent);
  border-left-color: var(--dp-accent);
}

.iv__bar {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 3px;
  padding: 3px;
  border-bottom: 1px solid var(--dp-line);
  flex-shrink: 0;
}

.iv__label {
  font-size: 9.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--dp-accent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.iv__bar > :deep(*) {
  max-width: 100%;
}

.iv__x {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--dp-panel-3);
  border: 1px solid var(--dp-line);
  border-radius: 2px;
  color: var(--dp-text-dim);
  cursor: pointer;
  flex-shrink: 0;
  z-index: 1;
}

.iv {
  position: relative;
}

.iv__x:hover {
  background: var(--dp-danger-soft);
  border-color: var(--dp-danger-line);
  color: var(--dp-danger);
}

.iv__drop {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 3px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.iv__hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 4px;
  color: var(--dp-text-dim);
  font-size: 9px;
  font-style: italic;
  text-align: center;
}
</style>