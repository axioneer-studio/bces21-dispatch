<script setup lang="ts">
import ConfirmDialog from '~/components/ConfirmDialog.vue'

interface HospitalBed {
  id: number
  room_id: number
  label: string
  patient_name: string | null
  accident: string
  arrival_date: string | null
  care_done: boolean
  police_status: PoliceStatus
  reason: string
}

/** Forces de l'ordre : non concernées, à prévenir, ou prévenues. */
type PoliceStatus = 'none' | 'to_notify' | 'notified'

const POLICE_STATUSES: { value: PoliceStatus; label: string; icon: string; tone: string }[] = [
  { value: 'none', label: 'Non', icon: 'lucide:bell-off', tone: 'is-muted' },
  { value: 'to_notify', label: 'À prévenir', icon: 'lucide:bell-ring', tone: 'is-warn' },
  { value: 'notified', label: 'Prévenues', icon: 'lucide:circle-check', tone: 'is-ok' }
]

function policeStatus(value: PoliceStatus) {
  return POLICE_STATUSES.find((status) => status.value === value) ?? POLICE_STATUSES[0]!
}

/** Valeur du menu des raisons qui ouvre la saisie libre. */
const OTHER_REASON = '__other__'

interface HospitalRoom {
  id: number
  name: string
  beds: HospitalBed[]
}

interface BedReason {
  id: number
  name: string
}

interface RoomsData {
  rooms: HospitalRoom[]
  reasons: BedReason[]
  can_manage: boolean
}

const props = defineProps<{ active: boolean }>()

const toast = useAppToast()

const rooms = ref<HospitalRoom[]>([])
const reasons = ref<BedReason[]>([])
/** Rôles « Gérer l'hôpital » : ajout et suppression des chambres, des lits et des raisons. */
const canManage = ref(false)
const loaded = ref(false)
const loadError = ref('')
/** Une seule action à la fois, pour éviter les doubles clics. */
const busy = ref(false)

const roomDialog = ref<HTMLDialogElement | null>(null)
/** Chambre renommée, ou `null` pour une nouvelle chambre. */
const editingRoom = ref<HospitalRoom | null>(null)
const roomName = ref('')
const roomError = ref('')

const patientDialog = ref<HTMLDialogElement | null>(null)
const editingBed = ref<HospitalBed | null>(null)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  patient_name: '',
  accident: '',
  arrival_date: '',
  police_status: 'none' as PoliceStatus
})
/** Raison choisie dans la liste, vide, ou `OTHER_REASON` pour une raison saisie à la main. */
const reasonChoice = ref('')
const otherReason = ref('')

const reasonsDialog = ref<HTMLDialogElement | null>(null)
const newReasonName = ref('')
const reasonError = ref('')
/** Popup de confirmation (remplace window.confirm). */
const confirmVisible = ref(false)
const confirmMessage = ref('')
let confirmResolve: ((value: boolean) => void) | null = null

async function confirm(message: string): Promise<boolean> {
  confirmMessage.value = message
  return new Promise((resolve) => {
    confirmResolve = resolve
    confirmVisible.value = true
  })
}

function onConfirm() {
  confirmVisible.value = false
  confirmResolve?.(true)
  confirmResolve = null
}

function onCancel() {
  confirmVisible.value = false
  confirmResolve?.(false)
  confirmResolve = null
}

const bedCount = computed(() => rooms.value.reduce((total, room) => total + room.beds.length, 0))
const occupiedCount = computed(() =>
  rooms.value.reduce((total, room) => total + room.beds.filter((bed) => bed.patient_name).length, 0)
)

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === 'object' && cause !== null && 'data' in cause) {
    const data = cause.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
  }
  return fallback
}

