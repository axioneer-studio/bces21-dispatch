<script setup lang="ts">
const props = defineProps<{
  modelValue: string | null
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
  <label class="zp">
    <span class="zp__label">ZIP</span>
    <span class="zp__separator" aria-hidden="true">|</span>
    <input
      v-model="draft"
      type="text"
      class="zp__input"
      maxlength="12"
      @input="onInput"
      @blur="onBlur"
    />
  </label>
</template>

<style scoped>
.zp {
  display: flex;
  align-items: center;
  gap: 4px;
}

.zp__label {
  flex: 0 0 24px;
  color: var(--dp-text-2);
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.zp__separator {
  color: var(--dp-line-strong);
  font-size: 10px;
}

.zp__input {
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
  background: rgba(0, 0, 0, 0.30);
  border: 1px solid var(--bces-border);
  color: var(--bces-text);
  font-size: 11px;
  font-weight: 600;
  font-family: ui-monospace, monospace;
  padding: 3px 6px;
  width: 100%;
  height: 26px;
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