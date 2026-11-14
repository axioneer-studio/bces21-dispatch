<script setup lang="ts">
import { ref } from 'vue'

interface ConfirmDialogProps {
  visible?: boolean
  title?: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  checkboxLabel?: string
  checkboxChecked?: boolean
}

const props = withDefaults(defineProps<ConfirmDialogProps>(), {
  visible: false,
  title: 'Confirmation',
  message: '',
  confirmLabel: 'Confirmer',
  cancelLabel: 'Annuler',
  danger: false,
  checkboxLabel: '',
  checkboxChecked: false
})

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
  (e: 'update:visible', value: boolean): void
  (e: 'update:checkboxChecked', value: boolean): void
}>()

function onConfirm() {
  emit('update:visible', false)
  emit('confirm')
}

function onCancel() {
  emit('update:visible', false)
  emit('cancel')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.visible" class="confirm-overlay" @click.self="onCancel" @keydown.esc="onCancel">
      <section class="confirm-panel" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <header class="confirm-header">
          <div class="confirm-header__start">
            <div class="confirm-header__icon">
              <Icon name="lucide:alert-triangle" size="18" />
            </div>
            <div class="confirm-header__info">
              <h2 id="confirm-title">{{ props.title }}</h2>
              <p class="confirm-header__subtitle">{{ props.message }}</p>
            </div>
          </div>
          <button type="button" class="confirm-close" aria-label="Fermer" @click="onCancel">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>

        <div v-if="props.checkboxLabel" class="confirm-option">
          <label class="confirm-option__label">
            <input
              type="checkbox"
              :checked="props.checkboxChecked"
              @change="$event => emit('update:checkboxChecked', ($event.target as HTMLInputElement).checked)"
              class="confirm-option__input"
            >
            <span class="confirm-option__box">
              <span v-if="props.checkboxChecked" class="confirm-option__check">✓</span>
            </span>
            <span class="confirm-option__text">
              <strong>{{ props.checkboxLabel }}</strong>
            </span>
          </label>
        </div>

        <slot name="content" />

        <footer class="confirm-footer">
          <button type="button" class="confirm-button confirm-button--cancel" @click="onCancel">
            {{ props.cancelLabel }}
          </button>
          <button
            type="button"
            class="confirm-button confirm-button--confirm"
            :class="{ 'confirm-button--danger': props.danger }"
            @click="onConfirm"
          >
            {{ props.confirmLabel }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(5, 8, 11, 0.72);
  backdrop-filter: blur(8px);
  animation: confirm-overlay-in 0.22s ease-out;
}

.confirm-panel {
  width: min(520px, 94%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--dp-line-strong);
  background: var(--dp-panel);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
  border-radius: 16px;
  overflow: hidden;
  animation: confirm-panel-in 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.confirm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.confirm-header__start {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.confirm-header__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--dp-accent-line);
  border-radius: 10px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
  flex-shrink: 0;
}

.confirm-header__info {
  min-width: 0;
}

.confirm-header h2 {
  margin: 0;
  color: var(--dp-text);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-align: left;
}

.confirm-header__subtitle {
  margin: 3px 0 0;
  color: var(--dp-text-2);
  font-size: 12px;
  line-height: 1.4;
  text-align: left;
}

.confirm-close {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--dp-line);
  color: var(--dp-text-2);
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  flex-shrink: 0;
}

.confirm-close:hover {
  color: var(--dp-text);
  background: var(--dp-panel-3);
  border-color: var(--dp-line-strong);
}

.confirm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.confirm-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 18px;
  border: 1px solid var(--dp-line);
  border-radius: 10px;
  color: var(--dp-text-2);
  background: var(--dp-bg);
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  transition: all 0.16s ease;
}

.confirm-button:hover:not(:disabled) {
  border-color: var(--dp-line-strong);
  color: var(--dp-text);
  background: var(--dp-panel-3);
}

.confirm-button--cancel {
  color: var(--dp-text-2);
  background: transparent;
}

.confirm-button--confirm {
  border-color: transparent;
  color: #0c1710;
  background: var(--dp-accent);
}

.confirm-button--confirm:hover:not(:disabled) {
  filter: brightness(1.08);
  color: #0c1710;
  background: var(--dp-accent);
}

.confirm-button--danger {
  border-color: var(--dp-danger-line);
  color: var(--dp-danger);
  background: var(--dp-danger-soft);
}

.confirm-button--danger:hover:not(:disabled) {
  filter: brightness(1.08);
  color: var(--dp-danger);
  background: var(--dp-danger-soft);
}

.confirm-option {
  display: flex;
  justify-content: center;
  padding: 12px 24px;
  background: var(--dp-panel-2);
  border-top: 1px solid var(--dp-line);
}

.confirm-option__label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--dp-text-2);
  cursor: pointer;
}

.confirm-option__input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.confirm-option__box {
  width: 20px;
  height: 20px;
  border: 1.5px solid var(--dp-line);
  border-radius: 5px;
  background: var(--dp-bg);
  flex-shrink: 0;
  display: grid;
  place-items: center;
  transition: all 0.15s ease;
}

.confirm-option__input:checked + .confirm-option__box {
  border-color: var(--dp-danger);
  background: var(--dp-danger);
}

.confirm-option__input:focus-visible + .confirm-option__box {
  outline: none;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--dp-accent) 40%, transparent);
}

.confirm-option__input:hover + .confirm-option__box {
  border-color: var(--dp-line-strong);
}

.confirm-option__check {
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
}

.confirm-option__text strong {
  color: var(--dp-text);
  font-weight: 600;
}

.confirm-option__text small {
  color: var(--dp-text-dim);
  font-size: 10px;
  font-weight: 500;
  margin-top: 2px;
  display: block;
  line-height: 1.3;
}

.confirm-option__checkbox input:hover {
  border-color: var(--dp-line-strong);
  background: var(--dp-panel-3);
  transform: scale(1.08);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.22);
}

.confirm-option__checkbox input:focus-visible {
  outline: none;
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--dp-accent) 50%, transparent), 0 6px 16px rgba(0, 0, 0, 0.2);
}

.confirm-option__label strong {
  color: var(--dp-text);
  font-weight: 700;
  letter-spacing: -0.02em;
}

.confirm-option__label small {
  color: var(--dp-text-dim);
  font-size: 9.5px;
  font-weight: 500;
  margin-top: 4px;
  display: block;
  line-height: 1.3;
  letter-spacing: -0.01em;
}

@keyframes confirm-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes confirm-panel-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 640px) {
  .confirm-footer {
    flex-direction: column-reverse;
  }
  .confirm-footer > button {
    width: 100%;
  }
}
</style>