function formatDate(value: string) {
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

function today() {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** Couleur stable par raison, pour la reconnaître d'un coup d'œil. */
function reasonHue(name: string) {
  let hash = 0
  for (const char of name.toLowerCase()) hash = (hash * 31 + char.charCodeAt(0)) % 360
  return hash
}

function occupied(room: HospitalRoom) {
  return room.beds.filter((bed) => bed.patient_name).length
}

async function load() {
  try {
    const data = await $fetch<RoomsData>('/api/hospital/rooms', { credentials: 'include' })
    rooms.value = data.rooms
    reasons.value = data.reasons
    canManage.value = data.can_manage
    loadError.value = ''
  } catch (cause) {
    loadError.value = messageFromError(cause, 'Impossible de charger les chambres.')
  } finally {
    loaded.value = true
  }
}

/** Rafraîchissement en arrière-plan, sans toucher à une saisie en cours. */
function refresh() {
  if (!props.active || busy.value || saving.value) return
  if (patientDialog.value?.open || reasonsDialog.value?.open || roomDialog.value?.open) return
  void load()
}

let refreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  refreshTimer = setInterval(refresh, 10_000)
  window.addEventListener('focus', refresh)
  refresh()
})
onBeforeUnmount(() => {
  clearInterval(refreshTimer)
  window.removeEventListener('focus', refresh)
})
watch(() => props.active, (active) => {
  if (active) refresh()
})

/** Lance une action, puis recharge les chambres pour rester à jour. */
async function run(action: () => Promise<unknown>, success: string, failure: string) {
  if (busy.value) return false
  busy.value = true
  try {
    await action()
    await load()
    toast.success(success)
    return true
  } catch (cause) {
    toast.error(messageFromError(cause, failure))
    return false
  } finally {
    busy.value = false
  }
}

// --- Chambres et lits ---

function openRoomDialog(room?: HospitalRoom) {
  editingRoom.value = room ?? null
  roomName.value = room?.name ?? ''
  roomError.value = ''
  roomDialog.value?.showModal()
}

async function saveRoom() {
  const name = roomName.value.trim()
  if (!name) {
    roomError.value = 'Le nom de la chambre est obligatoire.'
    return
  }
  const room = editingRoom.value
  if (room && name === room.name) {
    roomDialog.value?.close()
    return
  }
  if (busy.value) return
  busy.value = true
  roomError.value = ''
  try {
    await $fetch(room ? `/api/hospital/rooms/${room.id}` : '/api/hospital/rooms', {
      method: room ? 'PATCH' : 'POST',
      credentials: 'include',
      body: { name }
    })
    roomDialog.value?.close()
    await load()
    toast.success(room ? 'Chambre renommée.' : `Chambre « ${name} » ajoutée.`)
  } catch (cause) {
    roomError.value = messageFromError(cause, room ? 'Impossible de renommer la chambre.' : 'Impossible d’ajouter la chambre.')
  } finally {
    busy.value = false
  }
}

async function deleteRoom(room: HospitalRoom) {
  if (!(await confirm(`Supprimer la chambre « ${room.name} » et ses ${room.beds.length} lit(s) ?`))) return
  void run(
    () => $fetch(`/api/hospital/rooms/${room.id}`, { method: 'DELETE', credentials: 'include' }),
    'Chambre supprimée.',
    'Impossible de supprimer la chambre.'
  )
}

function addBed(room: HospitalRoom) {
  void run(
    () => $fetch(`/api/hospital/rooms/${room.id}/beds`, { method: 'POST', credentials: 'include' }),
    `Lit ajouté à « ${room.name} ».`,
    'Impossible d’ajouter le lit.'
  )
}

async function deleteBed(room: HospitalRoom, bed: HospitalBed) {
  if (!(await confirm(`Supprimer le ${bed.label} de « ${room.name} » ?`))) return
  void run(
    () => $fetch(`/api/hospital/beds/${bed.id}`, { method: 'DELETE', credentials: 'include' }),
    'Lit supprimé.',
    'Impossible de supprimer le lit.'
  )
}

// --- Patients ---

function openPatientDialog(bed: HospitalBed) {
  editingBed.value = bed
  formError.value = ''
  form.patient_name = bed.patient_name ?? ''
  form.accident = bed.accident
  form.arrival_date = bed.arrival_date ?? today()
  form.police_status = bed.police_status
  const known = !bed.reason || reasons.value.some((reason) => reason.name === bed.reason)
  reasonChoice.value = known ? bed.reason : OTHER_REASON
  otherReason.value = known ? '' : bed.reason
  patientDialog.value?.showModal()
}

function closePatientDialog() {
  if (saving.value) return
  patientDialog.value?.close()
}

