<script setup lang="ts">
const props = defineProps<{
  modelValue: string | null
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const draft = ref<string>(props.modelValue ?? '')

watch(
  () => props.modelValue,
  (v) => {
    draft.value = v ?? ''
  }
)

let commitTimer: ReturnType<typeof setTimeout> | null = null

function onInput() {
  if (commitTimer) clearTimeout(commitTimer)
  commitTimer = setTimeout(() => {
    const v = draft.value.trim()
    emit('update:modelValue', v === '' ? null : v)
  }, 400)
}

function onBlur() {
  if (commitTimer) clearTimeout(commitTimer)
  const v = draft.value.trim()
  emit('update:modelValue', v === '' ? null : v)
}
</script>

<template>
  <input
    v-model="draft"
    type="text"
    class="zp__input"
    :placeholder="placeholder ?? 'ZIP…'"
    maxlength="12"
    @input="onInput"
    @blur="onBlur"
  />
</template>

<style scoped>
.zp__input {
  background: rgba(0, 0, 0, 0.30);
  border: 1px solid var(--bces-border);
  color: var(--bces-text);
  font-size: 11px;
  font-weight: 600;
  font-family: ui-monospace, monospace;
  padding: 4px 8px;
  width: 80px;
  outline: none;
}

.zp__input:focus {
  border-color: var(--bces-accent);
}

.zp__input::placeholder {
  color: var(--bces-text-dim);
  font-weight: 500;
}
</style>