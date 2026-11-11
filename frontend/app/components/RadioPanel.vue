<script setup lang="ts">
import type { DispatchRadio } from '~/composables/useDispatchStore'
import type { Agent } from '~/utils/agent'
import { agentDisplayName, sortAgentsByGradeAndArrival } from '~/utils/agent'
import { isDirectionRadio, radioStatus, splitRadios } from '~/utils/radios'
import type { RadioStatus } from '~/utils/radios'
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

// --- Menu (porteur ou état) : un seul ouvert, rendu dans <body> pour pouvoir
// dépasser de la case, positionné sous la ligne de la radio (ou au-dessus
// s'il manque de place en bas).

type MenuKind = 'holder' | 'status'
const MENU_MIN_WIDTH = 220
const MENU_MAX_HEIGHT = 260
const VIEWPORT_MARGIN = 8

const openMenu = ref<{ radioId: number; kind: MenuKind; style: Record<string, string> } | null>(null)
const menuEl = ref<HTMLElement | null>(null)
const menuRadio = computed(() =>
  openMenu.value ? props.radios.find((radio) => radio.id === openMenu.value!.radioId) ?? null : null
)

const isMenuOpen = (radio: DispatchRadio, kind: MenuKind) =>
  openMenu.value?.radioId === radio.id && openMenu.value.kind === kind

function menuStyle(row: HTMLElement): Record<string, string> {
  const rect = row.getBoundingClientRect()
  const width = Math.min(Math.max(rect.width, MENU_MIN_WIDTH), window.innerWidth - 2 * VIEWPORT_MARGIN)
  const left = Math.max(VIEWPORT_MARGIN, Math.min(rect.left, window.innerWidth - width - VIEWPORT_MARGIN))
  const spaceBelow = window.innerHeight - rect.bottom - VIEWPORT_MARGIN
  const spaceAbove = rect.top - VIEWPORT_MARGIN
  const above = spaceBelow < MENU_MAX_HEIGHT && spaceAbove > spaceBelow
  const maxHeight = Math.min(MENU_MAX_HEIGHT, above ? spaceAbove : spaceBelow)
  return {
    left: `${left}px`,
    width: `${width}px`,
    maxHeight: `${maxHeight}px`,
    ...(above
      ? { bottom: `${window.innerHeight - rect.top + 2}px` }
      : { top: `${rect.bottom + 2}px` })
  }
}

function toggleMenu(radio: DispatchRadio, kind: MenuKind, event: MouseEvent) {
  if (isMenuOpen(radio, kind)) return closeMenu()
  const row = (event.currentTarget as HTMLElement).closest<HTMLElement>('.rp__row')
  if (!row) return
  openMenu.value = { radioId: radio.id, kind, style: menuStyle(row) }
}

const closeMenu = () => { openMenu.value = null }

/** Le menu est positionné une fois : on le ferme si la page ou la liste défile. */
function closeOnScroll(event: Event) {
  if (openMenu.value && !menuEl.value?.contains(event.target as Node)) closeMenu()
}

onMounted(() => {
  loadAgendaEvents()
  agendaRefreshTimer = setInterval(loadAgendaEvents, 5 * 60 * 1000)
  document.addEventListener('click', closeMenu)
  document.addEventListener('scroll', closeOnScroll, true)
  window.addEventListener('resize', closeMenu)
})

onBeforeUnmount(() => {
  if (agendaRefreshTimer) clearInterval(agendaRefreshTimer)
  document.removeEventListener('click', closeMenu)
  document.removeEventListener('scroll', closeOnScroll, true)
  window.removeEventListener('resize', closeMenu)
})

const sections = computed(() => {
  const { direction, normal } = splitRadios(props.radios, props.agents)
  return [
    { key: 'direction', title: 'Radio Direction', icon: 'lucide:radio-tower', radios: direction, empty: 'Aucune radio direction' },
    { key: 'normal', title: 'Radio', icon: 'lucide:radio', radios: normal, empty: 'Aucune radio' }
  ] as const
})

/** Employés actifs sans radio, dans l'ordre de la réserve. */
const agentsWithoutRadio = computed(() => {
  const equipped = new Set(
    props.radios.flatMap((radio) => (radio.employee_id === null ? [] : [radio.employee_id]))
  )
  return sortAgentsByGradeAndArrival(
    props.agents.filter((agent) => agent.is_active && !equipped.has(agent.id))
  )
})

const hasDirectionMembers = computed(() =>
  props.agents.some((agent) => agent.is_active && agent.grade_is_direction)
)

