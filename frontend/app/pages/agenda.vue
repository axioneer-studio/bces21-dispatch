<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Agenda partagé · BCES' })

type View = 'day' | 'week' | 'month' | 'year' | 'agenda'
type EventItem = {
  id: number
  title: string
  starts_at: string
  ends_at: string | null
  description: string | null
  color: string
}

const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
const { data: currentUser } = await useAsyncData('agenda-current-user', async () => {
  try {
    return await $fetch<{
      is_super_admin: boolean
      grade_permissions: string[]
    }>('/api/me', { credentials: 'include', headers: requestHeaders })
  } catch {
    return null
  }
})

const views: { value: View; label: string; icon: string }[] = [
  { value: 'day', label: 'Jour', icon: 'lucide:calendar' },
  { value: 'week', label: 'Semaine', icon: 'lucide:columns-3' },
  { value: 'month', label: 'Mois', icon: 'lucide:calendar-days' },
  { value: 'year', label: 'Année', icon: 'lucide:calendar-range' },
  { value: 'agenda', label: 'À venir', icon: 'lucide:list' }
]

const dayNames = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const cursor = ref(new Date())
const view = ref<View>('month')
const events = ref<EventItem[]>([])
const loading = ref(true)
const loadError = ref('')
const actionError = ref('')
const authRequired = ref(false)
const canManageEvents = computed(() => Boolean(
  currentUser.value?.is_super_admin ||
  currentUser.value?.grade_permissions.includes('agenda.manage_events')
))
const editorOpen = ref(false)
const saving = ref(false)
const deleting = ref(false)
const calendarEnabled = ref(true)
const editingEvent = ref<EventItem | null>(null)

const form = reactive({
  title: '',
  starts_at: '',
  ends_at: '',
  description: '',
  color: '#58ad7b'
})

const monthFormatter = new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric' })
const yearMonthFormatter = new Intl.DateTimeFormat('fr-FR', { month: 'long' })
const dateFormatter = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric'
})
const shortDateFormatter = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })
const monthLabel = computed(() => monthFormatter.format(cursor.value))
const todayKey = computed(() => dateKey(new Date()))
const periodLabel = computed(() => {
  if (view.value === 'year') return String(cursor.value.getFullYear())
  if (view.value === 'day') return dateFormatter.format(cursor.value)
  if (view.value === 'week') {
    const first = weekDays.value[0]
    const last = weekDays.value[6]
    if (!first || !last) return monthLabel.value
    return first.getMonth() === last.getMonth()
      ? `${first.getDate()} – ${new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).format(last)}`
      : `${shortDateFormatter.format(first)} – ${new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).format(last)}`
  }
  return monthLabel.value
})

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function dateKey(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function startOfWeek(date: Date) {
  const result = new Date(date)
  result.setHours(0, 0, 0, 0)
  result.setDate(result.getDate() - ((result.getDay() + 6) % 7))
  return result
}

const weekDays = computed(() => {
  const first = startOfWeek(cursor.value)
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(first)
    date.setDate(first.getDate() + index)
    return date
  })
})

const monthDays = computed(() => {
  const first = new Date(cursor.value.getFullYear(), cursor.value.getMonth(), 1)
  const start = startOfWeek(first)
  const dayCount = new Date(cursor.value.getFullYear(), cursor.value.getMonth() + 1, 0).getDate()
  const cellCount = Math.ceil(((first.getDay() + 6) % 7 + dayCount) / 7) * 7

  return Array.from({ length: cellCount }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    return date
  })
})

const visibleEvents = computed(() => calendarEnabled.value ? events.value : [])
const upcomingEvents = computed(() => visibleEvents.value
  .filter(event => {
    const todayStart = new Date()
    todayStart.setHours(0, 0, 0, 0)
    const startsAt = new Date(event.starts_at)
    return event.ends_at
      ? new Date(event.ends_at) > todayStart
      : startsAt >= todayStart
  })
  .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at)))
const agendaDays = computed(() => {
  const groups = new Map<string, { date: Date; events: EventItem[] }>()
  for (const event of upcomingEvents.value) {
    const startsAt = new Date(event.starts_at)
    const date = dateKey(startsAt) < todayKey.value ? new Date() : startsAt
    const key = dateKey(date)
    const group = groups.get(key) ?? { date, events: [] }
    group.events.push(event)
    groups.set(key, group)
  }
  return [...groups.values()]
})

function eventsFor(date: Date) {
  return visibleEvents.value
    .filter(event => eventOccursOnDate(event, date))
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at))
}

function miniDayLabel(date: Date) {
  const dayEvents = eventsFor(date)
  if (!dayEvents.length) return formatDay(date)

  const eventCount = dayEvents.length
  const titles = dayEvents.slice(0, 3).map(event => event.title).join(', ')
  const remaining = eventCount > 3 ? ` et ${eventCount - 3} autre(s)` : ''
  return `${formatDay(date)} · ${eventCount} événement${eventCount > 1 ? 's' : ''} : ${titles}${remaining}`
}

function eventOccursOnDate(event: EventItem, date: Date) {
  const dayStart = new Date(date)
  dayStart.setHours(0, 0, 0, 0)
  const dayEnd = new Date(dayStart)
  dayEnd.setDate(dayEnd.getDate() + 1)

  const startsAt = new Date(event.starts_at)
  if (!event.ends_at) return dateKey(startsAt) === dateKey(date)

  const endsAt = new Date(event.ends_at)
  return startsAt < dayEnd && endsAt > dayStart
}

function eventTime(event: EventItem, date = new Date(event.starts_at)) {
  const timeFormatter = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })
  const startsAt = new Date(event.starts_at)
  if (!event.ends_at) return timeFormatter.format(startsAt)

  const endsAt = new Date(event.ends_at)
  const startDay = dateKey(startsAt)
  const endDay = dateKey(endsAt)
  const currentDay = dateKey(date)

  if (startDay === endDay) return `${timeFormatter.format(startsAt)} – ${timeFormatter.format(endsAt)}`
  if (currentDay === startDay) {
    return `${timeFormatter.format(startsAt)} → ${shortDateFormatter.format(endsAt)} ${timeFormatter.format(endsAt)}`
  }
  if (currentDay === endDay) return `Fin ${timeFormatter.format(endsAt)}`
  return 'Suite'
}

function formatDay(date: Date) {
  return dateFormatter.format(date)
}

function movePeriod(amount: number) {
  const next = new Date(cursor.value)
  if (view.value === 'year') next.setFullYear(next.getFullYear() + amount)
  else if (view.value === 'month' || view.value === 'agenda') next.setMonth(next.getMonth() + amount)
  else if (view.value === 'week') next.setDate(next.getDate() + amount * 7)
  else next.setDate(next.getDate() + amount)
  cursor.value = next
}