async function savePatient() {
  const bed = editingBed.value
  if (!bed || saving.value) return
  if (!form.patient_name.trim()) {
    formError.value = 'Le nom du patient est obligatoire.'
    return
  }
  if (!form.arrival_date) {
    formError.value = 'La date d’arrivée est obligatoire.'
    return
  }
  const reason = reasonChoice.value === OTHER_REASON ? otherReason.value.trim() : reasonChoice.value
  if (reasonChoice.value === OTHER_REASON && !reason) {
    formError.value = 'Saisissez la raison, ou choisissez-en une dans la liste.'
    return
  }
  saving.value = true
  formError.value = ''
  const wasFree = !bed.patient_name
  try {
    await $fetch(`/api/hospital/beds/${bed.id}/patient`, {
      method: 'PUT',
      credentials: 'include',
      body: { ...form, reason }
    })
    patientDialog.value?.close()
    await load()
    toast.success(wasFree ? 'Patient affecté au lit.' : 'Fiche du patient mise à jour.')
  } catch (cause) {
    formError.value = messageFromError(cause, 'Impossible d’enregistrer ce patient.')
  } finally {
    saving.value = false
  }
}

/** Soins : faits ou non. Forces de l'ordre : passe à l'état suivant (Non → À prévenir → Prévenues). */
function toggleFlag(bed: HospitalBed, field: 'care_done' | 'police_status') {
  const index = POLICE_STATUSES.findIndex((status) => status.value === bed.police_status)
  const body = field === 'care_done'
    ? { care_done: !bed.care_done }
    : { police_status: POLICE_STATUSES[(index + 1) % POLICE_STATUSES.length]!.value }
  void run(
    () => $fetch(`/api/hospital/beds/${bed.id}/flags`, {
      method: 'PATCH',
      credentials: 'include',
      body
    }),
    'Lit mis à jour.',
    'Impossible de mettre à jour ce lit.'
  )
}

async function releaseBed(bed: HospitalBed) {
  if (!(await confirm(`Libérer le ${bed.label} occupé par « ${bed.patient_name} » ?`))) return
  void run(
    () => $fetch(`/api/hospital/beds/${bed.id}/patient`, { method: 'DELETE', credentials: 'include' }),
    'Lit libéré.',
    'Impossible de libérer ce lit.'
  )
}

// --- Raisons proposées ---

async function addReason() {
  const name = newReasonName.value.trim()
  if (!name) {
    reasonError.value = 'Saisissez une raison.'
    return
  }
  reasonError.value = ''
  const done = await run(
    () => $fetch('/api/hospital/bed-reasons', { method: 'POST', credentials: 'include', body: { name } }),
    `Raison « ${name} » ajoutée.`,
    'Impossible d’ajouter la raison.'
  )
  if (done) newReasonName.value = ''
}

function deleteReason(reason: BedReason) {
  void run(
    () => $fetch(`/api/hospital/bed-reasons/${reason.id}`, { method: 'DELETE', credentials: 'include' }),
    'Raison supprimée.',
    'Impossible de supprimer la raison.'
  )
}
</script>

