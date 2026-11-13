<script setup lang="ts">
interface MorgueEntry {
  id: number
  death_date: string
  identity: string
  affiliation: string
  info_shareable: boolean
  autopsy_done: boolean
  examiner_id: number | null
  examiner_name: string | null
  emergency_contacts: string
  recoverable: boolean
  incinerated_at: string | null
}

interface MorgueExaminer {
  id: number
  name: string
}

interface MorgueData {
  entries: MorgueEntry[]
  examiners: MorgueExaminer[]
  can_manage_autopsy: boolean
  can_incinerate: boolean
}

const props = defineProps<{ active: boolean }>()

const toast = useAppToast()

const entries = ref<MorgueEntry[]>([])
const examiners = ref<MorgueExaminer[]>([])
/** Légistes et Direction : seuls à renseigner l'autopsie et le légiste. */
const canManageAutopsy = ref(false)
const canIncinerate = ref(false)
const loaded = ref(false)
const loadError = ref('')
/** Défunt en cours d'enregistrement, d'incinération ou de retrait. */
const busyId = ref<number | null>(null)

const dialog = ref<HTMLDialogElement | null>(null)
const editingId = ref<number | null>(null)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  death_date: '',
  identity: '',
  affiliation: '',
  info_shareable: false,
  emergency_contacts: ''
})

/** Corps en cellule d'abord, puis urnes ; chacun du décès le plus ancien au plus récent. */
const sortedEntries = computed(() =>
  [...entries.value].sort((a, b) =>
    Number(a.incinerated_at !== null) - Number(b.incinerated_at !== null)
    || a.death_date.localeCompare(b.death_date)
    || a.id - b.id
  )
)
const bodyCount = computed(() => entries.value.filter((entry) => entry.incinerated_at === null).length)
const urnCount = computed(() => entries.value.length - bodyCount.value)