function goToToday() {
  cursor.value = new Date()
}

function toLocalDateTime(value: string) {
  const date = new Date(value)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}

function openEditor(date = cursor.value, event?: EventItem) {
  if (!canManageEvents.value) return
  editingEvent.value = event ?? null
  form.title = event?.title ?? ''
  form.description = event?.description ?? ''
  form.color = event?.color ?? '#58ad7b'
  form.starts_at = event ? toLocalDateTime(event.starts_at) : `${dateKey(date)}T09:00`
  form.ends_at = event?.ends_at ? toLocalDateTime(event.ends_at) : ''
  actionError.value = ''
  editorOpen.value = true
}

function closeEditor() {
  if (saving.value || deleting.value) return
  editorOpen.value = false
  editingEvent.value = null
}

function isUnauthorized(cause: unknown) {
  if (typeof cause !== 'object' || cause === null) return false
  return ('status' in cause && cause.status === 401)
    || ('statusCode' in cause && cause.statusCode === 401)
}

async function loadEvents() {
  loading.value = true
  loadError.value = ''
  authRequired.value = false
  try {
    events.value = await $fetch<EventItem[]>('/api/agenda/events', { credentials: 'include' })
  } catch (cause) {
    events.value = []
    authRequired.value = isUnauthorized(cause)
    loadError.value = authRequired.value
      ? 'Connectez-vous pour consulter l’agenda partagé.'
      : 'Les événements ne sont pas disponibles pour le moment.'
  } finally {
    loading.value = false
  }
}

async function saveEvent() {
  if (!canManageEvents.value) return
  actionError.value = ''
  if (!form.title.trim() || !form.starts_at) {
    actionError.value = 'Renseignez un titre et une date de début.'
    return
  }
  if (form.ends_at && new Date(form.ends_at) < new Date(form.starts_at)) {
    actionError.value = 'La fin doit être après le début.'
    return
  }

  saving.value = true
  const body = {
    title: form.title.trim(),
    description: form.description.trim() || null,
    color: form.color,
    starts_at: new Date(form.starts_at).toISOString(),
    ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null
  }

  try {
    if (editingEvent.value) {
      await $fetch(`/api/agenda/events/${editingEvent.value.id}`, {
        method: 'PATCH',
        credentials: 'include',
        body
      })
    } else {
      await $fetch('/api/agenda/events', {
        method: 'POST',
        credentials: 'include',
        body
      })
    }
    editorOpen.value = false
    editingEvent.value = null
    await loadEvents()
  } catch {
    actionError.value = 'Enregistrement impossible. Vérifiez votre connexion puis réessayez.'
  } finally {
    saving.value = false
  }
}

async function removeEvent(event: EventItem) {
  if (!canManageEvents.value) return
  if (!window.confirm(`Supprimer « ${event.title} » de l’agenda ?`)) return
  actionError.value = ''
  deleting.value = true
  try {
    await $fetch(`/api/agenda/events/${event.id}`, {
      method: 'DELETE',
      credentials: 'include'
    })
    if (editingEvent.value?.id === event.id) {
      editorOpen.value = false
      editingEvent.value = null
    }
    await loadEvents()
  } catch {
    actionError.value = 'Suppression impossible. Veuillez réessayer.'
  } finally {
    deleting.value = false
  }
}

function eventsInMonth(year: number, month: number) {
  const firstDay = new Date(year, month, 1)
  const firstDayOfNextMonth = new Date(year, month + 1, 1)
  return visibleEvents.value.filter(event => {
    const startsAt = new Date(event.starts_at)
    if (!event.ends_at) return startsAt >= firstDay && startsAt < firstDayOfNextMonth
    const endsAt = new Date(event.ends_at)
    return startsAt < firstDayOfNextMonth && endsAt > firstDay
  })
}

const yearMonths = computed(() => {
  const year = cursor.value.getFullYear()

  return Array.from({ length: 12 }, (_, month) => {
    const firstDay = new Date(year, month, 1)
    const leadingDays = (firstDay.getDay() + 6) % 7
    const dayCount = new Date(year, month + 1, 0).getDate()
    const days = Array.from({ length: 42 }, (_, index) => {
      const day = index - leadingDays + 1
      if (day < 1 || day > dayCount) return null

      const date = new Date(year, month, day)
      const dayEvents = eventsFor(date)
      const titles = dayEvents.slice(0, 3).map(event => event.title).join(', ')
      const remaining = dayEvents.length > 3 ? ` et ${dayEvents.length - 3} autre(s)` : ''

      return {
        day,
        date,
        eventCount: dayEvents.length,
        label: dayEvents.length
          ? `${formatDay(date)} · ${dayEvents.length} événement${dayEvents.length > 1 ? 's' : ''} : ${titles}${remaining}`
          : formatDay(date)
      }
    })

    return {
      name: yearMonthFormatter.format(firstDay),
      days,
      eventCount: eventsInMonth(year, month).length
    }
  })
})

function openMonth(month: number) {
  cursor.value = new Date(cursor.value.getFullYear(), month, 1)
  view.value = 'month'
}

function onKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape' && editorOpen.value) closeEditor()
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  loadEvents()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <main class="agenda-page">
    <header class="agenda-header">
      <div class="agenda-heading">
        <div class="agenda-heading__icon">
          <Icon name="lucide:calendar-days" size="19" />
        </div>
        <div>
          <p class="agenda-heading__eyebrow">BCES · ORGANISATION</p>
          <h1>Agenda partagé</h1>
        </div>
      </div>
      <div class="agenda-header__actions">
        <span class="agenda-header__status">
          <span :class="{ 'is-loading': loading, 'is-error': loadError }"></span>
          {{ loading ? 'Synchronisation…' : loadError ? 'Indisponible' : 'À jour' }}
        </span>
        <button v-if="canManageEvents" class="agenda-create agenda-create--header" type="button" @click="openEditor()">
          <Icon name="lucide:plus" size="17" />
          <span class="agenda-create__label">Créer un événement</span>
        </button>
      </div>
    </header>

    <div class="agenda-workspace">
      <aside class="agenda-sidebar">
        <button v-if="canManageEvents" class="agenda-create agenda-create--side" type="button" @click="openEditor()">
          <Icon name="lucide:plus" size="19" />
          <span>Créer un événement</span>
        </button>

        <section class="mini-calendar" aria-label="Calendrier mensuel">
          <div class="mini-calendar__header">
            <button type="button" aria-label="Mois précédent" @click="movePeriod(-1)">
              <Icon name="lucide:chevron-left" size="16" />
            </button>
            <strong>{{ monthLabel }}</strong>
            <button type="button" aria-label="Mois suivant" @click="movePeriod(1)">
              <Icon name="lucide:chevron-right" size="16" />
            </button>
          </div>
          <div class="mini-calendar__grid">
            <span v-for="name in dayNames" :key="name" class="mini-calendar__weekday">
              {{ name.slice(0, 1) }}
            </span>
            <button
              v-for="date in monthDays"
              :key="`mini-${dateKey(date)}`"
              type="button"
              :class="{
                'is-muted': date.getMonth() !== cursor.getMonth(),
                'is-today': dateKey(date) === todayKey,
                'is-selected': dateKey(date) === dateKey(cursor)
              }"
              :aria-label="miniDayLabel(date)"
              :title="miniDayLabel(date)"
              @click="cursor = date; view = 'day'"
            >
              {{ date.getDate() }}
              <span
                v-if="eventsFor(date).length"
                class="mini-calendar__event-indicator"
                :class="{ 'has-multiple': eventsFor(date).length > 1 }"
                aria-hidden="true"
              ></span>
            </button>
          </div>
        </section>

        <section class="agenda-calendars">
          <p class="agenda-sidebar__label">MES AGENDAS</p>
          <label class="agenda-calendar-toggle">
            <input v-model="calendarEnabled" type="checkbox">
            <span class="agenda-calendar-toggle__swatch"></span>
            <span>Agenda partagé</span>
            <Icon v-if="calendarEnabled" name="lucide:check" size="13" />
          </label>
        </section>

        <section class="agenda-sidebar__summary">
          <span class="agenda-sidebar__summary-icon">
            <Icon name="lucide:calendar-check-2" size="16" />
          </span>
          <p><strong>{{ upcomingEvents.length }}</strong> événement{{ upcomingEvents.length > 1 ? 's' : '' }} à venir</p>
        </section>
      </aside>

      <section class="agenda-main" aria-label="Calendrier partagé">
        <div class="agenda-toolbar">
          <div class="agenda-toolbar__period">
            <div class="agenda-toolbar__navigation">
              <button type="button" aria-label="Période précédente" @click="movePeriod(-1)">
                <Icon name="lucide:chevron-left" size="18" />
              </button>
              <button type="button" class="agenda-today" @click="goToToday">Aujourd’hui</button>
              <button type="button" aria-label="Période suivante" @click="movePeriod(1)">
                <Icon name="lucide:chevron-right" size="18" />
              </button>
            </div>
            <h2>{{ periodLabel }}</h2>
          </div>
          <div class="agenda-view-switch" role="group" aria-label="Choisir l’affichage">
            <button
              v-for="option in views"
              :key="option.value"
              type="button"
              :class="{ 'is-active': view === option.value }"
              :aria-pressed="view === option.value"
              @click="view = option.value"
            >
              <Icon :name="option.icon" size="15" />
              <span>{{ option.label }}</span>
            </button>
          </div>
        </div>

        <div v-if="loadError" class="agenda-notice" :class="{ 'agenda-notice--auth': authRequired }" role="alert">
          <span class="agenda-notice__icon">
            <Icon :name="authRequired ? 'lucide:lock-keyhole' : 'lucide:cloud-off'" size="19" />
          </span>
          <div>
            <strong>{{ authRequired ? 'Connexion requise' : 'Agenda momentanément indisponible' }}</strong>
            <p>{{ loadError }}</p>
          </div>
          <NuxtLink v-if="authRequired" to="/" class="agenda-notice__link">Se connecter</NuxtLink>
          <button v-else type="button" class="agenda-notice__link" @click="loadEvents">Réessayer</button>
        </div>

        <div v-if="actionError" class="agenda-action-error" role="alert">
          <Icon name="lucide:circle-alert" size="16" />
          <span>{{ actionError }}</span>
          <button type="button" aria-label="Fermer le message" @click="actionError = ''">
            <Icon name="lucide:x" size="15" />
          </button>
        </div>

        <div v-if="loading && !events.length" class="agenda-loading">
          <span class="agenda-spinner"></span>
          <p>Chargement de l’agenda…</p>
        </div>
        <div v-else-if="view === 'month'" class="month-calendar">
          <div class="month-calendar__weekdays">
            <span v-for="name in dayNames" :key="name">{{ name }}</span>
          </div>
          <div
            class="month-calendar__days"
            :style="{ '--week-count': monthDays.length / 7 }"
          >
            <section
              v-for="date in monthDays"
              :key="dateKey(date)"
              class="month-day"
              :class="{
                'is-outside': date.getMonth() !== cursor.getMonth(),
                'is-today': dateKey(date) === todayKey
              }"
            >
              <button v-if="canManageEvents" class="month-day__number" type="button" @click="openEditor(date)">
                <span>{{ date.getDate() }}</span>
                <Icon name="lucide:plus" size="14" />
              </button>
              <span v-else class="month-day__number"><span>{{ date.getDate() }}</span></span>
              <div class="month-day__events">
                <component
                  :is="canManageEvents ? 'button' : 'div'"
                  v-for="event in eventsFor(date).slice(0, 3)"
                  :key="event.id"
                  type="button"
                  class="month-event"
                  :style="{ '--event-color': event.color || '#58ad7b' }"
                  :title="`${formatDay(date)} · ${eventTime(event, date)} · ${event.title} — modifier`"
                  @click="canManageEvents && openEditor(date, event)"
                >
                  <time>{{ eventTime(event, date) }}</time>
                  <span>{{ event.title }}</span>
                </component>
                <span v-if="eventsFor(date).length > 3" class="month-day__more">
                  + {{ eventsFor(date).length - 3 }} autre{{ eventsFor(date).length > 4 ? 's' : '' }}
                </span>
              </div>
            </section>
          </div>
        </div>

        <div v-else-if="view === 'year'" class="year-calendar">
          <button
            v-for="(month, monthIndex) in yearMonths"
            :key="month.name"
            type="button"
            class="year-month"
            :aria-label="`Afficher ${month.name} ${cursor.getFullYear()}, ${month.eventCount ? month.eventCount + ' événement' + (month.eventCount > 1 ? 's' : '') : 'aucun événement'}`"
            @click="openMonth(monthIndex)"
          >
            <span class="year-month__heading">
              <strong>{{ month.name }}</strong>
              <span class="year-month__count">
                {{ month.eventCount || 'Aucun' }}
                événement{{ month.eventCount > 1 ? 's' : '' }}
              </span>
            </span>
            <span class="year-month__weekdays" aria-hidden="true">
              <span v-for="name in dayNames" :key="name">{{ name.slice(0, 1) }}</span>
            </span>
            <span class="year-month__days" aria-hidden="true">
              <span
                v-for="(day, index) in month.days"
                :key="index"
                class="year-month__day"
                :class="{
                  'has-event': !!day?.eventCount,
                  'is-today': day && dateKey(day.date) === todayKey
                }"
                :title="day?.label"
              >
                {{ day?.day ?? '' }}
                <i v-if="day?.eventCount"></i>
              </span>
            </span>
            <Icon name="lucide:arrow-up-right" size="14" class="year-month__arrow" />
          </button>
        </div>

        <div v-else-if="view === 'agenda'" class="upcoming-list">
          <div v-if="!agendaDays.length && !loading" class="agenda-empty">
            <span><Icon name="lucide:calendar-heart" size="24" /></span>
            <h3>Aucun événement à venir</h3>
            <p>Les prochains rendez-vous apparaîtront ici.</p>
            <button v-if="canManageEvents" class="agenda-create" type="button" @click="openEditor()">
              <Icon name="lucide:plus" size="17" /> Créer un événement
            </button>
          </div>
          <section v-for="group in agendaDays" :key="dateKey(group.date)" class="upcoming-day">
            <div class="upcoming-day__date">
              <strong>{{ group.date.getDate() }}</strong>
              <span>{{ new Intl.DateTimeFormat('fr-FR', { weekday: 'short', month: 'long' }).format(group.date) }}</span>
            </div>
            <div class="upcoming-day__events">
              <article v-for="event in group.events" :key="event.id" class="event-card" :style="{ '--event-color': event.color || '#58ad7b' }">
                <span class="event-card__accent"></span>
                <time>{{ eventTime(event, group.date) }}</time>
                <div class="event-card__content">
                  <h3>{{ event.title }}</h3>
                  <p v-if="event.description">{{ event.description }}</p>
                </div>
                <button v-if="canManageEvents" type="button" :aria-label="`Modifier ${event.title}`" @click="openEditor(group.date, event)">
                  <Icon name="lucide:pencil" size="16" />
                </button>
                <button v-if="canManageEvents" type="button" :aria-label="`Supprimer ${event.title}`" @click="removeEvent(event)">
                  <Icon name="lucide:trash-2" size="16" />
                </button>
              </article>
            </div>
          </section>
        </div>

        <div v-else class="week-calendar" :class="{ 'week-calendar--day': view === 'day' }">
          <section
            v-for="date in view === 'week' ? weekDays : [cursor]"
            :key="dateKey(date)"
            class="week-day"
            :class="{ 'is-today': dateKey(date) === todayKey }"
          >
            <header class="week-day__header">
              <span>{{ new Intl.DateTimeFormat('fr-FR', { weekday: 'short' }).format(date) }}</span>
              <strong>{{ date.getDate() }}</strong>
            </header>
            <div class="week-day__events">
              <article
                v-for="event in eventsFor(date)"
                :key="event.id"
                class="event-card"
                :style="{ '--event-color': event.color || '#58ad7b' }"
              >
                <time>{{ eventTime(event, date) }}</time>
                <div class="event-card__content">
                  <h3>{{ event.title }}</h3>
                  <p v-if="event.description">{{ event.description }}</p>
                </div>
                <button v-if="canManageEvents" type="button" :aria-label="`Modifier ${event.title}`" @click="openEditor(date, event)">
                  <Icon name="lucide:pencil" size="15" />
                </button>
                <button v-if="canManageEvents" type="button" :aria-label="`Supprimer ${event.title}`" @click="removeEvent(event)">
                  <Icon name="lucide:trash-2" size="15" />
                </button>
              </article>
              <button v-if="canManageEvents && !eventsFor(date).length" type="button" class="week-day__empty" @click="openEditor(date)">
                <Icon name="lucide:plus" size="15" />
                Ajouter un événement
              </button>
            </div>
          </section>
        </div>
      </section>
    </div>

    <div v-if="editorOpen" class="agenda-modal" @click.self="closeEditor">
      <form class="agenda-dialog" @submit.prevent="saveEvent">
        <header class="agenda-dialog__header">
          <div>
            <span class="agenda-dialog__eyebrow">{{ editingEvent ? 'MODIFIER' : 'NOUVEL' }} ÉVÉNEMENT</span>
            <h2>{{ editingEvent ? 'Modifier le rendez-vous' : 'Créer un événement' }}</h2>
          </div>
          <button type="button" aria-label="Fermer" @click="closeEditor">
            <Icon name="lucide:x" size="19" />
          </button>
        </header>
        <label class="agenda-field">
          <span>Titre <i>*</i></span>
          <input v-model="form.title" required maxlength="120" autofocus placeholder="Ex. Réunion d’équipe" />
        </label>
        <div class="agenda-dialog__dates">
          <label class="agenda-field">
            <span>Début <i>*</i></span>
            <input v-model="form.starts_at" type="datetime-local" required />
          </label>
          <label class="agenda-field">
            <span>Fin</span>
            <input v-model="form.ends_at" type="datetime-local" />
          </label>
        </div>
        <label class="agenda-field">
          <span>Description</span>
          <textarea v-model="form.description" rows="3" placeholder="Ajoutez des informations utiles…"></textarea>
        </label>
        <label class="agenda-field agenda-field--color">
          <span>Couleur de l’événement</span>
          <input v-model="form.color" type="color" aria-label="Couleur de l’événement" />
        </label>
        <p v-if="actionError" class="agenda-dialog__error" role="alert">{{ actionError }}</p>
        <footer class="agenda-dialog__footer">
          <button
            v-if="editingEvent"
            type="button"
            class="agenda-button agenda-button--danger"
            :disabled="saving || deleting"
            @click="removeEvent(editingEvent)"
          >
            <Icon v-if="deleting" name="lucide:loader-circle" size="15" class="is-spinning" />
            <Icon v-else name="lucide:trash-2" size="15" />
            {{ deleting ? 'Suppression…' : 'Supprimer' }}
          </button>
          <span class="agenda-dialog__footer-spacer"></span>
          <button type="button" class="agenda-button agenda-button--quiet" :disabled="saving || deleting" @click="closeEditor">Annuler</button>
          <button type="submit" class="agenda-button agenda-button--primary" :disabled="saving || deleting">
            <Icon v-if="saving" name="lucide:loader-circle" size="16" class="is-spinning" />
            {{ saving ? 'Enregistrement…' : editingEvent ? 'Enregistrer' : 'Créer l’événement' }}
          </button>
        </footer>
      </form>
    </div>
  </main>
