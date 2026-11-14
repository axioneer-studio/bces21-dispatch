<script setup lang="ts">
import type { Agent } from '~/utils/agent'
import { agentDisplayName } from '~/utils/agent'

const props = withDefaults(
  defineProps<{
    agent: Agent
    agents?: Agent[]
    draggable?: boolean
    tone?: 'default' | 'assigned' | 'pool'
    compact?: boolean
  }>(),
  {
    agents: () => [],
    draggable: false,
    tone: 'default',
    compact: false
  }
)

const emit = defineEmits<{
  dragstart: []
}>()

const gradeTextColor = computed(() => {
  const hex = props.agent.grade_color
  if (!hex || !/^#[0-9a-f]{6}$/i.test(hex)) return '#ffffff'

  const linearize = (index: number) => {
    const channel = parseInt(hex.slice(index, index + 2), 16) / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  }
  const luminance =
    linearize(1) * 0.2126 + linearize(3) * 0.7152 + linearize(5) * 0.0722

  return luminance > 0.179 ? '#111111' : '#ffffff'
})

const competencyRows = computed(() => {
  const rows: string[][] = []
  for (let index = 0; index < props.agent.competencies.length; index += 6) {
    rows.push(props.agent.competencies.slice(index, index + 6))
  }
  return rows
})

function onDragStart(e: DragEvent) {
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('application/json', JSON.stringify({ employeeId: props.agent.id }))
    e.dataTransfer.setData('text/plain', String(props.agent.id))
  }
  emit('dragstart')
}


</script>

<template>
  <div
    class="at"
    :class="[`at--${tone}`, {
      'at--compact': compact,
      'at--graded': agent.grade_color
    }]"
    :style="agent.grade_color
      ? { '--at-grade-color': agent.grade_color, '--at-grade-text': gradeTextColor }
      : undefined"
    :draggable="draggable"
    :title="`${agentDisplayName(agent, agents)} — ${agent.phone || 'sans numéro'}`"
    @dragstart="onDragStart"
  >
    <span class="at__name">{{ agentDisplayName(agent, agents) }}</span>
    <span class="at__skills">
      <span v-if="!competencyRows.length" class="at__skills-empty">·</span>
      <span v-for="(row, rowIndex) in competencyRows" :key="rowIndex" class="at__skills-row">
        <span
          v-for="(competency, index) in row"
          :key="`${competency}-${index}`"
          class="at__skill"
        >{{ competency }}</span>
      </span>
    </span>
    <span class="at__num">{{ agent.phone || '—' }}</span>
  </div>
</template>

<style scoped>
.at {
  position: relative;
  display: grid;
  grid-template-rows: repeat(3, auto);
  align-content: center;
  align-items: center;
  justify-items: center;
  gap: 0;
  width: 96px;
  min-height: 58px;
  flex: 0 0 96px;
  padding: 3px 4px;
  background: var(--dp-tile-bg);
  border: 1px solid var(--dp-tile-border);
  border-radius: 3px;
  font-variant-numeric: tabular-nums;
  user-select: none;
}

.at--compact {
  width: 84px;
  min-height: 48px;
  flex-basis: 84px;
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

.at--graded {
  background: color-mix(in srgb, var(--at-grade-color) 20%, var(--dp-tile-bg));
  border-color: color-mix(in srgb, var(--at-grade-color) 45%, var(--dp-tile-border));
}

.at__name {
  font-size: 10.5px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--dp-text);
  width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: center;
}

.at__skills {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 10px;
  line-height: 1.15;
  min-height: 12px;
  width: 100%;
  min-width: 0;
  color: inherit;
  text-align: center;
  filter: saturate(1.1);
}

.at__skill,
.at__skills-empty {
  flex: 0 0 calc(100% / 6);
  overflow-wrap: anywhere;
  text-align: center;
}

.at__skills-row {
  display: flex;
  justify-content: center;
  width: 100%;
}

.at__skills-empty {
  flex: none;
}

.at__num {
  font-family: ui-monospace, 'SFMono-Regular', monospace;
  font-size: 9.5px;
  font-weight: 600;
  line-height: 1.15;
  color: #fff;
  text-align: center;
  width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
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