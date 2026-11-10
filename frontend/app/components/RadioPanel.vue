<script setup lang="ts">
import type { DispatchRadio } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'
import { agentCallsign, agentDisplayName } from '~/utils/agent'
import { updateRadio } from '~/composables/useDispatchApi'

const props = defineProps<{
  radios: DispatchRadio[]
  agents: Agent[]
}>()

const toast = useAppToast()
type AgendaEvent = {
  id: number
  title: string
  starts_at: string
  ends_at: string | null
  description: string | null
  color: string
}

const agendaEvents = ref<AgendaEvent[]>([])
const agendaLoading = ref(false)
const agendaError = ref('')
let agendaRefreshTimer: ReturnType<typeof setInterval> | undefined
const agendaTimeFormatter = new Intl.DateTimeFormat('fr-FR', {
  hour: '2-digit',
  minute: '2-digit'
})

function agendaEventTime(event: AgendaEvent) {
  const startsAt = new Date(event.starts_at)
  if (!event.ends_at) return agendaTimeFormatter.format(startsAt)

  const endsAt = new Date(event.ends_at)
  const sameDay = startsAt.getFullYear() === endsAt.getFullYear()
    && startsAt.getMonth() === endsAt.getMonth()
    && startsAt.getDate() === endsAt.getDate()
  if (sameDay) {
    return `${agendaTimeFormatter.format(startsAt)} – ${agendaTimeFormatter.format(endsAt)}`
  }

  const nextDayAfterStart = new Date(startsAt)
  nextDayAfterStart.setHours(0, 0, 0, 0)
  nextDayAfterStart.setDate(nextDayAfterStart.getDate() + 1)
  const endDate = new Date(endsAt)
  endDate.setHours(0, 0, 0, 0)
  if (endDate.getTime() === nextDayAfterStart.getTime()) {
    return `${agendaTimeFormatter.format(startsAt)} - ${agendaTimeFormatter.format(endsAt)}`
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  if (startsAt < today) {
    return endsAt < tomorrow ? `Fin ${agendaTimeFormatter.format(endsAt)}` : 'En cours'
  }
  return agendaTimeFormatter.format(startsAt)
}

const todayEvents = computed(() => {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  const end = new Date(start)
  end.setDate(end.getDate() + 1)

  return agendaEvents.value
    .filter((event) => {
      const eventStart = new Date(event.starts_at)
      if (!event.ends_at) return eventStart >= start && eventStart < end
      return eventStart < end && new Date(event.ends_at) > start
    })
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at))
})

async function loadAgendaEvents() {
  if (agendaLoading.value) return
  agendaLoading.value = true
  agendaError.value = ''
  try {
    agendaEvents.value = await $fetch<AgendaEvent[]>('/api/agenda/events', {
      credentials: 'include'
    })
  } catch {
    agendaError.value = 'Événements indisponibles.'
  } finally {
    agendaLoading.value = false
  }
}

onMounted(() => {
  loadAgendaEvents()
  agendaRefreshTimer = setInterval(loadAgendaEvents, 5 * 60 * 1000)
})

onBeforeUnmount(() => {
  if (agendaRefreshTimer) clearInterval(agendaRefreshTimer)
})

const direction = computed(() => props.radios.filter((r) => r.is_direction))
const normal = computed(() => props.radios.filter((r) => !r.is_direction))

const statusOf = (r: DispatchRadio) =>
  r.is_loading ? 'loading' : r.is_on ? 'on' : 'off'