<template>
  <div class="rooms">
    <div class="rooms__toolbar">
      <div class="rooms__counts" aria-label="Résumé des chambres">
        <span class="rooms__count"><Icon name="lucide:door-closed" size="15" /><strong>{{ rooms.length }}</strong> chambre{{ rooms.length > 1 ? 's' : '' }}</span>
        <span class="rooms__count"><Icon name="lucide:bed-double" size="15" /><strong>{{ occupiedCount }}</strong>/ {{ bedCount }} lits occupés</span>
      </div>
      <div v-if="canManage" class="rooms__manage">
        <button type="button" class="rooms-button" @click="reasonError = ''; reasonsDialog?.showModal()">
          <Icon name="lucide:list" size="14" /> Raisons
        </button>
        <button type="button" class="rooms-button rooms-button--primary" @click="openRoomDialog()">
          <Icon name="lucide:plus" size="15" /> Ajouter une chambre
        </button>
      </div>
    </div>

    <div v-if="loadError" class="rooms__error" role="alert">
      <Icon name="lucide:circle-alert" size="16" /><span>{{ loadError }}</span>
    </div>

    <section v-for="room in rooms" :key="room.id" class="room" :aria-labelledby="`room-title-${room.id}`">
      <header class="room__head">
        <h3 :id="`room-title-${room.id}`"><Icon name="lucide:door-closed" size="16" /> {{ room.name }}</h3>
        <span class="room__occupancy">{{ occupied(room) }} / {{ room.beds.length }} occupé{{ occupied(room) > 1 ? 's' : '' }}</span>
        <div v-if="canManage" class="room__actions">
          <button type="button" class="rooms-button" :disabled="busy" @click="addBed(room)"><Icon name="lucide:plus" size="13" /> Lit</button>
          <button type="button" class="rooms-button" :disabled="busy" @click="openRoomDialog(room)"><Icon name="lucide:pencil" size="13" /> Renommer</button>
          <button type="button" class="rooms-button rooms-button--danger" :disabled="busy" aria-label="Supprimer la chambre" title="Supprimer la chambre" @click="deleteRoom(room)"><Icon name="lucide:trash-2" size="13" /></button>
        </div>
      </header>

      <div v-if="room.beds.length" class="room__beds">
        <article
          v-for="bed in room.beds"
          :key="bed.id"
          class="bed"
          :class="bed.patient_name ? 'bed--occupied' : 'bed--free'"
        >
          <header class="bed__head">
            <span class="bed__label"><Icon name="lucide:bed-single" size="13" /> {{ bed.label }}</span>
            <time v-if="bed.arrival_date" :datetime="bed.arrival_date" title="Date d’arrivée">{{ formatDate(bed.arrival_date) }}</time>
            <span v-else class="bed__free">Libre</span>
          </header>

          <template v-if="bed.patient_name">
            <h4 class="bed__patient">{{ bed.patient_name }}</h4>
            <span
              v-if="bed.reason"
              class="bed__reason"
              :style="{ '--reason-hue': reasonHue(bed.reason) }"
            >{{ bed.reason }}</span>
            <span v-else class="bed__reason bed__reason--none">Raison non précisée</span>

            <dl class="bed__rows">
              <dt><Icon name="lucide:siren" size="12" /> Accident</dt>
              <dd class="bed__text">{{ bed.accident || '—' }}</dd>

              <dt><Icon name="lucide:heart-pulse" size="12" /> Soins</dt>
              <dd>
                <button
                  type="button"
                  class="bed__badge bed__toggle"
                  :class="bed.care_done ? 'is-ok' : 'is-ko'"
                  :aria-pressed="bed.care_done"
                  :disabled="busy"
                  title="Cliquer pour changer"
                  @click="toggleFlag(bed, 'care_done')"
                >
                  <Icon :name="bed.care_done ? 'lucide:circle-check' : 'lucide:circle-dashed'" size="12" />
                  {{ bed.care_done ? 'Faits' : 'Non faits' }}
                </button>
              </dd>

              <dt><Icon name="lucide:shield-alert" size="12" /> Forces de l’ordre</dt>
              <dd>
                <button
                  type="button"
                  class="bed__badge bed__toggle"
                  :class="policeStatus(bed.police_status).tone"
                  :disabled="busy"
                  title="Cliquer pour passer à l’état suivant : Non, À prévenir, Prévenues"
                  @click="toggleFlag(bed, 'police_status')"
                >
                  <Icon :name="policeStatus(bed.police_status).icon" size="12" />
                  {{ policeStatus(bed.police_status).label }}
                </button>
              </dd>
            </dl>

            <footer class="bed__actions">
              <button type="button" class="rooms-button" :disabled="busy" @click="openPatientDialog(bed)"><Icon name="lucide:pencil" size="13" /> Modifier</button>
              <button type="button" class="rooms-button rooms-button--danger" :disabled="busy" @click="releaseBed(bed)"><Icon name="lucide:log-out" size="13" /> Libérer</button>
            </footer>
          </template>

          <template v-else>
            <p class="bed__empty">Aucun patient</p>
            <footer class="bed__actions">
              <button type="button" class="rooms-button rooms-button--primary" :disabled="busy" @click="openPatientDialog(bed)"><Icon name="lucide:user-plus" size="14" /> Affecter un patient</button>
              <button v-if="canManage" type="button" class="rooms-button rooms-button--danger bed__delete" :disabled="busy" aria-label="Supprimer le lit" title="Supprimer le lit" @click="deleteBed(room, bed)"><Icon name="lucide:trash-2" size="13" /></button>
            </footer>
          </template>
        </article>
      </div>
      <p v-else class="room__empty">Aucun lit dans cette chambre.</p>
    </section>

    <div v-if="loaded && !loadError && !rooms.length" class="rooms__empty">
      <Icon name="lucide:bed-double" size="21" />
      <p>{{ canManage ? 'Aucune chambre. Ajoutez la première chambre ci-dessus.' : 'Aucune chambre n’est encore configurée.' }}</p>
    </div>

    <dialog ref="patientDialog" class="rooms-dialog" aria-labelledby="bed-dialog-title" @cancel.prevent="closePatientDialog">
      <form class="rooms-dialog__content" @submit.prevent="savePatient">
        <header class="rooms-dialog__header">
          <h2 id="bed-dialog-title">{{ editingBed?.patient_name ? 'Modifier le patient' : 'Affecter un patient' }}<small v-if="editingBed"> · {{ editingBed.label }}</small></h2>
          <button type="button" class="rooms-dialog__close" aria-label="Fermer" :disabled="saving" @click="closePatientDialog">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>

        <div class="rooms-form">
          <label>Patient (nom, prénom)
            <input v-model="form.patient_name" type="text" maxlength="120" required>
          </label>
          <label>Date d’arrivée
            <input v-model="form.arrival_date" type="date" required>
          </label>
          <label class="rooms-form__wide">Accident
            <input v-model="form.accident" type="text" maxlength="200" placeholder="Ex. chute à moto, blessure par balle…">
          </label>
          <label :class="{ 'rooms-form__wide': reasonChoice !== OTHER_REASON }">Raison de la présence
            <select v-model="reasonChoice">
              <option value="">Non précisée</option>
              <option v-for="reason in reasons" :key="reason.id" :value="reason.name">{{ reason.name }}</option>
              <option :value="OTHER_REASON">Autre…</option>
            </select>
          </label>
          <label v-if="reasonChoice === OTHER_REASON">Autre raison
            <input v-model="otherReason" type="text" maxlength="64" placeholder="Saisir la raison" required>
          </label>
          <fieldset class="rooms-form__wide rooms-form__choices">
            <legend>Forces de l’ordre</legend>
            <label v-for="status in POLICE_STATUSES" :key="status.value" :class="{ 'is-selected': form.police_status === status.value }">
              <input v-model="form.police_status" type="radio" name="police-status" :value="status.value">
              <Icon :name="status.icon" size="13" /> {{ status.label }}
            </label>
          </fieldset>
        </div>

        <p v-if="formError" class="rooms__error" role="alert"><Icon name="lucide:circle-alert" size="16" /><span>{{ formError }}</span></p>

        <footer class="rooms-dialog__footer">
          <button type="button" class="rooms-button" :disabled="saving" @click="closePatientDialog">Annuler</button>
          <button type="submit" class="rooms-button rooms-button--primary" :disabled="saving">
            <Icon v-if="saving" name="lucide:loader-circle" size="14" class="rooms-spin" />
            {{ editingBed?.patient_name ? 'Enregistrer' : 'Affecter' }}
          </button>
        </footer>
      </form>
    </dialog>

    <dialog ref="roomDialog" class="rooms-dialog rooms-dialog--small" aria-labelledby="room-dialog-title" @cancel.prevent="!busy && roomDialog?.close()">
      <form class="rooms-dialog__content" @submit.prevent="saveRoom">
        <header class="rooms-dialog__header">
          <h2 id="room-dialog-title">{{ editingRoom ? 'Renommer la chambre' : 'Ajouter une chambre' }}</h2>
          <button type="button" class="rooms-dialog__close" aria-label="Fermer" :disabled="busy" @click="roomDialog?.close()">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>
        <div class="rooms-form">
          <label class="rooms-form__wide">Nom de la chambre
            <input v-model="roomName" type="text" maxlength="64" placeholder="Ex. Chambre 1, Soins intensifs…" required>
          </label>
        </div>
        <p v-if="roomError" class="rooms__error" role="alert"><Icon name="lucide:circle-alert" size="16" /><span>{{ roomError }}</span></p>
        <footer class="rooms-dialog__footer">
          <button type="button" class="rooms-button" :disabled="busy" @click="roomDialog?.close()">Annuler</button>
          <button type="submit" class="rooms-button rooms-button--primary" :disabled="busy">
            <Icon v-if="busy" name="lucide:loader-circle" size="14" class="rooms-spin" />
            {{ editingRoom ? 'Renommer' : 'Ajouter' }}
          </button>
        </footer>
      </form>
    </dialog>

    <dialog ref="reasonsDialog" class="rooms-dialog rooms-dialog--small" aria-labelledby="reasons-dialog-title">
      <div class="rooms-dialog__content">
        <header class="rooms-dialog__header">
          <h2 id="reasons-dialog-title">Raisons proposées</h2>
          <button type="button" class="rooms-dialog__close" aria-label="Fermer" @click="reasonsDialog?.close()">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>
        <p class="rooms-dialog__hint">Proposées à l’affectation d’un patient. On peut toujours saisir une autre raison.</p>
        <form class="rooms__add" @submit.prevent="addReason">
          <input v-model="newReasonName" type="text" maxlength="64" placeholder="Nouvelle raison" aria-label="Nouvelle raison">
          <button type="submit" class="rooms-button rooms-button--primary" :disabled="busy"><Icon name="lucide:plus" size="15" /> Ajouter</button>
        </form>
        <p v-if="reasonError" class="rooms__error" role="alert"><Icon name="lucide:circle-alert" size="16" /><span>{{ reasonError }}</span></p>
        <ul v-if="reasons.length" class="rooms__reasons">
          <li v-for="reason in reasons" :key="reason.id">
            <span class="bed__reason" :style="{ '--reason-hue': reasonHue(reason.name) }">{{ reason.name }}</span>
            <button type="button" class="rooms-button rooms-button--danger" :disabled="busy" :aria-label="`Supprimer la raison ${reason.name}`" @click="deleteReason(reason)"><Icon name="lucide:trash-2" size="13" /></button>
          </li>
        </ul>
        <p v-else class="rooms-dialog__hint">Aucune raison pour l’instant.</p>
      </div>
    </dialog>

    <ConfirmDialog
      v-model:visible="confirmVisible"
      title="Confirmation"
      :message="confirmMessage"
      @confirm="onConfirm"
      @cancel="onCancel"
    />
  </div>
