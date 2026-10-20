<script setup lang="ts">
import { DEFAULT_STATUS_ID, INTERVENTION_STATUSES } from '~/utils/statuses'

const props = defineProps<{
  modelValue: string | null
  compact?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const open = ref<boolean>(false)

const current = computed(() => {
  if (!props.modelValue) {
    const def = INTERVENTION_STATUSES.find((s) => s.default)
    return def ?? null
  }
  return INTERVENTION_STATUSES.find((s) => s.id === props.modelValue) ?? null
})

function pick(id: string) {
  emit('update:modelValue', id)
  open.value = false
}
</script>

<template>
  <div class="sp" @click.stop>
    <button
      type="button"
      class="sp__btn"
      :class="`sp__btn--${current?.id ?? 'a_prendre'}`"
      @click="open = !open"
    >
      <span class="sp__emoji">{{ current?.emoji ?? '⚠️' }}</span>
      <span class="sp__label">{{ current?.label ?? 'A PRENDRE' }}</span>
      <Icon name="lucide:chevron-down" size="12" />
    </button>
    <div v-if="open" class="sp__menu">
      <button
        v-for="s in INTERVENTION_STATUSES"
        :key="s.id"
        type="button"
        class="sp__menu-item"
        :class="{ 'sp__menu-item--active': s.id === (modelValue ?? DEFAULT_STATUS_ID) }"
        @click="pick(s.id)"
      >
        <span class="sp__emoji">{{ s.emoji }}</span>
        <span class="sp__label">{{ s.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.sp {
  position: relative;
  display: inline-block;
}

.sp__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(70, 153, 109, 0.10);
  border: 1px solid rgba(70, 153, 109, 0.40);
  color: var(--bces-text);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.sp__btn:hover {
  background: rgba(70, 153, 109, 0.18);
}

.sp__emoji {
  font-size: 13px;
}

.sp__label {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sp__menu {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  z-index: 30;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  padding: 4px;
  background: var(--bces-bg-elevated);
  border: 1px solid var(--bces-border-strong);
  min-width: 360px;
  max-width: 480px;
  max-height: 320px;
  overflow-y: auto;
}

.sp__menu-item {
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

.sp__menu-item:hover {
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
}

.sp__menu-item--active {
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
}
</style>