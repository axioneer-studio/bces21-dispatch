<script setup lang="ts">
import type { Agent } from '~/utils/agent'
import { agentCallsign, agentDisplayName } from '~/utils/agent'

const props = withDefaults(
  defineProps<{
    agent: Agent
    agents?: Agent[]
    draggable?: boolean
    removable?: boolean
    tone?: 'default' | 'assigned' | 'pool'
    compact?: boolean
  }>(),
  {
    agents: () => [],
    draggable: false,
    removable: false,
    tone: 'default',
    compact: false
  }
)

const emit = defineEmits<{
  dragstart: []
  remove: []
}>()

function onDragStart(e: DragEvent) {
  e.dataTransfer?.setData('application/json', JSON.stringify({ userId: props.agent.id }))
  emit('dragstart')
}

function onRemove(e: MouseEvent) {
  e.stopPropagation()
  emit('remove')
}
</script>

<template>
  <div
    class="at"
    :class="[`at--${tone}`, { 'at--compact': compact }]"
    :draggable="draggable"
    :title="`${agentDisplayName(agent, agents)} — ${agent.phone || 'sans numéro'}`"
    @dragstart="onDragStart"
  >
    <span class="at__name">{{ agentDisplayName(agent, agents) }}</span>
    <span class="at__skills">{{ agent.competencies.join(' ') || '·' }}</span>
    <span class="at__num">{{ agentCallsign(agent) }}</span>
    <button
      v-if="removable"
      type="button"
      class="at__x"
      aria-label="Retirer"
      @mousedown.stop
      @dragstart.stop.prevent
      @click="onRemove"
    >
      <Icon name="lucide:x" size="9" />
    </button>
  </div>
</template>

<style scoped>
.at {
  position: relative;
  display: grid;
  grid-template-rows: auto auto auto;
  align-content: center;
  justify-items: center;
  gap: 0;
  width: 96px;
  height: 58px;
  padding: 3px 4px;
  background: var(--dp-tile-bg);
  border: 1px solid var(--dp-tile-border);
  border-radius: 3px;
  font-variant-numeric: tabular-nums;
  user-select: none;
  overflow: hidden;
}

.at--compact {
  width: 84px;
  height: 48px;
}

.at--pool {
  cursor: grab;
}

.at--assigned {
  cursor: grab;
}

.at--pool:active,
.at--assigned:active {
  cursor: grabbing;
}

.at--assigned {
  background: var(--dp-tile-bg-active);
  border-color: var(--dp-tile-border-active);
}

.at__name {
  font-size: 10.5px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--dp-text);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.at__skills {
  font-size: 10px;
  line-height: 1.15;
  letter-spacing: -0.5px;
  min-height: 12px;
  filter: saturate(1.1);
}

.at__num {
  font-family: ui-monospace, 'SFMono-Regular', monospace;
  font-size: 9.5px;
  font-weight: 600;
  line-height: 1.15;
  color: var(--dp-text-dim);
}

.at__x {
  position: absolute;
  top: 1px;
  right: 1px;
  width: 13px;
  height: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--dp-tile-bg);
  border: none;
  border-radius: 2px;
  color: var(--dp-text-dim);
  opacity: 0;
  cursor: pointer;
  transition: opacity 0.12s ease, color 0.12s ease;
}

.at:hover .at__x {
  opacity: 1;
}

.at__x:hover {
  color: var(--dp-danger);
}
</style>