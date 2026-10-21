<script setup lang="ts">
import type { DispatchSlot } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'
import { assignUser, deleteSlot, unassignUser, updateSlot } from '~/composables/useDispatchApi'

const props = defineProps<{
  slot: DispatchSlot
  agents: Agent[]
  hospitalSlotId?: number
  fixed?: boolean
  compact?: boolean
  label?: string
}>()

const emit = defineEmits<{
  removed: [slotId: number]
}>()

const toast = useAppToast()
const dropOver = ref<boolean>(false)
const removing = ref<boolean>(false)

function setStatus(statusId: string | null) {
  updateSlot(props.slot.id, { status: statusId, location: null }).catch(() => {
    toast.error('Mise à jour impossible.')
  })
}

function setZip(zip: string | null) {
  updateSlot(props.slot.id, { zip_code: zip }).catch(() => {
    toast.error('Mise à jour impossible.')
  })
}

async function remove() {
  if (props.fixed || removing.value) return

  const assignedUserIds = props.slot.assignments.map((assignment) => assignment.user_id)
  if (assignedUserIds.length && props.hospitalSlotId === undefined) {
    toast.error('Suppression impossible : l’hôpital est indisponible.')
    return
  }

  removing.value = true
  try {
    if (props.hospitalSlotId !== undefined) {
      for (const userId of assignedUserIds) {
        await assignUser(props.hospitalSlotId, userId)
      }
    }
    await deleteSlot(props.slot.id)
    emit('removed', props.slot.id)
  } catch {
    toast.error('Suppression impossible. Les agents restants sont toujours assignés.')
  } finally {
    removing.value = false
  }
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
    :class="{
      'iv--compact': compact || !fixed,
      'iv--unassigned': !fixed && !assigned.length && !dropOver
    }"
    :data-drop-over="dropOver ? '1' : '0'"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div class="iv__bar">
      <span class="iv__label">{{ label ?? slot.title ?? 'Intervention' }}</span>
      <ZipPicker
        :model-value="slot.zip_code"
        @update:model-value="setZip"
      />
      <StatusPicker
        :model-value="slot.status ?? slot.location"
        @update:model-value="setStatus"
      />
      <button
        v-if="!fixed"
        type="button"
        class="iv__x"
        :disabled="removing"
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
        draggable
        :removable="!fixed"
        @remove="unassign(a.id)"
      />
      <div v-if="!assigned.length && !fixed" class="iv__hint iv__hint--unassigned">
        À PRENDRE
      </div>
      <div v-else-if="!assigned.length" class="iv__hint">
        <Icon name="lucide:mouse-pointer-click" size="11" />
        Glissez votre tuile ici
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

.iv--unassigned {
  border-color: var(--dp-danger-line);
  border-left-color: var(--dp-danger);
}

.iv--unassigned .iv__label {
  color: var(--dp-danger);
}

.iv__bar {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  padding: 3px;
  border-bottom: 1px solid var(--dp-line);
  flex-shrink: 0;
}

.iv__label {
  min-height: 14px;
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
  box-sizing: border-box;
  width: 100%;
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

.iv--compact {
  flex-direction: column;
  min-height: 126px;
  height: auto;
}

.iv--compact .iv__bar {
  flex: 0 0 auto;
  gap: 2px;
  border-right: 0;
  border-bottom: 1px solid var(--dp-line);
}

.iv--compact .iv__label {
  min-height: 12px;
  padding-right: 14px;
}

.iv--compact .iv__bar :deep(.zp__input),
.iv--compact .iv__bar :deep(.sp__select) {
  height: 18px;
  padding: 1px 3px;
  font-size: 9px;
}

.iv__x:hover {
  background: var(--dp-danger-soft);
  border-color: var(--dp-danger-line);
  color: var(--dp-danger);
}

.iv__drop {
  flex: 0 0 64px;
  height: 64px;
  min-height: 0;
  min-width: 0;
  overflow: auto;
  padding: 3px;
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-content: flex-start;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 3px;
}

.iv--compact .iv__drop {
  flex: 0 0 64px;
  align-content: flex-start;
}

.iv__hint {
  flex: 1;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
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

.iv__hint--unassigned {
  flex: 1;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  background: var(--dp-danger-soft);
  border: 1px dashed var(--dp-danger-line);
  color: var(--dp-danger);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

</style>