const affiliationOptions = computed(() =>
  [...new Set(entries.value.map((entry) => entry.affiliation).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr'))
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

/** Couleur stable par appartenance, pour reconnaître un groupe d'un coup d'œil. */
function affiliationHue(name: string) {
  let hash = 0
  for (const char of name.toLowerCase()) hash = (hash * 31 + char.charCodeAt(0)) % 360
  return hash
}

async function load() {
  try {
    const data = await $fetch<MorgueData>('/api/hospital/morgue', { credentials: 'include' })
    entries.value = data.entries
    examiners.value = data.examiners
    canManageAutopsy.value = data.can_manage_autopsy
    canIncinerate.value = data.can_incinerate
    loadError.value = ''
  } catch (cause) {
    loadError.value = messageFromError(cause, 'Impossible de charger la morgue.')
  } finally {
    loaded.value = true
  }
}

/** Rafraîchissement en arrière-plan, sans toucher à un défunt en cours de modification. */
function refresh() {
  if (!props.active || saving.value || busyId.value !== null || dialog.value?.open) return
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

function openDialog(entry?: MorgueEntry) {
  editingId.value = entry?.id ?? null
  formError.value = ''
  form.death_date = entry?.death_date ?? today()
  form.identity = entry?.identity ?? ''
  form.affiliation = entry?.affiliation ?? ''
  form.info_shareable = entry?.info_shareable ?? false
  form.emergency_contacts = entry?.emergency_contacts ?? ''
  dialog.value?.showModal()
}

function closeDialog() {
  if (saving.value) return
  dialog.value?.close()
}

async function save() {
  if (saving.value) return
  if (!form.death_date) {
    formError.value = 'La date du décès est obligatoire.'
    return
  }
  saving.value = true
  formError.value = ''
  const id = editingId.value
  try {
    const saved = await $fetch<MorgueEntry>(id === null ? '/api/hospital/morgue' : `/api/hospital/morgue/${id}`, {
      method: id === null ? 'POST' : 'PATCH',
      credentials: 'include',
      body: { ...form }
    })
    entries.value = id === null
      ? [...entries.value, saved]
      : entries.value.map((entry) => entry.id === id ? saved : entry)
    dialog.value?.close()
    toast.success(id === null ? 'Défunt ajouté à la morgue.' : 'Fiche du défunt mise à jour.')
  } catch (cause) {
    formError.value = messageFromError(cause, 'Impossible d’enregistrer ce défunt.')
  } finally {
    saving.value = false
  }
}

/**
 * Autopsie et récupération : renseignées après l'ajout, d'un clic sur la case.
 * Le légiste qui déclare l'autopsie devient le légiste du défunt.
 */
async function toggle(entry: MorgueEntry, field: 'autopsy_done' | 'recoverable') {
  if (busyId.value !== null) return
  busyId.value = entry.id
  try {
    const saved = await $fetch<MorgueEntry>(
      field === 'autopsy_done' ? `/api/hospital/morgue/${entry.id}/autopsy` : `/api/hospital/morgue/${entry.id}`,
      {
        method: field === 'autopsy_done' ? 'PUT' : 'PATCH',
        credentials: 'include',
        body: field === 'autopsy_done' ? { done: !entry.autopsy_done } : { recoverable: !entry.recoverable }
      }
    )
    entries.value = entries.value.map((item) => item.id === entry.id ? saved : item)
  } catch (cause) {
    toast.error(messageFromError(cause, 'Impossible de mettre à jour ce défunt.'))
  } finally {
    busyId.value = null
  }
}

/** Légistes au choix, avec celui déjà désigné même s'il n'a plus le rôle. */
function examinerOptions(entry: MorgueEntry) {
  if (entry.examiner_id === null || examiners.value.some((examiner) => examiner.id === entry.examiner_id)) {
    return examiners.value
  }
  return [...examiners.value, { id: entry.examiner_id, name: entry.examiner_name ?? 'Inconnu' }]
}

async function setExaminer(entry: MorgueEntry, select: HTMLSelectElement) {
  const examinerId = select.value ? Number(select.value) : null
  if (busyId.value !== null || examinerId === entry.examiner_id) return
  busyId.value = entry.id
  try {
    const saved = await $fetch<MorgueEntry>(`/api/hospital/morgue/${entry.id}/examiner`, {
      method: 'PUT',
      credentials: 'include',
      body: { examiner_id: examinerId }
    })
    entries.value = entries.value.map((item) => item.id === entry.id ? saved : item)
  } catch (cause) {
    toast.error(messageFromError(cause, 'Impossible de changer le légiste.'))
    // Le menu revient sur le légiste enregistré.
    select.value = String(entry.examiner_id ?? '')
  } finally {
    busyId.value = null
  }
}

function entryLabel(entry: MorgueEntry) {
  return entry.identity ? `« ${entry.identity} »` : 'ce défunt non identifié'
}

async function incinerate(entry: MorgueEntry) {
  if (busyId.value !== null) return
  if (!window.confirm(`Procéder à l’incinération de ${entryLabel(entry)} ? Le corps sera remplacé par une urne.`)) return
  busyId.value = entry.id
  try {
    const saved = await $fetch<MorgueEntry>(`/api/hospital/morgue/${entry.id}/incinerate`, {
      method: 'POST',
      credentials: 'include'
    })
    entries.value = entries.value.map((item) => item.id === entry.id ? saved : item)
    toast.success('Incinération enregistrée.')
  } catch (cause) {
    toast.error(messageFromError(cause, 'Impossible d’enregistrer l’incinération.'))
  } finally {
    busyId.value = null
  }
}

async function remove(entry: MorgueEntry) {
  if (busyId.value !== null) return
  const what = entry.incinerated_at ? 'l’urne de' : 'le corps de'
  if (!window.confirm(`Retirer ${what} ${entryLabel(entry)} de la morgue ?`)) return
  busyId.value = entry.id
  try {
    await $fetch(`/api/hospital/morgue/${entry.id}`, { method: 'DELETE', credentials: 'include' })
    entries.value = entries.value.filter((item) => item.id !== entry.id)
    toast.success(entry.incinerated_at ? 'Urne retirée de la morgue.' : 'Corps retiré de la morgue.')
  } catch (cause) {
    toast.error(messageFromError(cause, 'Impossible de retirer ce défunt.'))
  } finally {
    busyId.value = null
  }
}
</script>

<template>
  <div class="morgue">
    <div class="morgue__toolbar">
      <div class="morgue__counts" aria-label="Résumé de la morgue">
        <span class="morgue__count"><span class="morgue__shape morgue__shape--body" aria-hidden="true"></span><strong>{{ bodyCount }}</strong> corps en cellule</span>
        <span class="morgue__count"><span class="morgue__shape morgue__shape--urn" aria-hidden="true"></span><strong>{{ urnCount }}</strong> urne{{ urnCount > 1 ? 's' : '' }}</span>
      </div>
      <button type="button" class="morgue-button morgue-button--primary" @click="openDialog()">
        <Icon name="lucide:plus" size="16" /> Ajouter un défunt
      </button>
    </div>

    <div v-if="loadError" class="morgue__error" role="alert">
      <Icon name="lucide:circle-alert" size="16" /><span>{{ loadError }}</span>
    </div>

    <div v-if="sortedEntries.length" class="morgue__grid">
      <article
        v-for="entry in sortedEntries"
        :key="entry.id"
        class="morgue-case"
        :class="entry.incinerated_at ? 'morgue-case--urn' : 'morgue-case--body'"
        :aria-busy="busyId === entry.id"
      >
        <header class="morgue-case__head">
          <span class="morgue-case__kind">
            <Icon :name="entry.incinerated_at ? 'lucide:amphora' : 'lucide:snowflake'" size="13" />
            {{ entry.incinerated_at ? 'Urne' : 'Cellule réfrigérée' }}
          </span>
          <time :datetime="entry.death_date" title="Date du décès">{{ formatDate(entry.death_date) }}</time>
        </header>

        <h3 class="morgue-case__identity" :class="{ 'is-unknown': !entry.identity }">{{ entry.identity || 'Identité inconnue' }}</h3>
        <span
          v-if="entry.affiliation"
          class="morgue-case__affiliation"
          :style="{ '--affiliation-hue': affiliationHue(entry.affiliation) }"
        >{{ entry.affiliation }}</span>
        <span v-else class="morgue-case__affiliation morgue-case__affiliation--none">Appartenance inconnue</span>

        <dl class="morgue-case__rows">
          <dt><Icon name="lucide:info" size="12" /> Infos</dt>
          <dd>
            <span class="morgue-case__badge" :class="entry.info_shareable ? 'is-ok' : 'is-ko'">
              <Icon :name="entry.info_shareable ? 'lucide:circle-check' : 'lucide:circle-alert'" size="12" />
              {{ entry.info_shareable ? 'Communicables' : 'Non communicables' }}
            </span>
          </dd>

          <dt><Icon name="lucide:microscope" size="12" /> Autopsie</dt>
          <dd>
            <button
              v-if="canManageAutopsy"
              type="button"
              class="morgue-case__badge morgue-case__toggle"
              :class="entry.autopsy_done ? 'is-ok' : 'is-muted'"
              :aria-pressed="entry.autopsy_done"
              :disabled="busyId !== null"
              title="Cliquer pour changer"
              @click="toggle(entry, 'autopsy_done')"
            >
              <Icon :name="entry.autopsy_done ? 'lucide:circle-check' : 'lucide:circle-dashed'" size="12" />
              {{ entry.autopsy_done ? 'Effectuée' : 'Non effectuée' }}
            </button>
            <span v-else class="morgue-case__badge" :class="entry.autopsy_done ? 'is-ok' : 'is-muted'">
              <Icon :name="entry.autopsy_done ? 'lucide:circle-check' : 'lucide:circle-dashed'" size="12" />
              {{ entry.autopsy_done ? 'Effectuée' : 'Non effectuée' }}
            </span>
          </dd>

          <dt><Icon name="lucide:stethoscope" size="12" /> Légiste</dt>
          <dd>
            <select
              v-if="canManageAutopsy"
              class="morgue-case__select"
              :value="entry.examiner_id ?? ''"
              :disabled="busyId !== null"
              aria-label="Médecin légiste"
              @change="setExaminer(entry, $event.target as HTMLSelectElement)"
            >
              <option value="">Aucun</option>
              <option v-for="examiner in examinerOptions(entry)" :key="examiner.id" :value="examiner.id">{{ examiner.name }}</option>
            </select>
            <template v-else>{{ entry.examiner_name || '—' }}</template>
          </dd>

          <dt><Icon name="lucide:phone" size="12" /> Contacts</dt>
          <dd class="morgue-case__contacts">{{ entry.emergency_contacts || '—' }}</dd>
        </dl>

        <button
          type="button"
          class="morgue-case__recovery"
          :class="entry.recoverable ? 'is-ok' : 'is-ko'"
          :aria-pressed="entry.recoverable"
          :disabled="busyId !== null"
          title="Cliquer pour changer"
          @click="toggle(entry, 'recoverable')"
        >
          <Icon :name="entry.recoverable ? 'lucide:hand-heart' : 'lucide:lock'" size="13" />
          {{ entry.recoverable ? 'Récupérable par les proches' : 'Non récupérable' }}
        </button>

        <footer class="morgue-case__actions">
          <button type="button" class="morgue-button" :disabled="busyId !== null" @click="openDialog(entry)">
            <Icon name="lucide:pencil" size="13" /> Modifier
          </button>
          <button
            v-if="canIncinerate && !entry.incinerated_at"
            type="button"
            class="morgue-button morgue-button--warn"
            :disabled="busyId !== null"
            @click="incinerate(entry)"
          >
            <Icon :name="busyId === entry.id ? 'lucide:loader-circle' : 'lucide:flame'" size="13" :class="{ 'morgue-spin': busyId === entry.id }" /> Incinérer
          </button>
          <button
            type="button"
            class="morgue-button morgue-button--danger"
            :disabled="busyId !== null"
            :aria-label="entry.incinerated_at ? 'Retirer l’urne' : 'Retirer le corps'"
            :title="entry.incinerated_at ? 'Retirer l’urne' : 'Retirer le corps'"
            @click="remove(entry)"
          >
            <Icon name="lucide:log-out" size="13" /> Retirer
          </button>
        </footer>
      </article>
    </div>

    <div v-else-if="loaded && !loadError" class="morgue__empty">
      <Icon name="lucide:snowflake" size="21" />
      <p>Aucun défunt à la morgue.</p>
    </div>

    <dialog ref="dialog" class="morgue-dialog" aria-labelledby="morgue-dialog-title" @cancel.prevent="closeDialog">
      <form class="morgue-dialog__content" @submit.prevent="save">
        <header class="morgue-dialog__header">
          <h2 id="morgue-dialog-title">{{ editingId === null ? 'Ajouter un défunt' : 'Modifier le défunt' }}</h2>
          <button type="button" class="morgue-dialog__close" aria-label="Fermer" :disabled="saving" @click="closeDialog">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>

        <div class="morgue-form">
          <label>Date du décès
            <input v-model="form.death_date" type="date" required>
          </label>
          <label>Identité (nom, prénom)
            <input v-model="form.identity" type="text" maxlength="120" placeholder="Laisser vide si inconnue">
          </label>
          <label class="morgue-form__wide">Appartenance connue
            <input v-model="form.affiliation" type="text" maxlength="64" list="morgue-affiliations" placeholder="Groupe, organisation… (facultatif)">
            <datalist id="morgue-affiliations">
              <option v-for="option in affiliationOptions" :key="option" :value="option" />
            </datalist>
          </label>
          <label class="morgue-form__wide">Contacts d’urgence (nom, numéro)
            <textarea v-model="form.emergency_contacts" maxlength="500" rows="2" placeholder="Proches à appeler pour récupérer le corps ou l’urne"></textarea>
          </label>
          <label class="morgue-form__check morgue-form__wide"><input v-model="form.info_shareable" type="checkbox"> Informations communicables</label>
        </div>

        <p v-if="formError" class="morgue__error" role="alert"><Icon name="lucide:circle-alert" size="16" /><span>{{ formError }}</span></p>

        <footer class="morgue-dialog__footer">
          <button type="button" class="morgue-button" :disabled="saving" @click="closeDialog">Annuler</button>
          <button type="submit" class="morgue-button morgue-button--primary" :disabled="saving">
            <Icon v-if="saving" name="lucide:loader-circle" size="14" class="morgue-spin" />
            {{ editingId === null ? 'Ajouter' : 'Enregistrer' }}
          </button>
        </footer>
      </form>
    </dialog>
  </div>
</template>

<style scoped>
.morgue__toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.morgue__counts { display: flex; flex-wrap: wrap; gap: 8px; }
.morgue__count { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-2); background: var(--dp-panel-2); font-size: 11px; }
.morgue__count strong { color: var(--dp-text); font-size: 14px; font-variant-numeric: tabular-nums; }

/* Les deux formes de case, reprises en miniature dans le résumé. */
.morgue__shape { display: inline-block; flex-shrink: 0; border: 1.5px solid currentColor; }
.morgue__shape--body { width: 18px; height: 11px; border-radius: 2px; color: var(--dp-info); }
.morgue__shape--urn { width: 11px; height: 15px; border-radius: 6px 6px 3px 3px; color: var(--dp-warn); }

/* Toutes les cases ont la même taille, qu'elles contiennent un corps ou une urne. */
.morgue__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr)); grid-auto-rows: 1fr; gap: 14px; }