</template>

<style scoped>
.rooms { display: grid; gap: 16px; }
.rooms__toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.rooms__counts, .rooms__manage { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.rooms__count { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-2); background: var(--dp-panel-2); font-size: 11px; }
.rooms__count :deep(svg) { color: var(--dp-accent); }
.rooms__count strong { color: var(--dp-text); font-size: 14px; font-variant-numeric: tabular-nums; }
.rooms__add { display: flex; gap: 8px; }
.rooms__add input { min-width: 0; min-height: 40px; flex: 1 1 180px; padding: 0 11px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.rooms__add input:focus-visible { border-color: var(--dp-accent-line); outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }

.room { padding: 14px; border: 1px solid var(--dp-line); border-radius: 14px; background: var(--dp-panel-2); }
.room__head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin-bottom: 12px; }
.room__head h3 { display: inline-flex; align-items: center; gap: 7px; margin: 0; color: var(--dp-text); font-size: 15px; }
.room__head h3 :deep(svg) { color: var(--dp-accent); }
.room__occupancy { padding: 3px 9px; border: 1px solid var(--dp-line); border-radius: 999px; color: var(--dp-text-2); font-size: 10px; font-variant-numeric: tabular-nums; }
.room__actions { display: flex; gap: 6px; margin-left: auto; }
.room__empty { margin: 0; color: var(--dp-text-dim); font-size: 12px; }
.room__beds { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr)); align-items: start; gap: 12px; }