async function togglePower(radio: DispatchRadio) {
  try {
    await updateRadio(radio.id, { is_on: !radio.is_on, is_loading: false })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

async function setLoading(radio: DispatchRadio) {
  try {
    await updateRadio(radio.id, { is_loading: true, is_on: false })
    setTimeout(() => {
      updateRadio(radio.id, { is_loading: false }).catch(() => {})
    }, 2500)
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

async function editSerial(radio: DispatchRadio) {
  const next = window.prompt('Numéro de série :', radio.serial)
  if (next === null || next === radio.serial) return
  try {
    await updateRadio(radio.id, { serial: next.trim() })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}

const doctorMenu = ref<number | null>(null)
const doctorOf = (radio: DispatchRadio) =>
  props.agents.find((a) => a.id === radio.employee_id) ?? null

const doctorName = (radio: DispatchRadio) => {
  const d = doctorOf(radio)
  return d ? agentDisplayName(d, props.agents) : '—'
}

const doctorNum = (radio: DispatchRadio) => {
  const d = doctorOf(radio)
  return d ? agentCallsign(d) : ''
}

async function setDoctor(radio: DispatchRadio, agentId: number | null) {
  doctorMenu.value = null
  try {
    await updateRadio(radio.id, { employee_id: agentId })
  } catch {
    toast.error('Mise à jour impossible.')
  }
}
</script>

<template>
  <div class="rp">
    <section class="rp__group">
      <header class="rp__head rp__head--dir">
        <Icon name="lucide:radio-tower" size="12" />
        <span>Radio Direction</span>
        <span class="rp__count">{{ direction.length }}</span>
      </header>
      <div class="rp__rows">
        <div v-for="r in direction" :key="r.id" class="rp__row" :data-status="statusOf(r)">
          <button type="button" class="rp__power" :data-status="statusOf(r)" @click="togglePower(r)">
            <Icon v-if="statusOf(r) === 'on'" name="lucide:check" size="11" />
            <Icon v-else-if="statusOf(r) === 'off'" name="lucide:x" size="11" />
            <span v-else>⌛</span>
          </button>
          <button type="button" class="rp__serial" @click="editSerial(r)">
            {{ r.serial || '—' }}
          </button>
          <div class="rp__doctor" @click.stop>
            <button
              type="button"
              class="rp__doctor-btn"
              @click="doctorMenu = doctorMenu === r.id ? null : r.id"
            >
              <span class="rp__doctor-name">{{ doctorName(r) }}</span>
              <span v-if="doctorNum(r)" class="rp__doctor-num">{{ doctorNum(r) }}</span>
            </button>
            <div v-if="doctorMenu === r.id" class="rp__doctor-menu">
              <button type="button" class="rp__doctor-item" @click="setDoctor(r, null)">
                <Icon name="lucide:x" size="10" /> Aucun
              </button>
              <button
                v-for="a in agents" :key="a.id" type="button"
                class="rp__doctor-item"
                :class="{ 'rp__doctor-item--active': a.id === r.employee_id }"
                @click="setDoctor(r, a.id)"
              >
                <span>{{ agentDisplayName(a, agents) }}</span>
                <span class="rp__doctor-item-num">{{ agentCallsign(a) }}</span>
              </button>
            </div>
          </div>
          <span class="rp__freq">{{ r.frequency.replace(/\s*MHz$/i, '') }} MHz</span>
          <button
            type="button"
            class="rp__wait"
            :class="{ 'rp__wait--on': statusOf(r) === 'loading' }"
            title="Attente (2.5 s)"
            @click="setLoading(r)"
          >
            ⌛
          </button>
        </div>
        <div v-if="!direction.length" class="rp__empty">Aucune radio direction</div>
      </div>
    </section>

    <section class="rp__group rp__group--grow">
      <header class="rp__head">
        <Icon name="lucide:radio" size="12" />
        <span>Radio</span>
        <span class="rp__count">{{ normal.length }}</span>
      </header>
      <div class="rp__rows">
        <div v-for="r in normal" :key="r.id" class="rp__row" :data-status="statusOf(r)">
          <button type="button" class="rp__power" :data-status="statusOf(r)" @click="togglePower(r)">
            <Icon v-if="statusOf(r) === 'on'" name="lucide:check" size="11" />
            <Icon v-else-if="statusOf(r) === 'off'" name="lucide:x" size="11" />
            <span v-else>⌛</span>
          </button>
          <button type="button" class="rp__serial" @click="editSerial(r)">
            {{ r.serial || '—' }}
          </button>
          <div class="rp__doctor" @click.stop>
            <button
              type="button"
              class="rp__doctor-btn"
              @click="doctorMenu = doctorMenu === r.id ? null : r.id"
            >
              <span class="rp__doctor-name">{{ doctorName(r) }}</span>
              <span v-if="doctorNum(r)" class="rp__doctor-num">{{ doctorNum(r) }}</span>
            </button>
            <div v-if="doctorMenu === r.id" class="rp__doctor-menu">
              <button type="button" class="rp__doctor-item" @click="setDoctor(r, null)">
                <Icon name="lucide:x" size="10" /> Aucun
              </button>
              <button
                v-for="a in agents" :key="a.id" type="button"
                class="rp__doctor-item"
                :class="{ 'rp__doctor-item--active': a.id === r.employee_id }"
                @click="setDoctor(r, a.id)"
              >
                <span>{{ agentDisplayName(a, agents) }}</span>
                <span class="rp__doctor-item-num">{{ agentCallsign(a) }}</span>
              </button>
            </div>
          </div>
          <span class="rp__freq rp__freq--common">
            {{ r.common_frequency.replace(/\s*MHz$/i, '') }} MHz
          </span>
          <button
            type="button"
            class="rp__wait"
            :class="{ 'rp__wait--on': statusOf(r) === 'loading' }"
            title="Attente (2.5 s)"
            @click="setLoading(r)"
          >
            ⌛
          </button>
        </div>
        <div v-if="!normal.length" class="rp__empty">Aucune radio</div>
      </div>
    </section>

    <section class="rp__agenda">
      <header class="rp__head">
        <Icon name="lucide:calendar-days" size="12" />
        <NuxtLink to="/agenda" class="rp__agenda-link">Agenda du jour</NuxtLink>
        <span class="rp__count">{{ todayEvents.length }}</span>
      </header>
      <div class="rp__agenda-events" aria-live="polite">
        <p v-if="agendaLoading && !agendaEvents.length" class="rp__empty">Chargement…</p>
        <div v-else-if="agendaError" class="rp__agenda-error" role="alert">
          <span>{{ agendaError }}</span>
          <button type="button" @click="loadAgendaEvents">Réessayer</button>
        </div>
        <p v-else-if="!todayEvents.length" class="rp__empty">Aucun événement aujourd’hui</p>
        <template v-else>
          <article
            v-for="event in todayEvents"
            :key="event.id"
            class="rp__agenda-event"
            :style="{ '--event-color': event.color || 'var(--dp-accent)' }"
          >
            <time>{{ agendaEventTime(event) }}</time>
            <span>{{ event.title }}</span>
          </article>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.rp {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.rp__group {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-bottom: 1px solid var(--dp-line);
}

.rp__group--grow {
  flex: 1;
  border-bottom: none;
}

.rp__agenda {
  display: flex;
  flex: 0 1 auto;
  flex-direction: column;
  max-height: 200px;
  min-height: 150px;
  border-top: 1px solid var(--dp-line);
}

.rp__agenda-link {
  color: inherit;
  text-decoration: none;
}

.rp__agenda-link:hover {
  color: var(--dp-accent);
}

.rp__agenda-events {
  flex: 0 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 3px;
}

.rp__agenda-event {
  display: flex;
  gap: 6px;
  align-items: baseline;
  margin-bottom: 3px;
  padding: 4px 5px;
  border-left: 2px solid var(--event-color);
  background: var(--dp-panel-2);
  color: var(--dp-text-2);
  font-size: 10px;
}

.rp__agenda-event time {
  flex: 0 0 auto;
  color: var(--dp-text-dim);
  font-family: ui-monospace, monospace;
  font-size: 9px;
}

.rp__agenda-event span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rp__agenda-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px 4px;
  color: var(--dp-danger);
  font-size: 10px;
}

.rp__agenda-error button {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.rp__head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  background: var(--dp-panel-3);
  border-bottom: 1px solid var(--dp-line);
  color: var(--dp-text-2);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.rp__head--dir {
  color: var(--dp-info);
  box-shadow: inset 3px 0 0 var(--dp-info-soft);
}

.rp__count {
  margin-left: auto;
  color: var(--dp-text-dim);
  font-variant-numeric: tabular-nums;
}

.rp__rows {
  flex: 1;
  overflow-y: auto;
  padding: 2px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
}

.rp__row {
  display: grid;
  grid-template-columns: 22px minmax(52px, 0.9fr) minmax(64px, 1.3fr) minmax(48px, auto) 18px;
  align-items: center;
  gap: 3px;
  padding: 3px 4px;
  background: var(--dp-panel-2);
  border: 1px solid var(--dp-line);
  border-radius: 3px;
}

.rp__row:hover {
  border-color: var(--dp-line-strong);
}

.rp__row[data-status='on'] {
  border-left: 2px solid var(--dp-accent);
}

.rp__row[data-status='loading'] {
  border-left: 2px solid var(--dp-warn);
}

.rp__row[data-status='off'] {
  border-left: 2px solid var(--dp-line-strong);
}

.rp__power {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--dp-panel-3);
  color: var(--dp-text-dim);
  border: 1px solid var(--dp-line);
  border-radius: 2px;
  cursor: pointer;
  font-size: 10px;
}

.rp__power[data-status='on'] {
  background: var(--dp-accent-soft);
  border-color: var(--dp-accent-line);
  color: var(--dp-accent);
}

.rp__power[data-status='loading'] {
  background: var(--dp-warn-soft);
  border-color: var(--dp-warn-line);
  color: var(--dp-warn);
}

.rp__serial {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: var(--dp-text-2);
  font-family: ui-monospace, 'SFMono-Regular', monospace;
  font-size: 9.5px;
  font-weight: 600;
  text-align: left;
  padding: 2px 3px;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rp__serial:hover {
  background: var(--dp-panel-3);
  border-color: var(--dp-line-strong);
  color: var(--dp-text);
}

.rp__doctor {
  position: relative;
  min-width: 0;
}

.rp__doctor-btn {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px;
  width: 100%;
  padding: 2px 4px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: var(--dp-text-2);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  min-width: 0;
}

.rp__doctor-btn:hover {
  background: var(--dp-panel-3);
  border-color: var(--dp-line-strong);
  color: var(--dp-text);
}

.rp__doctor-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rp__doctor-num {
  font-family: ui-monospace, monospace;
  font-size: 8.5px;
  color: var(--dp-text-dim);
  flex-shrink: 0;
}

.rp__doctor-menu {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  padding: 3px;
  background: var(--dp-panel-3);
  border: 1px solid var(--dp-line-strong);
  border-radius: 3px;
  min-width: 170px;
  max-height: 240px;
  overflow-y: auto;
}

.rp__doctor-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 6px;
  background: transparent;
  border: none;
  border-radius: 2px;
  color: var(--dp-text-2);
  font-size: 10px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
}

.rp__doctor-item:hover,
.rp__doctor-item--active {
  background: var(--dp-accent-soft);
  color: var(--dp-accent);
}

.rp__doctor-item-num {
  font-family: ui-monospace, monospace;
  font-size: 8.5px;
  color: var(--dp-text-dim);
}

.rp__freq {
  display: inline-block;
  padding: 2px 3px;
  background: var(--dp-panel-3);
  border: 1px solid var(--dp-line);
  border-radius: 2px;
  color: var(--dp-text-dim);
  font-family: ui-monospace, monospace;
  font-size: 8.5px;
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
}

.rp__freq--common {
  background: var(--dp-warn-soft);
  border-color: var(--dp-warn-line);
  color: var(--dp-warn);
}

.rp__wait {
  width: 16px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: var(--dp-text-dim);
  font-size: 10px;
  cursor: pointer;
}

.rp__wait:hover,
.rp__wait--on {
  color: var(--dp-warn);
  background: var(--dp-warn-soft);
  border-color: var(--dp-warn-line);
}

.rp__empty {
  padding: 12px;
  text-align: center;
  color: var(--dp-text-dim);
  font-size: 10px;
  font-style: italic;
}
</style>