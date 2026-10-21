<script setup lang="ts">
import type { Agent, DispatchRadio } from '~/utils/agent'
import { agentAvatarUrl, agentDisplayName, agentFirstName } from '~/utils/agent'
import { updateRadio } from '~/composables/useDispatchApi'

const props = defineProps<{
  radio: DispatchRadio
  agents: Agent[]
}>()

const toast = useAppToast()

const status = computed<'on' | 'off' | 'loading'>(() => {
  if (props.radio.is_loading) return 'loading'
  return props.radio.is_on ? 'on' : 'off'
})

async function togglePower() {
  const next = !props.radio.is_on
  try {
    await updateRadio(props.radio.id, { is_on: next })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

async function setLoading() {
  try {
    await updateRadio(props.radio.id, {
      is_loading: true,
      is_on: false
    })
    setTimeout(async () => {
      try {
        await updateRadio(props.radio.id, { is_loading: false })
      } catch {
        /* ignore */
      }
    }, 2000)
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

async function editSerial() {
  const next = window.prompt('Numéro de série :', props.radio.serial)
  if (next === null || next === props.radio.serial) return
  try {
    await updateRadio(props.radio.id, { serial: next.trim() })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

async function setDoctor(agentId: number | null) {
  try {
    await updateRadio(props.radio.id, { doctor_id: agentId })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

const doctor = computed(() =>
  props.agents.find((a) => a.id === props.radio.doctor_id) ?? null
)

const doctorMenu = ref<boolean>(false)
function toggleDoctor() {
  doctorMenu.value = !doctorMenu.value
}
</script>

<template>
  <div class="rc" :data-status="status" :data-direction="radio.is_direction">
    <button
      type="button"
      class="rc__power"
      :data-status="status"
      :title="`Toggle ${radio.serial}`"
      @click="togglePower"
    >
      <span v-if="status === 'loading'" class="rc__power-emoji">⌛</span>
      <Icon v-else-if="status === 'on'" name="lucide:check" size="12" />
      <Icon v-else name="lucide:x" size="12" />
    </button>

    <button
      type="button"
      class="rc__serial"
      :title="`Éditer N° série (${radio.serial})`"
      @click="editSerial"
    >
      {{ radio.serial || '—' }}
    </button>

    <div class="rc__doctor" @click.stop>
      <button
        type="button"
        class="rc__doctor-btn"
        :class="{ 'rc__doctor-btn--set': !!doctor }"
        @click="toggleDoctor"
      >
        <img
          v-if="doctor && agentAvatarUrl(doctor)"
          :src="agentAvatarUrl(doctor)!"
          :alt="agentFirstName(doctor)"
          class="rc__avatar"
          width="18"
          height="18"
        />
        <span v-else-if="doctor" class="rc__avatar rc__avatar--ph">
          {{ agentFirstName(doctor).charAt(0).toUpperCase() }}
        </span>
        <Icon v-else name="lucide:user" size="12" />
        <span class="rc__doctor-name">{{ doctor ? agentDisplayName(doctor, agents) : '—' }}</span>
        <Icon name="lucide:chevron-down" size="10" />
      </button>
      <div v-if="doctorMenu" class="rc__doctor-menu">
        <button type="button" class="rc__doctor-item" @click="setDoctor(null)">
          <Icon name="lucide:x" size="11" /> Aucun
        </button>
        <button
          v-for="a in agents"
          :key="a.id"
          type="button"
          class="rc__doctor-item"
          :class="{ 'rc__doctor-item--active': a.id === radio.doctor_id }"
          @click="setDoctor(a.id)"
        >
          <img
            v-if="agentAvatarUrl(a)"
            :src="agentAvatarUrl(a)!"
            :alt="agentFirstName(a)"
            class="rc__avatar"
            width="14"
            height="14"
          />
          <span v-else class="rc__avatar rc__avatar--ph rc__avatar--sm">
            {{ agentFirstName(a).charAt(0).toUpperCase() }}
          </span>
          <span>{{ agentDisplayName(a, agents) }}</span>
        </button>
      </div>
    </div>

    <span class="rc__freq">
      <Icon name="lucide:radio" size="10" />
      {{ radio.frequency.replace(/\s*MHz$/i, '') }} MHz
    </span>

    <span class="rc__freq rc__freq--common">
      <Icon name="lucide:radio" size="10" />
      {{ radio.common_frequency.replace(/\s*MHz$/i, '') }} MHz
    </span>

    <button
      type="button"
      class="rc__loading"
      :class="{ 'rc__loading--active': status === 'loading' }"
      title="État chargement (2s)"
      @click="setLoading"
    >
      <span>⌛</span>
    </button>
  </div>
</template>

<style scoped>
.rc {
  display: grid;
  grid-template-columns: 26px 1fr 1.4fr 0.9fr 0.9fr 22px;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 10px;
}

.rc[data-direction='true'] {
  background: rgba(120, 110, 200, 0.10);
  border-color: rgba(120, 110, 200, 0.30);
}

.rc__power {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(210, 85, 79, 0.20);
  color: #ec8a86;
  border: 1px solid rgba(210, 85, 79, 0.45);
  cursor: pointer;
}

.rc__power[data-status='on'] {
  background: rgba(70, 153, 109, 0.25);
  border-color: rgba(70, 153, 109, 0.55);
  color: var(--bces-accent);
}

.rc__power[data-status='loading'] {
  background: rgba(214, 178, 78, 0.25);
  border-color: rgba(214, 178, 78, 0.55);
  color: #e6c46c;
}

.rc__power-emoji {
  font-size: 12px;
}

.rc__serial {
  background: transparent;
  border: none;
  color: var(--bces-text);
  font-family: ui-monospace, monospace;
  font-size: 10px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  padding: 2px 4px;
}

.rc__serial:hover {
  background: rgba(70, 153, 109, 0.10);
  color: var(--bces-accent);
}

.rc__doctor {
  position: relative;
}

.rc__doctor-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  padding: 2px 4px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--bces-text-dim);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
}

.rc__doctor-btn:hover,
.rc__doctor-btn--set {
  color: var(--bces-text);
  background: rgba(70, 153, 109, 0.08);
}

.rc__doctor-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rc__avatar {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.rc__avatar--sm {
  width: 14px;
  height: 14px;
  font-size: 9px;
}

.rc__avatar--ph {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
  font-weight: 700;
}

.rc__doctor-menu {
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
  min-width: 200px;
  max-height: 280px;
  overflow-y: auto;
}

.rc__doctor-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: transparent;
  color: var(--bces-text);
  font-size: 10px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.rc__doctor-item:hover {
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
}

.rc__doctor-item--active {
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
}

.rc__freq {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 2px 4px;
  background: rgba(0, 0, 0, 0.30);
  border: 1px solid var(--bces-border);
  color: var(--bces-text-muted);
  font-family: ui-monospace, monospace;
  font-size: 9px;
  font-weight: 600;
}

.rc__freq--common {
  background: rgba(214, 178, 78, 0.10);
  border-color: rgba(214, 178, 78, 0.30);
  color: #e6c46c;
}

.rc__loading {
  width: 20px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--bces-text-dim);
  border: 1px solid transparent;
  font-size: 12px;
  cursor: pointer;
}

.rc__loading:hover,
.rc__loading--active {
  color: #e6c46c;
  background: rgba(214, 178, 78, 0.10);
  border-color: rgba(214, 178, 78, 0.30);
}
</style>