const agentsById = computed(() => new Map(props.agents.map((agent) => [agent.id, agent])))
const inDirection = (radio: DispatchRadio) => isDirectionRadio(radio, agentsById.value)

/** Proposés à l'affectation : une radio Direction ne passe qu'à un autre membre de la Direction. */
const candidatesFor = (radio: DispatchRadio) =>
  inDirection(radio)
    ? agentsWithoutRadio.value.filter((agent) => agent.grade_is_direction)
    : agentsWithoutRadio.value

function noCandidateMessage(radio: DispatchRadio): string {
  if (!inDirection(radio)) return 'Tous les employés actifs ont une radio.'
  return hasDirectionMembers.value
    ? 'Tous les membres de la Direction ont une radio.'
    : 'Aucun membre de la Direction : cochez « Fait partie de la Direction » sur un grade.'
}

const isAssigned = (r: DispatchRadio) => r.employee_id !== null

const STATUS_OPTIONS: { value: RadioStatus; label: string }[] = [
  { value: 'on', label: 'ON' },
  { value: 'standby', label: 'Indisponible' },
  { value: 'off', label: 'OFF' }
]
const statusLabel = (r: DispatchRadio) =>
  STATUS_OPTIONS.find((option) => option.value === radioStatus(r))!.label

/** Message d'erreur renvoyé par l'API (`detail`), sinon le message par défaut. */
function apiError(error: unknown, fallback: string): string {
  const detail = (error as { data?: { detail?: unknown } } | null)?.data?.detail
  return typeof detail === 'string' && detail ? detail : fallback
}

async function setStatus(radio: DispatchRadio, status: RadioStatus) {
  closeMenu()
  if (status === radioStatus(radio)) return
  if (status !== 'off' && !isAssigned(radio)) {
    toast.warning('Affectez la radio à un employé avant de l’allumer.')
    return
  }
  try {
    await updateRadio(radio.id, { is_on: status === 'on', is_loading: status === 'standby' })
  } catch (error) {
    toast.error(apiError(error, 'Mise à jour impossible.'))
  }
}

const doctorOf = (radio: DispatchRadio) =>
  props.agents.find((a) => a.id === radio.employee_id) ?? null

const doctorName = (radio: DispatchRadio) => {
  const d = doctorOf(radio)
  return d ? agentDisplayName(d, props.agents) : '—'
}


async function setDoctor(radio: DispatchRadio, agentId: number | null) {
  closeMenu()
  if (agentId === radio.employee_id) return
  try {
    await updateRadio(radio.id, { employee_id: agentId })
  } catch (error) {
    toast.error(apiError(error, 'Mise à jour impossible.'))
  }
}
</script>