</template>

<style scoped>
.agenda-page {
  --agenda-bg: #101419;
  --agenda-surface: #171d23;
  --agenda-surface-raised: #1c232a;
  --agenda-border: #29323b;
  --agenda-text: #e6edf2;
  --agenda-muted: #93a0ab;
  --agenda-dim: #64717d;
  --agenda-accent: #65bd89;

  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  color: var(--agenda-text);
  background: var(--agenda-bg);
}

.agenda-header {
  display: flex;
  flex: 0 0 72px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 30px;
  border-bottom: 1px solid var(--agenda-border);
  background: var(--agenda-surface);
}

.agenda-heading,
.agenda-header__actions {
  display: flex;
  align-items: center;
}

.agenda-heading { gap: 13px; }
.agenda-heading__icon { display: grid; width: 38px; height: 38px; place-items: center; border: 1px solid rgba(101, 189, 137, .2); border-radius: 11px; color: var(--agenda-accent); background: rgba(101, 189, 137, .1); }
.agenda-heading__eyebrow { margin: 0 0 2px; color: var(--agenda-dim); font-size: 9px; font-weight: 750; letter-spacing: .14em; }
.agenda-heading h1 { font-size: 18px; font-weight: 650; letter-spacing: -.025em; }
.agenda-header__actions { gap: 20px; }
.agenda-header__status { display: flex; align-items: center; gap: 8px; color: var(--agenda-muted); font-size: 11px; }
.agenda-header__status > span { width: 7px; height: 7px; border-radius: 50%; background: var(--agenda-accent); box-shadow: 0 0 10px rgba(101, 189, 137, .4); }
.agenda-header__status > span.is-loading { background: #d3a85e; box-shadow: 0 0 10px rgba(211, 168, 94, .35); }
.agenda-header__status > span.is-error { background: #e27872; box-shadow: 0 0 10px rgba(226, 120, 114, .3); }

.agenda-create {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 40px;
  padding: 0 15px;
  border: 1px solid rgba(101, 189, 137, .3);
  border-radius: 8px;
  color: #dff3e6;
  background: #234634;
  font-size: 12px;
  font-weight: 650;
  transition: background .15s ease, border-color .15s ease, transform .15s ease;
}

.agenda-create:hover { transform: translateY(-1px); border-color: rgba(101, 189, 137, .55); background: #2b5940; }
.agenda-create--side { width: 100%; justify-content: flex-start; margin-bottom: 22px; background: var(--agenda-surface-raised); }
.agenda-create--header { min-height: 36px; }

.agenda-workspace {
  display: grid;
  flex: 1;
  grid-template-columns: 248px minmax(0, 1fr);
  gap: 20px;
  min-height: 0;
  padding: 20px 24px 24px;
}

.agenda-sidebar { min-width: 0; padding: 2px 3px 0 2px; }
.mini-calendar { padding: 13px 10px 11px; border: 1px solid var(--agenda-border); border-radius: 10px; background: var(--agenda-surface); }
.mini-calendar__header { display: flex; align-items: center; justify-content: space-between; gap: 5px; padding: 0 2px 11px; }
.mini-calendar__header strong { color: var(--agenda-text); font-size: 12px; font-weight: 650; text-transform: capitalize; }
.mini-calendar__header button { display: grid; width: 25px; height: 25px; place-items: center; border-radius: 6px; color: var(--agenda-muted); }
.mini-calendar__header button:hover { color: var(--agenda-text); background: var(--agenda-surface-raised); }
.mini-calendar__grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); justify-items: center; gap: 3px 1px; }
.mini-calendar__weekday { display: grid; width: 27px; height: 23px; place-items: center; color: var(--agenda-dim); font-size: 9px; font-weight: 700; text-transform: uppercase; }
.mini-calendar__grid button { display: grid; width: 27px; height: 27px; place-items: center; border-radius: 50%; color: var(--agenda-muted); font-size: 10px; }
.mini-calendar__grid button { position: relative; }
.mini-calendar__event-indicator { position: absolute; right: 3px; bottom: 3px; width: 4px; height: 4px; border-radius: 50%; background: var(--agenda-accent); }
.mini-calendar__event-indicator.has-multiple { width: 6px; height: 6px; box-shadow: 0 0 0 1px var(--agenda-surface); }
.mini-calendar__grid button:hover { color: var(--agenda-accent); background: rgba(101, 189, 137, .1); }
.mini-calendar__grid button.is-muted { color: #4e5a65; }
.mini-calendar__grid button.is-today { color: #0c1710; background: var(--agenda-accent); font-weight: 750; }
.mini-calendar__grid button.is-selected:not(.is-today) { outline: 1px solid var(--agenda-accent); outline-offset: -2px; color: var(--agenda-accent); }

.agenda-calendars { margin-top: 28px; }
.agenda-sidebar__label { margin: 0 0 11px 8px; color: var(--agenda-dim); font-size: 9px; font-weight: 750; letter-spacing: .13em; }
.agenda-calendar-toggle { display: flex; align-items: center; gap: 10px; min-height: 38px; padding: 0 9px; border-radius: 7px; color: var(--agenda-muted); font-size: 12px; cursor: pointer; }
.agenda-calendar-toggle:hover { background: rgba(255, 255, 255, .035); }
.agenda-calendar-toggle input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.agenda-calendar-toggle input:focus-visible + .agenda-calendar-toggle__swatch { outline: 2px solid var(--agenda-text); outline-offset: 2px; }
.agenda-calendar-toggle__swatch { width: 11px; height: 11px; flex: 0 0 11px; border: 1px solid var(--agenda-accent); border-radius: 3px; background: var(--agenda-accent); }
.agenda-calendar-toggle input:not(:checked) + .agenda-calendar-toggle__swatch { background: transparent; }
.agenda-calendar-toggle > span:nth-of-type(2) { flex: 1; }
.agenda-calendar-toggle > svg { color: var(--agenda-accent); }
.agenda-sidebar__summary { display: flex; align-items: center; gap: 10px; margin-top: 25px; padding: 13px 10px; border-top: 1px solid var(--agenda-border); }
.agenda-sidebar__summary-icon { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 8px; color: var(--agenda-accent); background: rgba(101, 189, 137, .1); }
.agenda-sidebar__summary p { color: var(--agenda-muted); font-size: 11px; }
.agenda-sidebar__summary strong { color: var(--agenda-text); font-weight: 700; }

.agenda-main { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; border: 1px solid var(--agenda-border); border-radius: 11px; background: var(--agenda-surface); }
.agenda-toolbar { display: flex; flex: 0 0 auto; align-items: center; justify-content: space-between; gap: 16px; min-height: 64px; padding: 10px 16px; border-bottom: 1px solid var(--agenda-border); }
.agenda-toolbar__period { display: flex; align-items: center; gap: 15px; min-width: 0; }
.agenda-toolbar__navigation { display: flex; align-items: center; gap: 5px; flex: 0 0 auto; }
.agenda-toolbar__navigation > button:not(.agenda-today) { display: grid; width: 31px; height: 31px; place-items: center; border-radius: 6px; color: var(--agenda-muted); }
.agenda-toolbar__navigation > button:not(.agenda-today):hover { color: var(--agenda-text); background: var(--agenda-surface-raised); }
.agenda-today { min-height: 30px; padding: 0 10px; border: 1px solid var(--agenda-border); border-radius: 6px; color: var(--agenda-text); font-size: 11px; font-weight: 600; }
.agenda-today:hover { border-color: #45515b; background: var(--agenda-surface-raised); }
.agenda-toolbar h2 { overflow: hidden; color: var(--agenda-text); font-size: 16px; font-weight: 600; text-overflow: ellipsis; text-transform: capitalize; white-space: nowrap; }
.agenda-view-switch { display: flex; align-items: center; gap: 3px; padding: 3px; border: 1px solid var(--agenda-border); border-radius: 8px; background: var(--agenda-bg); }
.agenda-view-switch button { display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 30px; padding: 0 9px; border: 1px solid transparent; border-radius: 5px; color: var(--agenda-muted); font-size: 10px; font-weight: 550; white-space: nowrap; }
.agenda-view-switch button:hover { color: var(--agenda-text); }
.agenda-view-switch button.is-active { border-color: rgba(101, 189, 137, .23); color: #c3edd1; background: rgba(101, 189, 137, .13); }

.agenda-notice { display: flex; align-items: center; gap: 12px; margin: 16px 18px 0; padding: 13px 15px; border: 1px solid rgba(211, 168, 94, .25); border-radius: 8px; background: rgba(211, 168, 94, .07); }
.agenda-notice--auth { border-color: rgba(101, 189, 137, .24); background: rgba(101, 189, 137, .06); }
.agenda-notice__icon { display: grid; width: 34px; height: 34px; flex: 0 0 34px; place-items: center; border-radius: 8px; color: #d3a85e; background: rgba(211, 168, 94, .1); }
.agenda-notice--auth .agenda-notice__icon { color: var(--agenda-accent); background: rgba(101, 189, 137, .1); }
.agenda-notice strong { color: var(--agenda-text); font-size: 12px; }
.agenda-notice p { margin-top: 3px; color: var(--agenda-muted); font-size: 11px; }
.agenda-notice__link { margin-left: auto; color: var(--agenda-accent); font-size: 11px; font-weight: 650; white-space: nowrap; }
.agenda-notice__link:hover { color: #a0e2b6; }
.agenda-action-error { display: flex; align-items: center; gap: 9px; margin: 12px 18px 0; padding: 10px 12px; border: 1px solid rgba(226, 120, 114, .24); border-radius: 7px; color: #f0a29d; background: rgba(226, 120, 114, .08); font-size: 11px; }
.agenda-action-error span { flex: 1; }
.agenda-action-error button { display: grid; place-items: center; color: inherit; }

.agenda-loading { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 14px; color: var(--agenda-muted); font-size: 12px; }
.agenda-spinner { width: 23px; height: 23px; border: 2px solid var(--agenda-border); border-top-color: var(--agenda-accent); border-radius: 50%; animation: agenda-spin .75s linear infinite; }
@keyframes agenda-spin { to { transform: rotate(360deg); } }
.month-calendar { display: flex; flex: 1; flex-direction: column; min-height: 0; overflow: auto; }
.month-calendar__weekdays { display: grid; flex: 0 0 39px; grid-template-columns: repeat(7, minmax(0, 1fr)); border-bottom: 1px solid var(--agenda-border); }
.month-calendar__weekdays span { display: flex; align-items: center; padding-left: 11px; color: var(--agenda-dim); font-size: 9px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.month-calendar__days { display: grid; flex: 1; grid-template-columns: repeat(7, minmax(0, 1fr)); grid-template-rows: repeat(var(--week-count), minmax(94px, 1fr)); min-height: 0; }
.month-day { min-width: 0; overflow: hidden; padding: 5px 6px 6px; border-right: 1px solid var(--agenda-border); border-bottom: 1px solid var(--agenda-border); background: #151a1f; }
.month-day:nth-child(7n) { border-right: 0; }
.month-day.is-outside { background: #12171b; }
.month-day.is-outside .month-day__number { color: #596570; }
.month-day.is-today .month-day__number > span { color: #0d1710; background: var(--agenda-accent); font-weight: 750; }
.month-day__number { display: flex; width: 100%; align-items: center; justify-content: space-between; padding: 0; color: var(--agenda-muted); font-size: 11px; }
.month-day__number > span { display: grid; width: 25px; height: 25px; place-items: center; border-radius: 50%; }
.month-day__number :deep(.iconify) { opacity: 0; color: var(--agenda-accent); transition: opacity .12s ease; }
.month-day:hover .month-day__number :deep(.iconify) { opacity: 1; }
.month-day__events { display: grid; gap: 3px; margin-top: 3px; }
.month-event { display: flex; align-items: center; gap: 5px; min-width: 0; padding: 4px 5px; border-left: 2px solid var(--event-color); border-radius: 3px; color: var(--agenda-text); background: color-mix(in srgb, var(--event-color) 12%, #1a2026); text-align: left; }
.month-event:hover { background: color-mix(in srgb, var(--event-color) 21%, #1a2026); }
.month-event time { flex: 0 0 auto; color: var(--agenda-muted); font-size: 9px; }
.month-event span { overflow: hidden; font-size: 10px; font-weight: 550; text-overflow: ellipsis; white-space: nowrap; }
.month-day__more { padding-left: 6px; color: var(--agenda-muted); font-size: 9px; }

.year-calendar { display: grid; flex: 1; grid-template-columns: repeat(auto-fit, 340px); justify-content: start; align-content: start; gap: 14px; overflow: auto; padding: 18px; }
.year-month { position: relative; display: flex; min-width: 0; flex-direction: column; gap: 12px; padding: 16px; border: 1px solid var(--agenda-border); border-radius: 10px; color: var(--agenda-text); background: #151a1f; text-align: left; transition: border-color .15s ease, background .15s ease; }
.year-month:hover { border-color: rgba(101, 189, 137, .45); background: var(--agenda-surface-raised); }
.year-month:focus-visible { outline: 2px solid var(--agenda-accent); outline-offset: 2px; }
.year-month__heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-width: 0; padding-right: 16px; }
.year-month__heading > strong { overflow: hidden; font-size: 12px; font-weight: 650; text-overflow: ellipsis; text-transform: capitalize; }
.year-month__count { flex: 0 0 auto; color: var(--agenda-muted); font-size: 9px; }
.year-month__weekdays,
.year-month__days { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 3px; }
.year-month__weekdays { color: var(--agenda-dim); font-size: 8px; font-weight: 700; text-align: center; text-transform: uppercase; }
.year-month__weekdays > span { display: grid; height: 18px; place-items: center; }
.year-month__day { position: relative; display: grid; width: 32px; height: 32px; justify-self: center; place-items: center; border-radius: 50%; color: var(--agenda-muted); font-size: 10px; font-variant-numeric: tabular-nums; }
.year-month__day.has-event { color: #c3edd1; background: rgba(101, 189, 137, .14); font-weight: 650; }
.year-month__day > i { position: absolute; bottom: 4px; width: 3px; height: 3px; border-radius: 50%; background: var(--agenda-accent); }
.year-month__day.is-today { color: #0c1710; background: var(--agenda-accent); font-weight: 750; }
.year-month__day.is-today > i { background: #0c1710; }
.year-month__arrow { position: absolute; top: 11px; right: 10px; color: var(--agenda-dim); opacity: 0; transition: opacity .15s ease; }
.year-month:hover .year-month__arrow,
.year-month:focus-visible .year-month__arrow { opacity: 1; }

.upcoming-list { flex: 1; min-height: 0; overflow: auto; padding: 16px 20px 24px; }
.upcoming-day { display: grid; grid-template-columns: 142px minmax(0, 1fr); gap: 16px; padding: 18px 0; border-bottom: 1px solid var(--agenda-border); }
.upcoming-day__date { display: flex; align-items: flex-start; gap: 10px; padding: 5px 0; }
.upcoming-day__date strong { display: grid; width: 38px; height: 38px; flex: 0 0 38px; place-items: center; border: 1px solid var(--agenda-border); border-radius: 9px; color: var(--agenda-text); background: var(--agenda-bg); font-size: 16px; }
.upcoming-day__date > span { padding-top: 3px; color: var(--agenda-muted); font-size: 10px; text-transform: capitalize; }
.upcoming-day__events { display: grid; gap: 8px; }
.event-card { display: flex; align-items: flex-start; gap: 13px; min-width: 0; padding: 12px; border: 1px solid var(--agenda-border); border-radius: 8px; background: #151a1f; }
.event-card__accent { width: 3px; min-height: 34px; flex: 0 0 3px; margin: 1px 0; border-radius: 3px; background: var(--event-color); }
.event-card > time { flex: 0 0 auto; padding-top: 2px; color: var(--agenda-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.event-card__content { flex: 1; min-width: 0; }
.event-card__content h3 { font-size: 12px; font-weight: 650; }
.event-card__content p { margin-top: 4px; color: var(--agenda-muted); font-size: 11px; line-height: 1.5; white-space: pre-wrap; }
.event-card > button { display: grid; width: 28px; height: 28px; flex: 0 0 28px; place-items: center; border-radius: 6px; color: var(--agenda-dim); }
.event-card > button:hover { color: var(--agenda-accent); background: rgba(101, 189, 137, .09); }
.event-card > button:last-child:hover { color: #e78d87; background: rgba(226, 120, 114, .09); }
.agenda-empty { display: flex; min-height: 280px; flex-direction: column; align-items: center; justify-content: center; gap: 10px; text-align: center; }
.agenda-empty > span { display: grid; width: 48px; height: 48px; place-items: center; border: 1px solid var(--agenda-border); border-radius: 14px; color: var(--agenda-accent); background: rgba(101, 189, 137, .08); }
.agenda-empty h3 { font-size: 14px; }
.agenda-empty p { margin-bottom: 5px; color: var(--agenda-muted); font-size: 11px; }

.week-calendar { display: grid; flex: 1; grid-template-columns: repeat(7, minmax(160px, 1fr)); min-height: 0; overflow: auto; }
.week-calendar--day { grid-template-columns: minmax(0, 1fr); }
.week-day { min-width: 0; border-right: 1px solid var(--agenda-border); }
.week-day__header { position: sticky; top: 0; z-index: 1; display: flex; flex-direction: column; align-items: center; gap: 5px; padding: 12px 6px; border-bottom: 1px solid var(--agenda-border); background: var(--agenda-surface); }
.week-day__header > span { color: var(--agenda-muted); font-size: 9px; font-weight: 700; text-transform: uppercase; }
.week-day__header > strong { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; font-size: 13px; }
.week-day.is-today .week-day__header > strong { color: #0d1710; background: var(--agenda-accent); }
.week-day__events { display: grid; align-content: start; gap: 8px; min-height: 140px; padding: 10px 8px; }
.week-day__events .event-card { flex-wrap: wrap; gap: 8px; padding: 9px; }
.week-day__events .event-card__accent { display: none; }
.week-day__events .event-card > time { width: 100%; color: var(--event-color); font-weight: 650; }
.week-day__events .event-card__content { flex-basis: calc(100% - 70px); }
.week-day__events .event-card > button { margin-left: auto; }
.week-day__empty { display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; border: 1px dashed var(--agenda-border); border-radius: 6px; color: var(--agenda-dim); font-size: 10px; }
.week-day__empty:hover { border-color: rgba(101, 189, 137, .4); color: var(--agenda-accent); }

.agenda-modal { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; overflow-y: auto; padding: 20px; background: rgba(5, 8, 10, .76); backdrop-filter: blur(5px); }
.agenda-dialog { width: min(510px, 100%); padding: 23px; border: 1px solid #35404b; border-radius: 12px; background: #171d23; box-shadow: 0 26px 80px rgba(0, 0, 0, .5); }
.agenda-dialog__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 15px; margin-bottom: 22px; }
.agenda-dialog__eyebrow { color: var(--agenda-accent); font-size: 9px; font-weight: 750; letter-spacing: .13em; }
.agenda-dialog__header h2 { margin-top: 5px; font-size: 17px; font-weight: 650; }
.agenda-dialog__header > button { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 6px; color: var(--agenda-muted); }
.agenda-dialog__header > button:hover { color: var(--agenda-text); background: var(--agenda-surface-raised); }
.agenda-field { display: grid; gap: 7px; margin: 14px 0; color: var(--agenda-muted); font-size: 11px; font-weight: 550; }
.agenda-field > span i { color: #e78d87; font-style: normal; }
.agenda-field input:not([type='color']), .agenda-field textarea { width: 100%; min-width: 0; padding: 10px 11px; border: 1px solid #35404b; border-radius: 6px; outline: none; color: var(--agenda-text); background: #101419; font-size: 12px; }
.agenda-field input:focus, .agenda-field textarea:focus { border-color: var(--agenda-accent); box-shadow: 0 0 0 2px rgba(101, 189, 137, .12); }
.agenda-field textarea { resize: vertical; }
.agenda-dialog__dates { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }
.agenda-field--color { grid-template-columns: 1fr auto; align-items: center; }
.agenda-field--color input { width: 37px; height: 29px; padding: 2px; border: 1px solid #35404b; border-radius: 5px; background: #101419; }
.agenda-dialog__error { margin: 10px 0 0; color: #f0a29d; font-size: 11px; }
.agenda-dialog__footer { display: flex; justify-content: flex-end; gap: 9px; margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--agenda-border); }
.agenda-button { display: inline-flex; min-height: 36px; align-items: center; justify-content: center; gap: 7px; padding: 0 13px; border: 1px solid transparent; border-radius: 6px; font-size: 11px; font-weight: 650; }
.agenda-button:disabled { cursor: wait; opacity: .65; }
.agenda-button--quiet { border-color: var(--agenda-border); color: var(--agenda-muted); }
.agenda-button--quiet:hover:not(:disabled) { color: var(--agenda-text); background: var(--agenda-surface-raised); }
.agenda-dialog__footer-spacer { flex: 1; }
.agenda-button--danger { border-color: rgba(226, 120, 114, .28); color: #e78d87; }
.agenda-button--danger:hover:not(:disabled) { border-color: rgba(226, 120, 114, .5); background: rgba(226, 120, 114, .09); }
.agenda-button--primary { border-color: #4a9b69; color: #08130b; background: var(--agenda-accent); }
.agenda-button--primary:hover:not(:disabled) { background: #81d29f; }
.is-spinning { animation: agenda-spin .75s linear infinite; }

@media (max-width: 1100px) {
  .agenda-workspace { grid-template-columns: 215px minmax(0, 1fr); gap: 14px; padding: 15px; }
  .agenda-view-switch button { padding: 0 7px; }
  .agenda-view-switch button span { display: none; }
}

@media (max-width: 760px) {
  .agenda-page { height: auto; min-height: 100%; overflow: visible; }
  .agenda-header { flex-basis: 62px; padding: 0 15px; }
  .agenda-heading { gap: 9px; }
  .agenda-heading__icon { width: 33px; height: 33px; }
  .agenda-heading__eyebrow { font-size: 8px; }
  .agenda-heading h1 { font-size: 15px; }
  .agenda-header__actions { gap: 10px; }
  .agenda-header__status { font-size: 0; }
  .agenda-header__status > span { width: 8px; height: 8px; }
  .agenda-create--header { width: 36px; min-height: 36px; padding: 0; }
  .agenda-create--header .agenda-create__label { display: none; }
  .agenda-workspace { display: flex; flex-direction: column; gap: 12px; min-height: 0; padding: 12px; }
  .agenda-sidebar { display: grid; grid-template-columns: minmax(210px, 1fr) minmax(130px, .7fr); align-items: start; gap: 10px; }
  .agenda-create--side { display: none; }
  .mini-calendar { padding: 9px; }
  .mini-calendar__header { padding-bottom: 6px; }
  .mini-calendar__grid { gap: 0; }
  .mini-calendar__weekday { width: 23px; height: 19px; }
  .mini-calendar__grid button { width: 23px; height: 23px; }
  .agenda-calendars { margin: 4px 0 0; padding: 8px; border: 1px solid var(--agenda-border); border-radius: 9px; background: var(--agenda-surface); }
  .agenda-sidebar__label { margin-left: 0; }
  .agenda-calendar-toggle { gap: 7px; padding: 0 2px; font-size: 10px; }
  .agenda-sidebar__summary { grid-column: 1 / -1; margin: 0; padding: 6px 3px; border: 0; }
  .agenda-main { min-height: 610px; overflow: visible; }
  .agenda-toolbar { flex-wrap: wrap; gap: 9px; padding: 10px; }
  .agenda-toolbar__period { width: 100%; justify-content: space-between; gap: 8px; }
  .agenda-toolbar h2 { font-size: 13px; }
  .agenda-toolbar__navigation { gap: 2px; }
  .agenda-toolbar__navigation > button:not(.agenda-today) { width: 27px; height: 28px; }
  .agenda-today { min-height: 28px; padding: 0 7px; font-size: 10px; }
  .agenda-view-switch { width: 100%; justify-content: space-between; }
  .agenda-view-switch button { flex: 1; min-width: 30px; }
  .agenda-view-switch button span { display: inline; font-size: 9px; }
  .month-calendar { min-height: 560px; overflow: visible; }
  .month-calendar__weekdays { flex-basis: 31px; }
  .month-calendar__weekdays span { justify-content: center; padding: 0; font-size: 8px; }
  .month-calendar__days { grid-template-rows: repeat(var(--week-count), minmax(75px, 1fr)); }
  .month-day { padding: 3px 2px; }
  .month-day__number { justify-content: center; }
  .month-day__number > span { width: 22px; height: 22px; font-size: 10px; }
  .month-day__number :deep(.iconify) { display: none; }
  .month-day__events { gap: 2px; margin-top: 2px; }
  .month-event { justify-content: center; padding: 3px 2px; border-left-width: 2px; }
  .month-event time { display: none; }
  .month-event span { font-size: 8px; }
  .month-day__more { padding-left: 2px; font-size: 8px; }
  .year-calendar { grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: 8px; padding: 12px; }
  .year-month { padding: 10px; gap: 8px; }
  .year-month__heading { gap: 6px; padding-right: 14px; }
  .year-month__heading > strong { font-size: 10px; }
  .year-month__count { font-size: 8px; }
  .year-month__days { gap: 1px; }
  .year-month__day { width: 26px; height: 26px; font-size: 8px; }
  .year-month__day > i { bottom: 3px; }
  .week-calendar { grid-template-columns: repeat(7, minmax(132px, 1fr)); }
  .week-calendar--day { grid-template-columns: minmax(0, 1fr); }
  .upcoming-list { padding: 8px 12px 16px; }
  .upcoming-day { grid-template-columns: 92px minmax(0, 1fr); gap: 8px; padding: 12px 0; }
  .upcoming-day__date { flex-direction: column; gap: 5px; }
  .upcoming-day__date > span { font-size: 9px; }
  .event-card { gap: 8px; padding: 9px; }
  .agenda-notice { align-items: flex-start; margin: 10px; padding: 10px; }
  .agenda-notice__icon { width: 30px; height: 30px; flex-basis: 30px; }
  .agenda-notice__link { align-self: center; }
}

@media (prefers-reduced-motion: reduce) {
  .agenda-page *, .agenda-page *::before, .agenda-page *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
</style>
