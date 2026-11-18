<script setup lang="ts">
import { findStatus, STATUS_KINDS } from '~/utils/statuses'

const props = defineProps<{
  modelValue: string | null
}>()

/** Statuts gérés dans Administration, reçus avec le snapshot du Dispatch. */
const { snapshot } = useDispatchStore()
const statuses = computed(() => snapshot.value.statuses)
const color = computed(() => findStatus(statuses.value, props.modelValue)?.color ?? null)
/** Statuts puis lieux, chacun dans son groupe du menu. */
const groups = computed(() =>
  STATUS_KINDS.map((kind) => ({ ...kind, items: statuses.value.filter((status) => status.kind === kind.value) }))
    .filter((group) => group.items.length)
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

function onChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  emit('update:modelValue', value || null)
}
</script>

<template>
  <label class="sp">
    <span class="sp__label">Statut</span>
    <span class="sp__separator" aria-hidden="true">|</span>
    <select
      class="sp__select"
      :class="{ 'sp__select--colored': color }"
      :style="color ? { '--status-color': color } : undefined"
      :value="modelValue ?? ''"
      @change="onChange"
    >
      <option value=""></option>
      <optgroup v-for="group in groups" :key="group.value" :label="group.label">
        <option v-for="status in group.items" :key="status.id" :value="status.key">
          {{ status.emoji }} {{ status.label }}
        </option>
      </optgroup>
    </select>
  </label>
</template>

<style scoped>
.sp {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sp__label {
  flex: 0 0 33px;
  color: var(--dp-text-2);
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sp__separator {
  color: var(--dp-line-strong);
  font-size: 10px;
}

.sp__select {
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
  width: 100%;
  height: 26px;
  padding: 3px 6px;
  background: var(--dp-panel-2);
  border: 1px solid var(--dp-line-strong);
  border-radius: 2px;
  color: var(--dp-text);
  font-size: 10px;
  font-weight: 600;
}

/* Statut coloré dans Administration. */
.sp__select--colored {
  border-color: var(--status-color);
  background: color-mix(in srgb, var(--status-color) 22%, var(--dp-panel-2));
}
</style>