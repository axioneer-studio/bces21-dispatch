<script setup lang="ts">
import type { DispatchRadio } from '~/composables/useDispatchStore'
import type { RealtimeAgendaEvent } from '~/composables/useRealtimeData'
import type { Agent } from '~/utils/agent'
import { agentDisplayName, sortAgentsByGradeAndArrival } from '~/utils/agent'
import { isDirectionRadio, radioStatus, splitRadios } from '~/utils/radios'
import type { RadioStatus } from '~/utils/radios'
import { updateRadio } from '~/composables/useDispatchApi'

const props = defineProps<{
  radios: DispatchRadio[]
  agents: Agent[]
  /** Employés dans la réserve « Hors service BCES » : leurs radios sont verrouillées OFF. */
  pool: Agent[]
}>()

const toast = useAppToast()
const { agendaEvents, agendaLoaded } = useRealtimeData()
const selectedAgendaEvent = ref<RealtimeAgendaEvent | null>(null)
const agendaTimeFormatter = new Intl.DateTimeFormat('fr-FR', {
  hour: '2-digit',
  minute: '2-digit'
})
const agendaDateTimeFormatter = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  hour: '2-digit', minute: '2-digit'
})

function openAgendaEvent(event: RealtimeAgendaEvent) {
  selectedAgendaEvent.value = event
}

function closeAgendaEvent() {
  selectedAgendaEvent.value = null
}

function agendaEventTime(event: RealtimeAgendaEvent) {
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

const agendaDays = computed(() => {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  const end = new Date(start)
  end.setDate(end.getDate() + 7)

  const dayKey = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
  const groups = new Map<string, { key: string; label: string; events: RealtimeAgendaEvent[] }>()
  for (let offset = 0; offset < 7; offset += 1) {
    const date = new Date(start)
    date.setDate(date.getDate() + offset)
    groups.set(dayKey(date), {
      key: dayKey(date),
      label: offset === 0 ? "Aujourd'hui" : offset === 1 ? 'Demain' : new Intl.DateTimeFormat('fr-FR', {
        weekday: 'short', day: 'numeric', month: 'short'
      }).format(date),
      events: []
    })
  }

  for (const event of agendaEvents.value) {
    const eventStart = new Date(event.starts_at)
    const eventEnd = event.ends_at ? new Date(event.ends_at) : null
    const overlapsWindow = eventEnd
      ? eventStart < end && eventEnd > start
      : eventStart >= start && eventStart < end
    if (!overlapsWindow) continue

    // Un événement qui a commencé avant aujourd'hui mais continue est listé aujourd'hui.
    const displayDate = eventStart < start ? start : eventStart
    groups.get(dayKey(displayDate))?.events.push(event)
  }

  return [...groups.values()]
    .filter((group) => group.events.length > 0)
    .map((group) => ({
      ...group,
      events: group.events.sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at))
    }))
})
const agendaEventCount = computed(() =>
  agendaDays.value.reduce((count, day) => count + day.events.length, 0)
)

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
  document.addEventListener('click', closeMenu)
  document.addEventListener('scroll', closeOnScroll, true)
  window.addEventListener('resize', closeMenu)
})

