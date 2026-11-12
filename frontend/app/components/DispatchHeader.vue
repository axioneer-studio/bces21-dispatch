<script setup lang="ts">
import { resetAssignments, updateState } from '~/composables/useDispatchApi'
import type { FrequencyKind } from '~/composables/useDispatchStore'
import FrequencyPicker from '~/components/FrequencyPicker.vue'

const props = defineProps<{
  canResetAssignments: boolean
  canDeleteInterventions: boolean
}>()

const { state, snapshot, applyResetSnapshot } = useDispatchStore()
const toast = useAppToast()

const hospitalOpen = ref<boolean>(true)
const hospitalMenu = ref<boolean>(false)
const resettingAssignments = ref(false)
const resetDialogOpen = ref(false)
const deleteInterventions = ref(false)
const dynamicInterventions = computed(() =>
  snapshot.value.slots.filter(
    (slot) => slot.kind === 'intervention' || slot.kind === 'consultation'
  )
)
const hasAssignments = computed(() => snapshot.value.slots.some((slot) => slot.assignments.length > 0))
const canResetDispatch = computed(() =>
  hasAssignments.value ||
  state.value.hospital_status !== 'ferme' ||
  (props.canDeleteInterventions && dynamicInterventions.value.length > 0)
)

// --- Fréquences : double-clic pour ouvrir le popup de saisie / tirage aléatoire ---

/** « 147 MHz », ou « Aucune » tant que la fréquence n'est pas enregistrée en base. */
const frequencyText = (value: string | null) => {
  const digits = value?.replace(/\s*MHz$/i, '').trim()
  return digits ? `${digits} MHz` : 'Aucune'
}

const frequencies = computed(() => [
  { kind: 'radio' as const, label: 'Radio', value: frequencyText(state.value.freq_bces) },
  { kind: 'shared' as const, label: 'Radio commune', value: frequencyText(state.value.freq_shared) }
])

/** Popup de fréquence : quel type est en cours d'édition. */
const editingFrequencyKind = ref<FrequencyKind | null>(null)

/** Bornes pour le type de fréquence en cours d'édition. */
const editingBounds = computed(() => {
  if (!editingFrequencyKind.value) return { min: null, max: null }
  return snapshot.value.frequency_bounds[editingFrequencyKind.value] ?? { min: null, max: null }
})

/** Fréquence actuelle pour le type en cours d'édition. */
const editingCurrent = computed(() => {
  if (!editingFrequencyKind.value) return null
  return editingFrequencyKind.value === 'radio' ? state.value.freq_bces : state.value.freq_shared
})

function openFrequencyPicker(kind: FrequencyKind) {
  editingFrequencyKind.value = kind
}

function closeFrequencyPicker() {
  editingFrequencyKind.value = null
}

async function onFrequencyUpdated(kind: FrequencyKind, value: string | null) {
  // La mise à jour est gérée par le composant FrequencyPicker via l'API Direction.
  // On recharge le snapshot via le WebSocket (broadcast) ou on attend la prochaine réception.
  closeFrequencyPicker()
}

watch(
  () => state.value.hospital_status,
  (v) => {
    hospitalOpen.value = v !== 'ferme'
  },
  { immediate: true }
)