<template>
  <div class="rp">
    <section
      v-for="section in sections"
      :key="section.key"
      class="rp__group"
      :class="{ 'rp__group--grow': section.key === 'normal' }"
    >
      <header class="rp__head" :class="{ 'rp__head--dir': section.key === 'direction' }">
        <Icon :name="section.icon" size="12" />
        <span>{{ section.title }}</span>
        <span class="rp__count">{{ section.radios.length }}</span>
      </header>
      <div class="rp__rows">
        <div
          v-for="r in section.radios"
          :key="r.id"
          class="rp__row"
          :data-status="radioStatus(r)"
        >
          <span class="rp__serial">{{ r.serial || '—' }}</span>
          <div class="rp__doctor" @click.stop>
            <button
              type="button"
              class="rp__doctor-btn"
              :aria-expanded="isMenuOpen(r, 'holder')"
              @click="toggleMenu(r, 'holder', $event)"
            >
              <span class="rp__doctor-name">{{ doctorName(r) }}</span>
            </button>
          </div>
          <div class="rp__status" @click.stop>
            <button
              type="button"
              class="rp__power"
              :data-status="radioStatus(r)"
              :title="`État : ${statusLabel(r)}`"
              :aria-label="`État de la radio : ${statusLabel(r)}`"
              :aria-expanded="isMenuOpen(r, 'status')"
              @click="toggleMenu(r, 'status', $event)"
            >
              <Icon v-if="radioStatus(r) === 'on'" name="lucide:check" size="11" />
              <Icon v-else-if="radioStatus(r) === 'off'" name="lucide:x" size="11" />
              <Icon v-else name="lucide:hourglass" size="11" />
            </button>
          </div>
        </div>
        <div v-if="!section.radios.length" class="rp__empty">{{ section.empty }}</div>
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

    <Teleport to="body">
      <div
        v-if="openMenu && menuRadio"
        ref="menuEl"
        class="rp__doctor-menu"
        :style="openMenu.style"
        @click.stop
      >
        <template v-if="openMenu.kind === 'holder'">
          <template v-if="doctorOf(menuRadio)">
            <div class="rp__doctor-current">
              <span>{{ agentDisplayName(doctorOf(menuRadio)!, agents) }}</span>
            </div>
            <button type="button" class="rp__doctor-item" @click="setDoctor(menuRadio, null)">
              <Icon name="lucide:x" size="10" /> Retirer l’affectation
            </button>
          </template>
          <p class="rp__doctor-label">{{ inDirection(menuRadio) ? 'Direction sans radio' : 'Sans radio' }}</p>
          <button
            v-for="a in candidatesFor(menuRadio)" :key="a.id" type="button"
            class="rp__doctor-item"
            @click="setDoctor(menuRadio, a.id)"
          >
            <span>{{ agentDisplayName(a, agents) }}</span>
          </button>
          <p v-if="!candidatesFor(menuRadio).length" class="rp__doctor-none">
            {{ noCandidateMessage(menuRadio) }}
          </p>
        </template>
        <template v-else>
          <button
            v-for="option in STATUS_OPTIONS"
            :key="option.value"
            type="button"
            class="rp__doctor-item rp__status-item"
            :class="{ 'rp__doctor-item--active': radioStatus(menuRadio) === option.value }"
            :data-status="option.value"
            :disabled="option.value !== 'off' && !isAssigned(menuRadio)"
            @click="setStatus(menuRadio, option.value)"
          >
            <Icon v-if="option.value === 'on'" name="lucide:check" size="10" />
            <Icon v-else-if="option.value === 'off'" name="lucide:x" size="10" />
            <Icon v-else name="lucide:hourglass" size="10" />
            <strong>{{ option.label }}</strong>
          </button>
          <p v-if="!isAssigned(menuRadio)" class="rp__doctor-none">
            Affectez la radio avant de l’allumer.
          </p>
        </template>
      </div>
    </Teleport>
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
  overflow-x: hidden;
  overflow-y: auto;
  padding: 2px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
}

.rp__row {
  display: grid;
  /* Numéro, porteur, puis l'état à droite comme sur le Google Sheets. */
  grid-template-columns: minmax(52px, 0.9fr) minmax(64px, 1.3fr) 22px;
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

.rp__row[data-status='standby'] {
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

.rp__power:hover {
  border-color: var(--dp-line-strong);
}

.rp__power[data-status='on'] {
  background: var(--dp-accent-soft);
  border-color: var(--dp-accent-line);
  color: var(--dp-accent);
}

.rp__power[data-status='standby'] {
  background: var(--dp-warn-soft);
  border-color: var(--dp-warn-line);
  color: var(--dp-warn);
}

.rp__serial {
  padding: 2px 3px;
  color: var(--dp-text-2);
  font-family: ui-monospace, 'SFMono-Regular', monospace;
  font-size: 9.5px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rp__status {
  display: flex;
  justify-content: flex-end;
}

.rp__status-item {
  justify-content: flex-start;
}

.rp__status-item[data-status='on'] { color: var(--dp-accent); }
.rp__status-item[data-status='standby'] { color: var(--dp-warn); }

.rp__status-item:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.rp__status-item:disabled:hover {
  background: transparent;
}

.rp__doctor {
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


/* Rendu dans <body> : position et taille calculées depuis la ligne (menuStyle). */
.rp__doctor-menu {
  position: fixed;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  padding: 3px;
  background: var(--dp-panel-3);
  border: 1px solid var(--dp-line-strong);
  border-radius: 3px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
  overflow-x: hidden;
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

.rp__doctor-current {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 2px;
  background: var(--dp-accent-soft);
  color: var(--dp-accent);
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.rp__doctor-item > span,
.rp__doctor-current > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rp__doctor-label {
  margin: 4px 0 2px;
  padding: 2px 6px 3px;
  border-top: 1px solid var(--dp-line);
  color: var(--dp-text-dim);
  font-size: 8.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.rp__doctor-none {
  margin: 0;
  padding: 4px 6px;
  color: var(--dp-text-dim);
  font-size: 10px;
  font-style: italic;
  white-space: normal;
}




.rp__empty {
  padding: 12px;
  text-align: center;
  color: var(--dp-text-dim);
  font-size: 10px;
  font-style: italic;
}
</style>