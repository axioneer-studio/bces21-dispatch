<script setup lang="ts">
type Agent = {
  id: number
  discord_id: string
  discord_username: string
  discord_avatar: string | null
  prenom_rp: string | null
  nom_rp: string | null
}

const props = defineProps<{
  agent: Agent
  displayName: string
  series: string
  avatarUrl: string | null
  fromSlotId: string | null
}>()

const emit = defineEmits<{
  dragStart: [event: DragEvent]
  unassign: []
}>()

function handleDragStart(event: DragEvent) {
  emit('dragStart', event)
}

function handleUnassign(event: MouseEvent) {
  event.preventDefault()
  event.stopPropagation()
  emit('unassign')
}
</script>

<template>
  <div
    class="agent-tile"
    draggable="true"
    @dragstart="handleDragStart"
  >
    <img
      v-if="avatarUrl"
      :src="avatarUrl"
      :alt="displayName"
      class="agent-tile__avatar"
      width="36"
      height="36"
      draggable="false"
    />
    <div v-else class="agent-tile__avatar agent-tile__avatar--placeholder" aria-hidden="true">
      {{ displayName.charAt(0).toUpperCase() }}
    </div>
    <div class="agent-tile__meta">
      <div class="agent-tile__name">{{ displayName }}</div>
      <div class="agent-tile__series">{{ series }}</div>
    </div>
    <button
      v-if="fromSlotId"
      type="button"
      class="agent-tile__unassign"
      aria-label="Retirer"
      @click="handleUnassign"
      @mousedown.stop
      @dragstart.stop.prevent
    >
      <Icon name="lucide:x" size="12" />
    </button>
  </div>
</template>

<style scoped>
.agent-tile {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 0;
  border: 1px dashed var(--bces-border-strong);
  background: var(--bces-accent-soft);
  cursor: grab;
  transition: transform 0.12s ease, box-shadow 0.12s ease, background 0.12s ease;
  position: relative;
  user-select: none;
}

.agent-tile:active {
  cursor: grabbing;
}

.agent-tile:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(70, 153, 109, 0.25);
  background: rgba(70, 153, 109, 0.20);
}

.agent-tile__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--bces-bg-elevated);
  border: 1px solid var(--bces-border);
}

.agent-tile__unassign,
.agent-tile__avatar {
  border-radius: 0;
}

.agent-tile__avatar--placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: var(--bces-accent);
  font-size: 12px;
}

.agent-tile__meta {
  flex: 1;
  min-width: 0;
}

.agent-tile__name {
  font-size: 11px;
  font-weight: 600;
  color: var(--bces-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}

.agent-tile__series {
  font-size: 9px;
  color: var(--bces-text-dim);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.agent-tile__unassign {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--bces-text-dim);
  background: rgba(0, 0, 0, 0.25);
  transition: color 0.15s ease, background 0.15s ease;
  flex-shrink: 0;
}

.agent-tile__unassign:hover {
  color: #ec8a86;
  background: rgba(210, 85, 79, 0.20);
}
</style>