async function setHospital(s: 'ouvert' | 'ferme' | 'nuit') {
  try {
    await updateState({ hospital_status: s })
    hospitalMenu.value = false
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

async function resetDispatchAssignments() {
  if (resettingAssignments.value || !canResetDispatch.value) return

  resettingAssignments.value = true
  try {
    const updatedSnapshot = await resetAssignments(deleteInterventions.value)
    applyResetSnapshot(updatedSnapshot)
    toast.success(
      deleteInterventions.value
        ? 'Dispatch réinitialisé : hôpital fermé, affectations retirées, radios éteintes et interventions supprimées.'
        : 'Dispatch réinitialisé : hôpital fermé, radios éteintes et employés remis hors service BCES.'
    )
    resetDialogOpen.value = false
    deleteInterventions.value = false
  } catch {
    toast.error('Réinitialisation du Dispatch impossible.')
  } finally {
    resettingAssignments.value = false
  }
}

// LSES / SAFD : statuts synchronisés depuis le Google Sheet (lecture seule)
const lsesLabel = computed(() => {
  switch (state.value.lses_status) {
    case 'ouvert':
      return 'Ouvert'
    case 'ferme':
      return 'Fermé'
    case 'nuit':
      return 'Nuit'
    default:
      return "C'est bugué"
  }
})

const lsesClass = computed(() => {
  switch (state.value.lses_status) {
    case 'ouvert':
      return 'dh__chip--on'
    case 'nuit':
      return 'dh__chip--nuit'
    case 'ferme':
      return 'dh__chip--off'
    default:
      return 'dh__chip--bug'
  }
})

const safdLabel = computed(() =>
  state.value.safd_status === 'disponible' ? 'Disponibles' : 'Indisponibles'
)

</script>

<template>
  <header class="dh">
    <div class="dh__brand">
      <span class="dh__title">Dispatch</span>
    </div>

    <div class="dh__group dh__freqs">
      <button
        v-for="frequency in frequencies"
        :key="frequency.kind"
        type="button"
        class="dh__chip dh__chip--freq"
        :disabled="editingFrequencyKind !== null"
        :aria-busy="editingFrequencyKind === frequency.kind"
        :title="`Double-cliquer pour choisir ou générer une nouvelle ${frequency.label.toLowerCase()}`"
        @dblclick="openFrequencyPicker(frequency.kind)"
      >
        <Icon
          :name="editingFrequencyKind === frequency.kind ? 'lucide:loader-circle' : 'lucide:radio'"
          size="14"
          :class="{ dh__spin: editingFrequencyKind === frequency.kind }"
        />
        {{ frequency.label }} : <strong>{{ frequency.value }}</strong>
      </button>
    </div>

    <div class="dh__group">
      <div class="dh__dropdown" @click.stop>
        <button
          type="button"
          class="dh__chip"
          :class="`dh__chip--${state.hospital_status}`"
          @click="hospitalMenu = !hospitalMenu"
        >
          <Icon name="lucide:heart-pulse" size="14" />
          Hôpital : <strong>{{ state.hospital_status === 'ouvert' ? 'Ouvert' : state.hospital_status === 'ferme' ? 'Fermé' : 'Nuit' }}</strong>
          <Icon name="lucide:chevron-down" size="12" />
        </button>
        <div v-if="hospitalMenu" class="dh__menu">
          <button type="button" class="dh__menu-item" @click="setHospital('ouvert')">
            <Icon name="lucide:check" size="14" /> Ouvert
          </button>
          <button type="button" class="dh__menu-item" @click="setHospital('ferme')">
            <Icon name="lucide:x" size="14" /> Fermé
          </button>
          <button type="button" class="dh__menu-item" @click="setHospital('nuit')">
            <Icon name="lucide:moon" size="14" /> Nuit
          </button>
        </div>
      </div>
    </div>

    <div class="dh__group">
      <span class="dh__chip dh__chip--readonly" :class="lsesClass">
        <Icon name="lucide:door-open" size="14" />
        LSES : <strong>{{ lsesLabel }}</strong>
      </span>
    </div>

    <div class="dh__group">
      <span
        class="dh__chip dh__chip--readonly"
        :class="state.safd_status === 'disponible' ? 'dh__chip--on' : 'dh__chip--off'"
      >
        <Icon name="lucide:truck" size="14" />
        SAFD : <strong>{{ safdLabel }}</strong>
      </span>
    </div>

    <div v-if="props.canResetAssignments" class="dh__group dh__reset">
      <button
        type="button"
        class="dh__reset-button"
        :disabled="resettingAssignments || !canResetDispatch"
        @click="resetDialogOpen = true"
      >
        <Icon :name="resettingAssignments ? 'lucide:loader-circle' : 'lucide:rotate-ccw'" size="14" :class="{ 'dh__spin': resettingAssignments }" />
        {{ resettingAssignments ? 'Réinitialisation…' : 'Tempête' }}
      </button>
    </div>

  </header>
  <Teleport to="body">
    <div
      v-if="resetDialogOpen"
      class="dh-modal"
      role="presentation"
      @click.self="resetDialogOpen = false"
      @keydown.esc="resetDialogOpen = false"
    >
      <section
        class="dh-modal__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dh-reset-title"
        aria-describedby="dh-reset-description"
      >
        <div class="dh-modal__header">
          <div class="dh-modal__icon">
            <Icon name="lucide:alert-triangle" size="18" />
          </div>
          <div>
            <h2 id="dh-reset-title">Réinitialiser le Dispatch ?</h2>
            <p id="dh-reset-description">
              Les employés affectés seront remis dans « Hors service BCES », les radios ON ou indisponibles passeront OFF et l’hôpital sera fermé.
            </p>
          </div>
          <button type="button" class="dh-modal__close" aria-label="Fermer" @click="resetDialogOpen = false">
            <Icon name="lucide:x" size="16" />
          </button>
        </div>
        <label v-if="props.canDeleteInterventions" class="dh-modal__option">
          <input v-model="deleteInterventions" type="checkbox">
          <span>
            <strong>Supprimer aussi toutes les interventions et consultations</strong>
            <small>{{ dynamicInterventions.length }} case{{ dynamicInterventions.length > 1 ? 's' : '' }} concernée{{ dynamicInterventions.length > 1 ? 's' : '' }}</small>
          </span>
        </label>
        <div class="dh-modal__actions">
          <button type="button" class="dh-modal__cancel" :disabled="resettingAssignments" @click="resetDialogOpen = false">
            Annuler
          </button>
          <button type="button" class="dh-modal__confirm" :disabled="resettingAssignments" @click="resetDispatchAssignments">
            <Icon :name="resettingAssignments ? 'lucide:loader-circle' : 'lucide:rotate-ccw'" size="14" :class="{ 'dh__spin': resettingAssignments }" />
            {{ resettingAssignments ? 'Réinitialisation…' : 'Confirmer' }}
          </button>
        </div>
      </section>
    </div>

    <FrequencyPicker
      v-if="editingFrequencyKind"
      :kind="editingFrequencyKind"
      :label="editingFrequencyKind === 'radio' ? 'Radio' : 'Radio commune'"
      :current="editingCurrent"
      :min="editingBounds.min"
      :max="editingBounds.max"
      @update:current="onFrequencyUpdated"
      @close="closeFrequencyPicker"
    />
  </Teleport>
</template>

<style scoped>
.dh {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #16191e;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-wrap: wrap;
  min-height: 52px;
}

.dh__brand {
  display: flex;
  align-items: center;
  padding-right: 8px;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.dh__title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--dp-accent);
}

.dh__group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dh__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 0;
  background: rgba(70, 153, 109, 0.10);
  border: 1px solid rgba(70, 153, 109, 0.40);
  color: var(--dp-text);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.dh__chip strong {
  color: var(--dp-accent);
  font-weight: 700;
}

.dh__chip--off {
  background: rgba(210, 85, 79, 0.12);
  border-color: rgba(210, 85, 79, 0.45);
  color: #ec8a86;
}

.dh__chip--off strong {
  color: #ec8a86;
}

.dh__chip--ferme {
  background: rgba(210, 85, 79, 0.18);
  border-color: rgba(210, 85, 79, 0.50);
  color: #ec8a86;
}

.dh__chip--ferme strong {
  color: #ec8a86;
}

.dh__chip--nuit {
  background: rgba(120, 110, 200, 0.18);
  border-color: rgba(120, 110, 200, 0.50);
  color: #c8c0f0;
}

.dh__chip--nuit strong {
  color: #c8c0f0;
}

.dh__chip--bug {
  background: rgba(210, 160, 60, 0.18);
  border-color: rgba(210, 160, 60, 0.50);
  color: #e8c878;
}

.dh__chip--bug strong {
  color: #e8c878;
}

.dh__chip--readonly {
  cursor: default;
}

.dh__chip--freq {
  background: rgba(0, 0, 0, 0.30);
  border-color: rgba(255, 255, 255, 0.08);
  color: var(--dp-text);
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  /* Le double-clic ne sélectionne pas le texte. */
  user-select: none;
}

.dh__chip--freq:hover:not(:disabled) {
  border-color: var(--dp-line-strong);
}

.dh__chip--freq:disabled {
  opacity: 0.6;
  cursor: wait;
}

.dh__chip--freq strong {
  color: var(--dp-text);
  font-variant-numeric: tabular-nums;
}

.dh__dropdown {
  position: relative;
}

.dh__menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 4px;
  background: var(--dp-panel-3);
  border: 1px solid var(--dp-line-strong);
  min-width: 140px;
}

