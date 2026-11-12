<script setup lang="ts">
import { randomizeFrequency, resetAssignments, updateState } from '~/composables/useDispatchApi'
import type { FrequencyKind } from '~/composables/useDispatchStore'

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

// --- Fréquences : double-clic pour en tirer une nouvelle entre les bornes de Paramètres ---

const frequencies = computed(() => [
  { kind: 'radio' as const, label: 'Radio', value: state.value.freq_147.replace(/\s*MHz$/i, '') },
  { kind: 'shared' as const, label: 'Radio commune', value: state.value.freq_570.replace(/\s*MHz$/i, '') }
])
/** Tirage en cours : les deux fréquences restent inactives jusqu'à la réponse. */
const randomizingFrequency = ref<FrequencyKind | null>(null)

async function randomize(kind: FrequencyKind, label: string) {
  if (randomizingFrequency.value !== null) return
  const bounds = snapshot.value.frequency_bounds[kind]
  if (bounds?.min == null || bounds.max == null) {
    toast.warning(`Réglez d’abord les bornes de la fréquence « ${label} » dans Administration → Paramètres.`)
    return
  }
  if (!window.confirm(`Générer une nouvelle fréquence « ${label} » au hasard, entre ${bounds.min} et ${bounds.max} ?`)) return
  randomizingFrequency.value = kind
  try {
    const result = await randomizeFrequency(kind)
    toast.success(`Nouvelle fréquence « ${label} » : ${result.current} MHz.`)
  } catch (error) {
    const detail = (error as { data?: { detail?: unknown } } | null)?.data?.detail
    toast.error(typeof detail === 'string' && detail ? detail : 'Changement de fréquence impossible.')
  } finally {
    randomizingFrequency.value = null
  }
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
        :disabled="randomizingFrequency !== null"
        :aria-busy="randomizingFrequency === frequency.kind"
        :title="`Double-cliquer pour générer une nouvelle ${frequency.label.toLowerCase()}`"
        @dblclick="randomize(frequency.kind, frequency.label)"
      >
        <Icon
          :name="randomizingFrequency === frequency.kind ? 'lucide:loader-circle' : 'lucide:radio'"
          size="14"
          :class="{ dh__spin: randomizingFrequency === frequency.kind }"
        />
        {{ frequency.label }} : <strong>{{ frequency.value }} MHz</strong>
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
        <h2 id="dh-reset-title">Réinitialiser le Dispatch ?</h2>
        <p id="dh-reset-description">
          Les employés affectés seront remis dans « Hors service BCES », les radios ON ou indisponibles passeront OFF et l’hôpital sera fermé.
        </p>
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
  padding: 18px;
  background: rgba(0, 0, 0, 0.68);
}

.dh-modal__panel {
  width: min(440px, 100%);
  padding: 20px;
  border: 1px solid var(--dp-line-strong);
  background: var(--dp-panel);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.45);
}

.dh-modal__panel h2 {
  margin: 0;
  color: var(--dp-text);
  font-size: 16px;
}

.dh-modal__panel > p {
  margin: 10px 0 16px;
  color: var(--dp-text-2);
  font-size: 12px;
  line-height: 1.5;
}

.dh-modal__option {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px;
  border: 1px solid var(--dp-line);
  color: var(--dp-text);
  background: var(--dp-panel-2);
  cursor: pointer;
}

.dh-modal__option input {
  margin-top: 2px;
  accent-color: var(--dp-danger);
}

.dh-modal__option span {
  display: grid;
  gap: 4px;
  font-size: 11px;
}

.dh-modal__option small {
  color: var(--dp-text-dim);
  font-size: 10px;
}

.dh-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.dh-modal__actions button {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 6px;
  padding: 0 11px;
  border: 1px solid var(--dp-line);
  color: var(--dp-text-2);
  background: transparent;
  font-size: 11px;
  font-weight: 650;
  cursor: pointer;
}

.dh-modal__actions .dh-modal__confirm {
  border-color: var(--dp-danger);
  color: #fff;
  background: var(--dp-danger);
}

.dh-modal__actions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
</style>