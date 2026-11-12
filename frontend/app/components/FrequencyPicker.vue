<script setup lang="ts">
import { randomizeFrequency } from '~/composables/useDispatchApi'
import type { FrequencyKind } from '~/composables/useDispatchStore'

const props = defineProps<{
  kind: FrequencyKind
  label: string
  current: string | null
  min: number | null
  max: number | null
}>()

const emit = defineEmits<{
  (e: 'update:current', value: string | null): void
  (e: 'close'): void
}>()

const toast = useAppToast()

const manualValue = ref('')
const randomizing = ref(false)
const error = ref('')

/** Fréquence formatée pour l'affichage. */
const formattedCurrent = computed(() => {
  const digits = props.current?.replace(/\s*MHz$/i, '').trim()
  return digits ? `${digits} MHz` : 'Aucune'
})

/** Valide la saisie manuelle : uniquement des chiffres, max 5. */
function onManualInput(event: Event) {
  const input = event.target as HTMLInputElement
  input.value = input.value.replace(/\D/g, '').slice(0, 5)
  manualValue.value = input.value
  error.value = ''
}

/** Applique la fréquence saisie manuellement. */
async function applyManual() {
  const digits = manualValue.value.trim()
  if (!digits) {
    error.value = 'Saisissez une fréquence.'
    return
  }
  const value = Number(digits)
  if (props.min !== null && props.max !== null && (value < props.min || value > props.max)) {
    error.value = `La fréquence doit être comprise entre ${props.min} et ${props.max} MHz.`
    return
  }
  try {
    const updated = await $fetch<{ kind: FrequencyKind; current: string | null; min: number | null; max: number | null }>(
      `/api/direction/frequencies/${props.kind}`,
      {
        method: 'PUT',
        body: { min: props.min, current: value, max: props.max },
        credentials: 'include'
      }
    )
    emit('update:current', updated.current)
    error.value = ''
  } catch (cause) {
    const detail = (cause as { data?: { detail?: unknown } } | null)?.data?.detail
    error.value = typeof detail === 'string' && detail ? detail : 'Fréquence impossible à enregistrer.'
  }
}

