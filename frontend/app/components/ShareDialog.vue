<script setup lang="ts">
interface ShareDialogProps {
  visible?: boolean
  title?: string
  error?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}

const props = withDefaults(defineProps<ShareDialogProps>(), {
  visible: false,
  title: 'Partager',
  error: '',
  confirmLabel: 'Enregistrer',
  cancelLabel: 'Annuler',
  danger: false
})

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
  (e: 'update:visible', value: boolean): void
}>()

function onConfirm() {
  emit('confirm')
}

function onCancel() {
  emit('update:visible', false)
  emit('cancel')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.visible" class="share-overlay" @click.self="onCancel" @keydown.esc="onCancel">
      <section class="share-panel" role="dialog" aria-modal="true" aria-labelledby="share-title">
        <header class="share-header">
          <div class="share-header__start">
            <div class="share-header__icon">
              <Icon name="lucide:share-2" size="18" />
            </div>
            <div class="share-header__info">
              <h2 id="share-title">{{ props.title }}</h2>
            </div>
          </div>
          <button type="button" class="share-close" aria-label="Fermer" @click="onCancel">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>

        <div class="share-content">
          <slot name="content" />
        </div>

        <footer class="share-footer">
          <div class="share-footer__row">
            <div v-if="props.error" class="share-footer__error" role="alert">
              <Icon name="lucide:circle-alert" size="15" />
              <span>{{ props.error }}</span>
            </div>
            <div class="share-footer__actions">
              <button type="button" class="share-button share-button--cancel" @click="onCancel">
                {{ props.cancelLabel }}
              </button>
              <button
                type="button"
                class="share-button share-button--confirm"
                :class="{ 'share-button--danger': props.danger }"
                @click="onConfirm"
              >
                {{ props.confirmLabel }}
              </button>
            </div>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.share-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(5, 8, 11, 0.72);
  backdrop-filter: blur(8px);
  animation: share-overlay-in 0.22s ease-out;
}

.share-panel {
  width: min(760px, 94%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--dp-line-strong);
  background: var(--dp-panel);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
  border-radius: 16px;
  overflow: hidden;
  animation: share-panel-in 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.share-content {
  display: grid;
  gap: 18px;
  padding: clamp(18px, 4vw, 28px);
  overflow-y: auto;
}

.share-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.share-header__start {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.share-header__icon {
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

.share-header__info {
  min-width: 0;
}

.share-header h2 {
  margin: 0;
  color: var(--dp-text);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-align: left;
}

.share-footer__error {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 10px;
  border: 1px solid var(--dp-danger-line);
  border-radius: 8px;
  color: #f0a29d;
  background: var(--dp-danger-soft);
  font-size: 11px;
  line-height: 1.4;
  flex-shrink: 0;
}

.share-footer__error Icon {
  flex-shrink: 0;
}

.share-close {
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

.share-close:hover {
  color: var(--dp-text);
  background: var(--dp-panel-3);
  border-color: var(--dp-line-strong);
}

.share-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.share-footer__row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.share-footer__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
  margin-left: auto;
}

.share-button {
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

.share-button:hover:not(:disabled) {
  border-color: var(--dp-line-strong);
  color: var(--dp-text);
  background: var(--dp-panel-3);
}

.share-button--cancel {
  color: var(--dp-text-2);
  background: transparent;
}

.share-button--confirm {
  border-color: transparent;
  color: #0c1710;
  background: var(--dp-accent);
}

.share-button--confirm:hover:not(:disabled) {
  filter: brightness(1.08);
  color: #0c1710;
  background: var(--dp-accent);
}

.share-button--danger {
  border-color: var(--dp-danger-line);
  color: var(--dp-danger);
  background: var(--dp-danger-soft);
}

.share-button--danger:hover:not(:disabled) {
  filter: brightness(1.08);
  color: var(--dp-danger);
  background: var(--dp-danger-soft);
}

@keyframes share-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes share-panel-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 640px) {
  .share-footer {
    flex-direction: column-reverse;
  }
  .share-footer > button {
    width: 100%;
  }
}
</style>