.dh__menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: transparent;
  color: var(--dp-text);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.dh__menu-item:hover {
  background: var(--dp-accent-soft);
  color: var(--dp-accent);
}

.dh__freqs {
  flex-wrap: wrap;
  margin-left: 6px;
  margin-right: 8px;
}

.dh__reset {
  margin-left: auto;
}

.dh__reset-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 30px;
  padding: 5px 10px;
  border: 1px solid rgba(210, 85, 79, 0.45);
  border-radius: 0;
  color: #ec8a86;
  background: rgba(210, 85, 79, 0.12);
  font-size: 11px;
  font-weight: 650;
  white-space: nowrap;
  cursor: pointer;
}

.dh__reset-button:hover:not(:disabled) {
  background: rgba(210, 85, 79, 0.2);
}

.dh__reset-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.dh__spin {
  animation: dh-spin 1s linear infinite;
}

@keyframes dh-spin {
  to { transform: rotate(360deg); }
}

.dh-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(5, 8, 11, 0.72);
  backdrop-filter: blur(8px);
  animation: dh-overlay-in 0.22s ease-out;
}

.dh-modal__panel {
  width: min(460px, 94%);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--dp-line-strong);
  background: var(--dp-panel);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
  border-radius: 16px;
  overflow: hidden;
  animation: dh-panel-in 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.dh-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.dh-modal__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--dp-danger-line);
  border-radius: 10px;
  color: var(--dp-danger);
  background: var(--dp-danger-soft);
  flex-shrink: 0;
}