/** Génère une fréquence aléatoire entre les bornes. */
async function generateRandom() {
  if (randomizing.value) return
  if (props.min == null || props.max == null) {
    toast.warning(`Réglez d’abord les bornes de la fréquence « ${props.label} » dans Direction → Fréquences.`)
    return
  }
  randomizing.value = true
  error.value = ''
  try {
    const result = await randomizeFrequency(props.kind)
    emit('update:current', result.current)
  } catch (cause) {
    const detail = (cause as { data?: { detail?: unknown } } | null)?.data?.detail
    toast.error(typeof detail === 'string' && detail ? detail : 'Tirage aléatoire impossible.')
  } finally {
    randomizing.value = false
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div class="fp-overlay" @click.self="close" @keydown.esc="close">
      <section class="fp-panel" role="dialog" aria-modal="true" aria-labelledby="fp-title">
        <header class="fp-header">
          <div class="fp-header__icon">
            <Icon name="lucide:radio" size="18" />
          </div>
          <div>
            <h2 id="fp-title">Fréquence « {{ label }} »</h2>
            <p class="fp-header__subtitle">Choisissez une fréquence manuellement ou générez-en une au hasard.</p>
          </div>
          <button type="button" class="fp-close" aria-label="Fermer" @click="close">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>

        <div class="fp-body">
          <div class="fp-current">
            <span class="fp-current__label">Fréquence actuelle</span>
            <strong class="fp-current__value">{{ formattedCurrent }}</strong>
          </div>

          <div v-if="error" class="fp-error" role="alert">
            <Icon name="lucide:circle-alert" size="14" /><span>{{ error }}</span>
          </div>

          <div class="fp-section">
            <div class="fp-section__header">
              <Icon name="lucide:pencil" size="14" />
              <span class="fp-section__title">Saisie manuelle</span>
            </div>
            <div class="fp-input-group">
              <input
                type="text"
                inputmode="numeric"
                pattern="[0-9]*"
                maxlength="5"
                autocomplete="off"
                v-model="manualValue"
                :placeholder="props.min != null && props.max != null ? `${props.min}–${props.max}` : '?'"
                @input="onManualInput"
                @keydown.enter.prevent="applyManual"
              />
              <span class="fp-unit">MHz</span>
              <button type="button" class="fp-button fp-button--apply" :disabled="!manualValue.trim()" @click="applyManual">
                Appliquer
              </button>
            </div>
          </div>

          <div class="fp-section">
            <div class="fp-section__header">
              <Icon name="lucide:shuffle" size="14" />
              <span class="fp-section__title">Génération aléatoire</span>
            </div>
            <button
              type="button"
              class="fp-button fp-button--random fp-button--full"
              :disabled="randomizing || props.min == null || props.max == null"
              @click="generateRandom"
            >
              <Icon
                :name="randomizing ? 'lucide:loader-circle' : 'lucide:zap'"
                size="14"
                :class="{ 'fp-spin': randomizing }"
              />
              {{ randomizing ? 'Tirage en cours…' : 'Générer une fréquence' }}
            </button>
            <p class="fp-bounds">
              <span v-if="props.min != null && props.max != null">Entre {{ props.min }} et {{ props.max }} MHz</span>
              <span v-else class="fp-bounds--missing">Bornes non définies dans Direction → Fréquences</span>
            </p>
          </div>
        </div>

        <footer class="fp-footer">
          <button type="button" class="fp-button fp-button--cancel" @click="close">Annuler</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.fp-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(5, 8, 11, 0.72);
  backdrop-filter: blur(8px);
  animation: fp-overlay-in 0.22s ease-out;
}

.fp-panel {
  width: min(520px, 94%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--dp-line-strong);
  background: var(--dp-panel);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
  border-radius: 16px;
  overflow: hidden;
  animation: fp-panel-in 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.fp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.fp-header__icon {
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

.fp-header__info {
  min-width: 0;
}

.fp-header h2 {
  margin: 0;
  color: var(--dp-text);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.fp-header__subtitle {
  margin: 3px 0 0;
  color: var(--dp-text-2);
  font-size: 12px;
  line-height: 1.4;
}

.fp-close {
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

.fp-close:hover {
  color: var(--dp-text);
  background: var(--dp-panel-3);
  border-color: var(--dp-line-strong);
}

.fp-body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
}

.fp-current {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--dp-line);
  border-radius: 10px;
  background: var(--dp-panel-2);
}

.fp-current__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--dp-text-2);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.fp-current__value {
  font-size: 18px;
  font-weight: 800;
  color: var(--dp-accent);
  font-variant-numeric: tabular-nums;
  margin-left: auto;
}

.fp-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid var(--dp-danger-line);
  border-radius: 10px;
  color: #f0a29d;
  background: var(--dp-danger-soft);
  font-size: 12px;
}

.fp-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fp-section__header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-section__header Icon {
  color: var(--dp-accent);
}

.fp-section__title {
  font-size: 13px;
  font-weight: 700;
  color: var(--dp-text);
  letter-spacing: -0.01em;
}

.fp-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-input-group input {
  flex: 1;
  min-height: 42px;
  border: 1px solid var(--dp-line);
  border-radius: 10px;
  padding: 0 14px;
  color: var(--dp-text);
  background: var(--dp-bg);
  font: inherit;
  font-size: 14px;
  font-family: ui-monospace, 'SFMono-Regular', monospace;
}

.fp-input-group input:focus-visible {
  outline: 2px solid rgba(70, 153, 109, 0.24);
  outline-offset: 1px;
  border-color: var(--dp-accent-line);
}

.fp-unit {
  color: var(--dp-text-2);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.fp-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 16px;
  border: 1px solid var(--dp-line);
  border-radius: 10px;
  color: var(--dp-text-2);
  background: transparent;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.fp-button--full {
  width: 100%;
}

.fp-button:hover:not(:disabled) {
  border-color: var(--dp-line-strong);
  color: var(--dp-text);
  background: var(--dp-panel-3);
}

.fp-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.fp-button--apply {
  border-color: var(--dp-accent);
  color: #0c1710;
  background: var(--dp-accent);
  min-width: 90px;
}

.fp-button--apply:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.fp-button--random {
  border-color: var(--dp-info-line);
  color: var(--dp-info);
  background: var(--dp-info-soft);
}

.fp-button--random:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.fp-button--cancel {
  color: var(--dp-text-2);
  min-width: 90px;
}

.fp-button--cancel:hover:not(:disabled) {
  color: var(--dp-text);
  background: var(--dp-panel-3);
}

.fp-bounds {
  font-size: 11px;
  color: var(--dp-text-dim);
  margin: 0;
}

.fp-bounds--missing {
  color: var(--dp-warn);
}

.fp-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.fp-spin {
  animation: fp-spin 1s linear infinite;
}

@keyframes fp-spin {
  to { transform: rotate(360deg); }
}

@keyframes fp-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes fp-panel-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>