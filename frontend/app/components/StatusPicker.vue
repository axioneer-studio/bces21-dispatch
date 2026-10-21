<script setup lang="ts">
import { INTERVENTION_STATUSES } from '~/utils/statuses'
import { INTERVENTION_LOCATIONS } from '~/utils/locations'

const props = defineProps<{
  modelValue: string | null
}>()

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
    <select class="sp__select" :value="modelValue ?? ''" @change="onChange">
      <option value=""></option>
      <option v-for="status in INTERVENTION_STATUSES" :key="status.id" :value="status.id">
        {{ status.emoji }} {{ status.label }}
      </option>
      <option v-for="location in INTERVENTION_LOCATIONS" :key="location.id" :value="location.id">
        {{ location.emoji }} {{ location.label }}
      </option>
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
</style>