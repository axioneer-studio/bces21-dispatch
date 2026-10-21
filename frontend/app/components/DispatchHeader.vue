<script setup lang="ts">
import { updateState } from '~/composables/useDispatchApi'

const { state } = useDispatchStore()
const toast = useAppToast()

const hospitalOpen = ref<boolean>(true)
const hospitalMenu = ref<boolean>(false)

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

async function toggleLses() {
  const next = state.value.lses_status === 'ouvert' ? 'ferme' : 'ouvert'
  try {
    await updateState({ lses_status: next })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

async function toggleSafd() {
  const next = state.value.safd_status === 'disponible' ? 'indisponible' : 'disponible'
  try {
    await updateState({ safd_status: next })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

</script>

<template>
  <header class="dh">
    <div class="dh__brand">
      <span class="dh__title">Dispatch</span>
    </div>

    <div class="dh__group dh__freqs">
      <span class="dh__chip dh__chip--freq">
        <Icon name="lucide:radio" size="14" />
        Radio : <strong>{{ state.freq_147.replace(/\s*MHz$/i, '') }} MHz</strong>
      </span>
      <span class="dh__chip dh__chip--freq">
        <Icon name="lucide:radio" size="14" />
        Radio commune : <strong>{{ state.freq_570.replace(/\s*MHz$/i, '') }} MHz</strong>
      </span>
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
      <button
        type="button"
        class="dh__chip"
        :class="state.lses_status === 'ouvert' ? 'dh__chip--on' : 'dh__chip--off'"
        @click="toggleLses"
      >
        <Icon name="lucide:door-open" size="14" />
        LSES : <strong>{{ state.lses_status === 'ouvert' ? 'Ouvert' : 'Fermé' }}</strong>
      </button>
    </div>

    <div class="dh__group">
      <button
        type="button"
        class="dh__chip"
        :class="state.safd_status === 'disponible' ? 'dh__chip--on' : 'dh__chip--off'"
        @click="toggleSafd"
      >
        <Icon name="lucide:truck" size="14" />
        SAFD : <strong>{{ state.safd_status === 'disponible' ? 'Disponible' : 'Indisponible' }}</strong>
      </button>
    </div>

  </header>
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
}

.dh__chip--nuit {
  background: rgba(120, 110, 200, 0.18);
  border-color: rgba(120, 110, 200, 0.50);
  color: #c8c0f0;
}

.dh__chip--nuit strong {
  color: #c8c0f0;
}

.dh__chip--freq {
  background: rgba(0, 0, 0, 0.30);
  border-color: rgba(255, 255, 255, 0.08);
  color: var(--dp-text);
  cursor: default;
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
</style>