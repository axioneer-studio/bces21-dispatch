<script setup lang="ts">
import { findLocation, INTERVENTION_LOCATIONS } from '~/utils/locations'

const props = defineProps<{
  modelValue: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const open = ref<boolean>(false)

const current = computed(() => findLocation(props.modelValue))

function pick(id: string | null) {
  emit('update:modelValue', id)
  open.value = false
}
</script>

<template>
  <div class="lp" @click.stop>
    <button type="button" class="lp__btn" @click="open = !open">
      <span v-if="current" class="lp__emoji">{{ current.emoji }}</span>
      <Icon v-else name="lucide:map-pin" size="13" />
      <span class="lp__label">{{ current?.label ?? 'Lieu…' }}</span>
      <Icon name="lucide:chevron-down" size="12" />
    </button>
    <div v-if="open" class="lp__menu">
      <button type="button" class="lp__menu-item lp__menu-item--clear" @click="pick(null)">
        <Icon name="lucide:x" size="13" /> Aucun
      </button>
      <button
        v-for="l in INTERVENTION_LOCATIONS"
        :key="l.id"
        type="button"
        class="lp__menu-item"
        :class="{ 'lp__menu-item--active': l.id === modelValue }"
        @click="pick(l.id)"
      >
        <span class="lp__emoji">{{ l.emoji }}</span>
        <span class="lp__label">{{ l.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.lp {
  position: relative;
  display: inline-block;
}

.lp__btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.30);
  border: 1px solid var(--bces-border);
  color: var(--bces-text);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  max-width: 160px;
}

.lp__btn:hover {
  border-color: var(--bces-border-strong);
}

.lp__emoji {
  font-size: 13px;
}

.lp__label {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
}

.lp__menu {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 4px;
  background: var(--bces-bg-elevated);
  border: 1px solid var(--bces-border-strong);
  min-width: 180px;
  max-height: 320px;
  overflow-y: auto;
}

.lp__menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  background: transparent;
  color: var(--bces-text);
  font-size: 11px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.lp__menu-item:hover {
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
}

.lp__menu-item--active {
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
}

.lp__menu-item--clear {
  color: var(--bces-text-dim);
  border-bottom: 1px solid var(--bces-border);
  margin-bottom: 2px;
  padding-bottom: 6px;
}
</style>