.morgue-case { position: relative; display: flex; flex-direction: column; gap: 10px; min-width: 0; padding: 14px; border: 1px solid var(--dp-line); background: var(--dp-panel-2); transition: border-color .16s ease, opacity .16s ease; }
.morgue-case[aria-busy='true'] { opacity: .6; }
/* Corps : porte de cellule réfrigérée, angles droits et poignée en haut. */
.morgue-case--body { border-radius: 6px; border-top: 4px solid var(--dp-info); padding-top: 18px; background: linear-gradient(180deg, var(--dp-info-soft), transparent 46%), var(--dp-panel-2); }
.morgue-case--body::before { content: ''; position: absolute; top: 7px; left: 50%; width: 42px; height: 4px; transform: translateX(-50%); border-radius: 2px; background: color-mix(in srgb, var(--dp-info) 55%, transparent); }
/* Urne : sommet en arche, bord doré. */
.morgue-case--urn { border-color: var(--dp-warn-line); border-radius: 120px 120px 14px 14px; padding-top: 34px; background: radial-gradient(ellipse at 50% 0, var(--dp-warn-soft), transparent 62%), var(--dp-panel-2); }

/* En-tête, identité et appartenance centrés, pour un corps comme pour une urne. */
.morgue-case__head { display: flex; flex-direction: column; align-items: center; gap: 3px; color: var(--dp-text-dim); font-size: 10px; font-weight: 700; letter-spacing: .04em; }
.morgue-case__head time { color: var(--dp-text); font-size: 12px; font-variant-numeric: tabular-nums; letter-spacing: 0; }
.morgue-case__kind { display: inline-flex; align-items: center; gap: 5px; text-transform: uppercase; }
.morgue-case--body .morgue-case__kind { color: var(--dp-info); }
.morgue-case--urn .morgue-case__kind { color: var(--dp-warn); }
.morgue-case__identity { margin: 0; overflow-wrap: anywhere; text-align: center; color: var(--dp-text); font-size: 14px; font-weight: 700; }
.morgue-case__identity.is-unknown { color: var(--dp-text-dim); font-style: italic; font-weight: 600; }
.morgue-case__affiliation { align-self: center; max-width: 100%; overflow: hidden; padding: 3px 9px; border: 1px solid hsl(var(--affiliation-hue) 55% 55% / .5); border-radius: 999px; color: hsl(var(--affiliation-hue) 70% 72%); background: hsl(var(--affiliation-hue) 55% 45% / .16); font-size: 10px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.morgue-case__affiliation--none { border-color: var(--dp-line); color: var(--dp-text-dim); background: transparent; font-weight: 500; }
/* Une ligne par information : libellé à gauche, valeur à droite, toutes alignées. */
.morgue-case__rows { display: grid; grid-template-columns: max-content minmax(0, 1fr); align-items: center; gap: 7px 12px; margin: 0; padding: 10px 0; border-top: 1px solid var(--dp-line); border-bottom: 1px solid var(--dp-line); }
.morgue-case__rows dt { display: inline-flex; align-items: center; gap: 5px; color: var(--dp-text-dim); font-size: 9px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.morgue-case__rows dd { display: flex; min-width: 0; min-height: 26px; align-items: center; margin: 0; overflow-wrap: anywhere; color: var(--dp-text-2); font-size: 11px; }
.morgue-case__contacts { white-space: pre-line; }
.morgue-case__badge { display: inline-flex; min-height: 24px; align-items: center; gap: 5px; padding: 0 8px; border: 1px solid var(--dp-line); border-radius: 6px; background: transparent; font: inherit; font-size: 10px; font-weight: 600; }
.morgue-case__badge.is-ok { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.morgue-case__badge.is-ko { border-color: var(--dp-danger-line); color: var(--dp-danger); background: var(--dp-danger-soft); }
.morgue-case__badge.is-muted { color: var(--dp-text-dim); }
.morgue-case__select { width: 100%; min-width: 0; min-height: 26px; padding: 0 6px; border: 1px solid var(--dp-line); border-radius: 6px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; cursor: pointer; }
.morgue-case__select:focus-visible { border-color: var(--dp-accent-line); outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }
.morgue-case__select:disabled { opacity: .6; cursor: wait; }
.morgue-case__toggle, .morgue-case__recovery { cursor: pointer; transition: filter .16s ease, border-color .16s ease; }
.morgue-case__toggle:hover:not(:disabled), .morgue-case__recovery:hover:not(:disabled) { filter: brightness(1.2); border-color: var(--dp-line-strong); }
.morgue-case__toggle:focus-visible, .morgue-case__recovery:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: 2px; }
.morgue-case__toggle:disabled, .morgue-case__recovery:disabled { cursor: wait; }
/* Récupération et boutons calés en bas de la case. */
.morgue-case__recovery { display: flex; width: 100%; align-items: center; justify-content: center; gap: 6px; margin: auto 0 0; padding: 6px 8px; border: 1px solid transparent; border-radius: 7px; font: inherit; font-size: 10px; font-weight: 700; }
.morgue-case__recovery.is-ok { color: var(--dp-accent); background: var(--dp-accent-soft); }
.morgue-case__recovery.is-ko { color: var(--dp-danger); background: var(--dp-danger-soft); }
/* Boutons de même largeur sur une seule ligne. */
.morgue-case__actions { display: grid; grid-auto-columns: minmax(0, 1fr); grid-auto-flow: column; gap: 6px; }
.morgue-case__actions .morgue-button { min-width: 0; padding: 0 6px; }

.morgue-button { display: inline-flex; min-height: 32px; align-items: center; justify-content: center; gap: 6px; padding: 0 10px; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text-2); background: transparent; font: inherit; font-size: 10px; font-weight: 650; cursor: pointer; transition: background .16s ease, border-color .16s ease, color .16s ease; }
.morgue-button:hover:not(:disabled) { border-color: var(--dp-line-strong); color: var(--dp-text); background: var(--dp-panel-3); }
.morgue-button:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: 2px; }
.morgue-button:disabled { opacity: .5; cursor: not-allowed; }
.morgue-button--primary { min-height: 40px; padding: 0 14px; border-color: transparent; color: #0c1710; background: var(--dp-accent); font-size: 11px; }
.morgue-button--primary:hover:not(:disabled) { filter: brightness(1.08); color: #0c1710; background: var(--dp-accent); }
.morgue-button--warn { border-color: var(--dp-warn-line); color: var(--dp-warn); background: var(--dp-warn-soft); }
.morgue-button--danger { color: var(--dp-danger); background: var(--dp-danger-soft); }

.morgue__empty { display: grid; min-height: 170px; justify-items: center; align-content: center; gap: 9px; padding: 24px; border: 1px dashed var(--dp-line-strong); border-radius: 14px; color: var(--dp-text-dim); text-align: center; font-size: 12px; }
.morgue__empty p { margin: 0; }
.morgue__error { display: flex; align-items: center; gap: 8px; margin: 0 0 14px; padding: 10px 12px; border: 1px solid var(--dp-danger-line); border-radius: 10px; color: #f0a29d; background: var(--dp-danger-soft); font-size: 12px; }

.morgue-dialog { position: fixed; inset: 50% auto auto 50%; width: min(640px, calc(100vw - 28px)); max-height: min(90dvh, 760px); margin: 0; padding: 0; overflow: auto; transform: translate(-50%, -50%); border: 1px solid var(--dp-line-strong); border-radius: 18px; color: var(--dp-text); background: var(--dp-panel); box-shadow: 0 24px 80px rgba(0, 0, 0, .55); }
.morgue-dialog::backdrop { background: rgba(5, 8, 11, .76); backdrop-filter: blur(5px); }
.morgue-dialog__content { display: grid; gap: 16px; margin: 0; padding: clamp(18px, 4vw, 26px); }
.morgue-dialog__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 14px; border-bottom: 1px solid var(--dp-line); }
.morgue-dialog__header h2 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
.morgue-dialog__close { display: grid; width: 32px; height: 32px; place-items: center; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text-2); background: transparent; cursor: pointer; }
.morgue-dialog__close:hover:not(:disabled) { color: var(--dp-text); background: var(--dp-panel-3); }
.morgue-dialog__footer { display: flex; justify-content: flex-end; gap: 8px; padding-top: 14px; border-top: 1px solid var(--dp-line); }

.morgue-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; gap: 12px; }
.morgue-form > label { display: grid; align-content: start; gap: 6px; color: var(--dp-text-2); font-size: 11px; font-weight: 650; }
.morgue-form input:not([type='checkbox']), .morgue-form textarea { width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 11px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.morgue-form textarea { padding: 9px 11px; resize: vertical; }
.morgue-form input:focus-visible, .morgue-form textarea:focus-visible { border-color: var(--dp-accent-line); outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }
.morgue-form__wide { grid-column: 1 / -1; }
.morgue-form > label.morgue-form__check { display: flex; align-items: center; gap: 8px; font-weight: 500; cursor: pointer; }
.morgue-form__check input { accent-color: var(--dp-accent); }

.morgue-spin { animation: morgue-spin 1s linear infinite; }
@keyframes morgue-spin { to { transform: rotate(360deg); } }

@media (max-width: 640px) {
  .morgue-form { grid-template-columns: 1fr; }
  .morgue-dialog__footer { flex-direction: column-reverse; }
  .morgue-dialog__footer > button { width: 100%; }
}
</style>