.dh-modal__header > div {
  min-width: 0;
}

.dh-modal__header h2 {
  margin: 0;
  color: var(--dp-text);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.dh-modal__header p {
  margin: 3px 0 0;
  color: var(--dp-text-2);
  font-size: 12px;
  line-height: 1.4;
}

.dh-modal__close {
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

.dh-modal__close:hover {
  color: var(--dp-text);
  background: var(--dp-panel-3);
  border-color: var(--dp-line-strong);
}

.dh-modal__option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid var(--dp-line);
  color: var(--dp-text);
  background: var(--dp-panel-2);
  cursor: pointer;
}

.dh-modal__option input {
  margin-top: 3px;
  accent-color: var(--dp-danger);
}

.dh-modal__option span {
  display: grid;
  gap: 4px;
  font-size: 12px;
}

.dh-modal__option small {
  color: var(--dp-text-dim);
  font-size: 10px;
}

.dh-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.dh-modal__actions button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--dp-line);
  color: var(--dp-text-2);
  background: transparent;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dh-modal__actions button:hover:not(:disabled) {
  border-color: var(--dp-line-strong);
  color: var(--dp-text);
  background: var(--dp-panel-3);
}

.dh-modal__actions .dh-modal__confirm {
  border-color: var(--dp-danger);
  color: #fff;
  background: var(--dp-danger);
}

.dh-modal__actions .dh-modal__confirm:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.dh-modal__actions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

@keyframes dh-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes dh-panel-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>