/* Lit : même allure qu'une cellule de la morgue, angles droits et tête de lit en haut. */
.bed { position: relative; display: grid; gap: 10px; min-width: 0; padding: 18px 14px 14px; border: 1px solid var(--dp-line); border-top: 4px solid var(--dp-accent); border-radius: 6px; background: linear-gradient(180deg, var(--dp-accent-soft), transparent 46%), var(--dp-panel); }
.bed::before { content: ''; position: absolute; top: 7px; left: 50%; width: 42px; height: 4px; transform: translateX(-50%); border-radius: 2px; background: color-mix(in srgb, var(--dp-accent) 55%, transparent); }
.bed--free { border-style: dashed; border-top-style: solid; border-top-color: var(--dp-line-strong); background: var(--dp-panel); }
.bed--free::before { background: var(--dp-line-strong); }
.bed__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.bed__label { display: inline-flex; align-items: center; gap: 5px; color: var(--dp-accent); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.bed--free .bed__label { color: var(--dp-text-dim); }
.bed__head time { color: var(--dp-text); font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
.bed__free { color: var(--dp-text-dim); font-size: 10px; font-weight: 700; text-transform: uppercase; }
.bed__patient { margin: 0; overflow-wrap: anywhere; color: var(--dp-text); font-size: 14px; font-weight: 700; }
.bed__reason { justify-self: start; max-width: 100%; overflow: hidden; padding: 3px 9px; border: 1px solid hsl(var(--reason-hue) 55% 55% / .5); border-radius: 999px; color: hsl(var(--reason-hue) 70% 72%); background: hsl(var(--reason-hue) 55% 45% / .16); font-size: 10px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.bed__reason--none { border-color: var(--dp-line); color: var(--dp-text-dim); background: transparent; font-weight: 500; }
.bed__empty { margin: 0; color: var(--dp-text-dim); font-size: 12px; font-style: italic; }

/* Une ligne par information : libellé à gauche, valeur à droite, toutes alignées. */
.bed__rows { display: grid; grid-template-columns: max-content minmax(0, 1fr); align-items: center; gap: 7px 12px; margin: 0; padding: 10px 0; border-top: 1px solid var(--dp-line); border-bottom: 1px solid var(--dp-line); }
.bed__rows dt { display: inline-flex; align-items: center; gap: 5px; color: var(--dp-text-dim); font-size: 9px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.bed__rows dd { display: flex; min-width: 0; min-height: 26px; align-items: center; margin: 0; overflow-wrap: anywhere; color: var(--dp-text-2); font-size: 11px; }
.bed__badge { display: inline-flex; min-height: 24px; align-items: center; gap: 5px; padding: 0 8px; border: 1px solid var(--dp-line); border-radius: 6px; background: transparent; font: inherit; font-size: 10px; font-weight: 600; }
.bed__badge.is-ok { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.bed__badge.is-ko { border-color: var(--dp-danger-line); color: var(--dp-danger); background: var(--dp-danger-soft); }
.bed__badge.is-warn { border-color: var(--dp-warn-line); color: var(--dp-warn); background: var(--dp-warn-soft); }
.bed__badge.is-muted { color: var(--dp-text-dim); }
.bed__toggle { cursor: pointer; transition: filter .16s ease, border-color .16s ease; }
.bed__toggle:hover:not(:disabled) { filter: brightness(1.2); border-color: var(--dp-line-strong); }
.bed__toggle:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: 2px; }
.bed__toggle:disabled { cursor: wait; }

/* Boutons de même largeur sur une seule ligne. */
.bed__actions { display: grid; grid-auto-columns: minmax(0, 1fr); grid-auto-flow: column; gap: 6px; }
.bed__actions .rooms-button { min-width: 0; padding: 0 6px; }
.bed--free .bed__actions { grid-template-columns: minmax(0, 1fr); grid-auto-columns: 34px; }

.rooms-button { display: inline-flex; min-height: 32px; align-items: center; justify-content: center; gap: 6px; padding: 0 10px; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text-2); background: transparent; font: inherit; font-size: 10px; font-weight: 650; cursor: pointer; white-space: nowrap; transition: background .16s ease, border-color .16s ease, color .16s ease; }
.rooms-button:hover:not(:disabled) { border-color: var(--dp-line-strong); color: var(--dp-text); background: var(--dp-panel-3); }
.rooms-button:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: 2px; }
.rooms-button:disabled { opacity: .5; cursor: not-allowed; }
.rooms-button--primary { border-color: transparent; color: #0c1710; background: var(--dp-accent); }
.rooms-button--primary:hover:not(:disabled) { filter: brightness(1.08); color: #0c1710; background: var(--dp-accent); }
.rooms-button--danger { color: var(--dp-danger); background: var(--dp-danger-soft); }
.rooms__toolbar .rooms-button { min-height: 40px; padding: 0 14px; font-size: 11px; }

.rooms__empty { display: grid; min-height: 170px; justify-items: center; align-content: center; gap: 9px; padding: 24px; border: 1px dashed var(--dp-line-strong); border-radius: 14px; color: var(--dp-text-dim); text-align: center; font-size: 12px; }
.rooms__empty p { margin: 0; }
.rooms__error { display: flex; align-items: center; gap: 8px; margin: 0; padding: 10px 12px; border: 1px solid var(--dp-danger-line); border-radius: 10px; color: #f0a29d; background: var(--dp-danger-soft); font-size: 12px; }

.rooms-dialog { position: fixed; inset: 50% auto auto 50%; width: min(600px, calc(100vw - 28px)); max-height: min(90dvh, 760px); margin: 0; padding: 0; overflow: auto; transform: translate(-50%, -50%); border: 1px solid var(--dp-line-strong); border-radius: 18px; color: var(--dp-text); background: var(--dp-panel); box-shadow: 0 24px 80px rgba(0, 0, 0, .55); }
.rooms-dialog--small { width: min(440px, calc(100vw - 28px)); }
.rooms-dialog::backdrop { background: rgba(5, 8, 11, .76); backdrop-filter: blur(5px); }
.rooms-dialog__content { display: grid; gap: 16px; margin: 0; padding: clamp(18px, 4vw, 26px); }
.rooms-dialog__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 14px; border-bottom: 1px solid var(--dp-line); }
.rooms-dialog__header h2 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
.rooms-dialog__header small { color: var(--dp-text-dim); font-size: 13px; font-weight: 500; }
.rooms-dialog__close { display: grid; width: 32px; height: 32px; place-items: center; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text-2); background: transparent; cursor: pointer; }
.rooms-dialog__close:hover:not(:disabled) { color: var(--dp-text); background: var(--dp-panel-3); }
.rooms-dialog__footer { display: flex; justify-content: flex-end; gap: 8px; padding-top: 14px; border-top: 1px solid var(--dp-line); }
.rooms-dialog__footer .rooms-button { min-height: 40px; padding: 0 14px; font-size: 11px; }
.rooms-dialog__hint { margin: 0; color: var(--dp-text-dim); font-size: 11px; }
.rooms-dialog .rooms__add .rooms-button { min-height: 40px; }
.rooms__reasons { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.rooms__reasons li { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 8px; border: 1px solid var(--dp-line); border-radius: 9px; background: var(--dp-panel-2); }
.rooms__reasons .rooms-button { width: 30px; min-height: 28px; padding: 0; }

.rooms-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; gap: 12px; }
.rooms-form > label { display: grid; align-content: start; gap: 6px; color: var(--dp-text-2); font-size: 11px; font-weight: 650; }
.rooms-form input:not([type='checkbox'], [type='radio']), .rooms-form select { width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 11px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.rooms-form select { cursor: pointer; }
.rooms-form__choices { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; border: 0; }
.rooms-form__choices legend { margin-bottom: 6px; padding: 0; color: var(--dp-text-2); font-size: 11px; font-weight: 650; }
.rooms-form__choices label { display: inline-flex; min-height: 36px; flex: 1 1 120px; align-items: center; justify-content: center; gap: 6px; padding: 0 12px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text-2); background: var(--dp-bg); font-size: 11px; font-weight: 600; cursor: pointer; }
.rooms-form__choices label.is-selected { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.rooms-form__choices input { position: absolute; opacity: 0; pointer-events: none; }
.rooms-form__choices label:focus-within { outline: 2px solid var(--dp-accent); outline-offset: 2px; }
.rooms-form select:focus-visible, .rooms-form input:focus-visible { border-color: var(--dp-accent-line); outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }
.rooms-form__wide { grid-column: 1 / -1; }

.rooms-spin { animation: rooms-spin 1s linear infinite; }
@keyframes rooms-spin { to { transform: rotate(360deg); } }

@media (max-width: 640px) {
  .rooms-form { grid-template-columns: 1fr; }
  .room__actions { margin-left: 0; }
  .rooms-dialog__footer { flex-direction: column-reverse; }
  .rooms-dialog__footer > button { width: 100%; }
}
</style>