onBeforeUnmount(() => {
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

const poolIds = computed(() => new Set(props.pool.map((agent) => agent.id)))
const employeeInPool = (radio: DispatchRadio) =>
  radio.employee_id !== null && poolIds.value.has(radio.employee_id)

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
  if (employeeInPool(radio)) {
    toast.warning(
      'Employé hors service BCES : la radio reste éteinte.'
    )
    return
  }
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
        <NuxtLink to="/agenda" class="rp__agenda-link">Agenda · 7 jours</NuxtLink>
        <span class="rp__count">{{ agendaEventCount }}</span>
      </header>
      <div class="rp__agenda-events" aria-live="polite">
        <p v-if="!agendaLoaded" class="rp__empty">Connexion à l’agenda…</p>
        <p v-else-if="!agendaDays.length" class="rp__empty">Aucun événement cette semaine</p>
        <template v-else>
          <section v-for="day in agendaDays" :key="day.key" class="rp__agenda-day">
            <h3>{{ day.label }}</h3>
            <button
              type="button"
              v-for="event in day.events"
              :key="event.id"
              class="rp__agenda-event"
              :aria-label="`Détails de ${event.title}`"
              :style="{ '--event-color': event.color || 'var(--dp-accent)' }"
              @click="openAgendaEvent(event)"
            >
              <time>{{ agendaEventTime(event) }}</time>
              <span>{{ event.title }}</span>
            </button>
          </section>
        </template>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="selectedAgendaEvent"
        class="rp__agenda-detail-overlay"
        @click.self="closeAgendaEvent"
        @keydown.esc="closeAgendaEvent"
      >
        <section class="rp__agenda-detail-panel" role="dialog" aria-modal="true" aria-labelledby="agenda-detail-title">
          <header class="rp__agenda-detail-head">
            <div class="rp__agenda-detail-icon">
              <Icon name="lucide:calendar-days" size="18" />
            </div>
            <div class="rp__agenda-detail-heading">
              <h2 id="agenda-detail-title">{{ selectedAgendaEvent.title }}</h2>
              <p>Détails de l’événement</p>
            </div>
            <button type="button" class="rp__agenda-detail-close" aria-label="Fermer" @click="closeAgendaEvent">
              <Icon name="lucide:x" size="16" />
            </button>
          </header>
          <div class="rp__agenda-detail-body">
            <div class="rp__agenda-detail-time">
              <span class="rp__agenda-detail-label">Date et heure</span>
              <strong>
                {{ agendaDateTimeFormatter.format(new Date(selectedAgendaEvent.starts_at)) }}
                <template v-if="selectedAgendaEvent.ends_at">
                  <span> – </span>{{ agendaDateTimeFormatter.format(new Date(selectedAgendaEvent.ends_at)) }}
                </template>
              </strong>
            </div>
            <div class="rp__agenda-detail-description">
              <span class="rp__agenda-detail-label">Description</span>
              <p>{{ selectedAgendaEvent.description?.trim() || 'Aucune description.' }}</p>
            </div>
          </div>
          <footer class="rp__agenda-detail-footer">
            <button type="button" class="rp__agenda-detail-action" @click="closeAgendaEvent">Fermer</button>
          </footer>
        </section>
      </div>
    </Teleport>

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
            :disabled="option.value !== 'off' && (employeeInPool(menuRadio) || !isAssigned(menuRadio))"
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

.rp__agenda-day h3 {
  margin: 4px 2px 3px;
  color: var(--dp-text-dim);
  font-size: 9px;
  font-weight: 700;
  text-transform: capitalize;
}

.rp__agenda-event {
  display: flex;
  gap: 6px;
  align-items: baseline;
  width: 100%;
  margin-bottom: 3px;
  padding: 4px 5px;
  border: 0;
  border-left: 2px solid var(--event-color);
  background: var(--dp-panel-2);
  color: var(--dp-text-2);
  font-size: 10px;
  text-align: left;
  cursor: pointer;
}

.rp__agenda-event:hover,
.rp__agenda-event:focus-visible {
  background: var(--dp-panel-3);
}

.rp__agenda-event:focus-visible {
  outline: 1px solid var(--dp-accent);
  outline-offset: 1px;
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

.rp__agenda-detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(5, 8, 11, 0.72);
  backdrop-filter: blur(8px);
}

.rp__agenda-detail-panel {
  width: min(520px, 94%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--dp-line-strong);
  border-radius: 16px;
  background: var(--dp-panel);
  color: var(--dp-text);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
}

.rp__agenda-detail-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.rp__agenda-detail-icon {
  display: grid;
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--dp-accent-line);
  border-radius: 10px;
  background: var(--dp-accent-soft);
  color: var(--dp-accent);
}

.rp__agenda-detail-heading {
  min-width: 0;
  flex: 1;
}

.rp__agenda-detail-heading h2 {
  margin: 0;
  color: var(--dp-text);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.rp__agenda-detail-heading p {
  margin: 3px 0 0;
  color: var(--dp-text-2);
  font-size: 12px;
  line-height: 1.4;
}

.rp__agenda-detail-close {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--dp-line);
  border-radius: 8px;
  background: transparent;
  color: var(--dp-text-2);
  cursor: pointer;
}

.rp__agenda-detail-close:hover {
  border-color: var(--dp-line-strong);
  background: var(--dp-panel-3);
  color: var(--dp-text);
}

.rp__agenda-detail-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
  padding: 20px 24px;
}

.rp__agenda-detail-time,
.rp__agenda-detail-description {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin: 0;
  padding: 14px 16px;
  border: 1px solid var(--dp-line);
  border-radius: 10px;
  background: var(--dp-panel-2);
}

.rp__agenda-detail-label {
  color: var(--dp-text-2);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.rp__agenda-detail-time strong {
  color: var(--dp-accent);
  font-size: 13px;
  font-weight: 650;
  line-height: 1.5;
  text-transform: capitalize;
}

.rp__agenda-detail-description p {
  margin: 0;
  color: var(--dp-text);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.rp__agenda-detail-footer {
  display: flex;
  justify-content: flex-end;
  padding: 14px 24px;
  border-top: 1px solid var(--dp-line);
}

.rp__agenda-detail-action {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--dp-line);
  border-radius: 8px;
  background: transparent;
  color: var(--dp-text-2);
  font-size: 12px;
  cursor: pointer;
}

.rp__agenda-detail-action:hover {
  background: var(--dp-panel-3);
  color: var(--dp-text);
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
