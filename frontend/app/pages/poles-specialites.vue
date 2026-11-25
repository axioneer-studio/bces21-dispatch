<script setup lang="ts">
import ConfirmDialog from '~/components/ConfirmDialog.vue'

definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Pôles & Spé • BCES' })

/**
 * Formations générales, rangées en pôles (ex. Pilote Medicopter, Stock,
 * Formateur) et en spécialités (ex. Médecin légiste). Les périodes d'essai et de
 * formation (Internes, Résidents) sont suivies par les formateurs dans la page
 * Formation, avec leurs propres routes (/api/formation).
 */
type TrainingCategory = 'pole' | 'specialty'

interface Training {
  id: number
  name: string
  emoji: string
  kind: 'general'
  category: TrainingCategory
  /** Droits donnés à ceux qui l'ont validée. */
  permissions: string[]
}

interface PermissionOption {
  key: string
  label: string
}

/** Rôle dans une formation. */
type MemberStatus = 'lead' | 'second' | 'validated' | 'in_progress'

interface TrainingMember {
  training_id: number
  employee_id: number
  status: MemberStatus
}

interface TrainingEmployee {
  id: number
  name: string
  phone: string | null
  grade_id: number | null
  grade_name: string | null
  grade_level: number | null
  grade_color: string | null
  /** Grade « Période d'essai » ou « En formation » : ne rejoint ni pôle ni spécialité. */
  in_formation: boolean
  competencies: string[]
}

interface TrainingPage {
  trainings: Training[]
  employees: TrainingEmployee[]
  members: TrainingMember[]
  permission_options: PermissionOption[]
  /** Ajouter, modifier et supprimer les formations : ceux qui gèrent l'hôpital. */
  can_manage: boolean
  /** Direction : gère l'équipe de toute formation et nomme son Responsable. */
  can_assign_lead: boolean
  /** Tuile liée au compte connecté. */
  employee_id: number | null
}

/** Ce que chaque droit permet, sous son nom dans la fenêtre d'une formation. */
const PERMISSION_HINTS: Record<string, string> = {
  'training.validate': 'Valide les formations de période d’essai et de période de formation.',
  'hospital.forensic': 'Autopsie, incinération et mise en cercueil à la morgue.',
  'human_resources.manage': 'Ouvre Ressources humaines : gérer les employés et leurs compétences.',
  'stock.manage': 'Gestion des stocks du BCES (page Stock).'
}

/** Rôles d'une formation, dans leur ordre d'affichage. Seul « En cours » n'a pas l'emoji. */
const STATUSES: { value: MemberStatus; label: string }[] = [
  { value: 'lead', label: 'Responsable' },
  { value: 'second', label: 'Second' },
  { value: 'validated', label: 'Validé' },
  { value: 'in_progress', label: 'En cours' }
]
const STATUS_RANK = Object.fromEntries(STATUSES.map((status, index) => [status.value, index])) as Record<MemberStatus, number>

const toast = useAppToast()

const trainings = ref<Training[]>([])
const employees = ref<TrainingEmployee[]>([])
const members = ref<TrainingMember[]>([])
const canManage = ref(false)
const canAssignLead = ref(false)
const ownEmployeeId = ref<number | null>(null)
const permissionOptions = ref<PermissionOption[]>([])

function permissionLabel(key: string) {
  return permissionOptions.value.find((option) => option.key === key)?.label ?? key
}
const loaded = ref(false)
const loadError = ref('')
/** Validations en cours, par « formation:employé ». */
const busy = ref<string[]>([])

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === 'object' && cause !== null && 'data' in cause) {
    const data = cause.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
  }
  return fallback
}

/** Un même emoji peut s'écrire avec ou sans sélecteur de variante (U+FE0F). */
function emojiKey(value: string) {
  return value.replace(/️/g, '').trim()
}

function hasTraining(employee: TrainingEmployee, training: Training) {
  return employee.competencies.some((item) => emojiKey(item) === emojiKey(training.emoji))
}

/** Le compte connecté est le Responsable de cette formation. */
/** Rôle du compte connecté dans cette formation (Responsable, Second, En cours), s'il en a un. */
function ownStatus(training: Training): MemberStatus | null {
  if (ownEmployeeId.value === null) return null
  return members.value.find((member) =>
    member.training_id === training.id && member.employee_id === ownEmployeeId.value
  )?.status ?? null
}

/**
 * Rôles que le compte peut donner, changer ou retirer : la Direction tous, le
 * Responsable Second, Validé et En cours, le Second Validé et En cours.
 */
function assignableStatuses(training: Training) {
  if (canAssignLead.value) return STATUSES
  const own = ownStatus(training)
  if (own === 'lead') return STATUSES.filter((status) => status.value !== 'lead')
  if (own === 'second') return STATUSES.filter((status) => status.value === 'validated' || status.value === 'in_progress')
  return []
}

/** Gérer l'équipe d'une formation : la Direction, son Responsable et ses Seconds. */
function canEditRoster(training: Training) {
  return assignableStatuses(training).length > 0
}

/** Un membre ne se change ou ne se retire que si son rôle fait partie de ceux que le compte peut donner. */
function canEditRow(training: Training, status: MemberStatus) {
  return assignableStatuses(training).some((item) => item.value === status)
}

function memberStatus(training: Training, employee: TrainingEmployee): MemberStatus | null {
  const member = members.value.find((item) => item.training_id === training.id && item.employee_id === employee.id)
  if (member) return member.status
  return hasTraining(employee, training) ? 'validated' : null
}

/** Équipe d'une formation : Responsables, Seconds, Validés puis En cours. */
function rosterFor(training: Training) {
  return employees.value
    .map((employee) => ({ employee, status: memberStatus(training, employee) }))
    .filter((row): row is { employee: TrainingEmployee; status: MemberStatus } => row.status !== null)
    .sort((a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status])
}

/** Employés qui ont validé la formation (l'emoji), quel que soit leur rôle. */
function validatedFor(training: Training) {
  return employees.value.filter((employee) => hasTraining(employee, training))
}

const CATEGORY_LABELS: Record<TrainingCategory, string> = { pole: 'Pôle', specialty: 'Spécialité' }

/** Une section par catégorie : les spécialités, puis les pôles. */
const sections = computed(() => [
  {
    category: 'specialty' as const,
    title: 'Spécialités',
    detail: 'Ex. Médecin légiste.',
    trainings: trainings.value.filter((training) => training.category === 'specialty')
  },
  {
    category: 'pole' as const,
    title: 'Pôles',
    detail: 'Ex. Pilote Medicopter, Stock, Formateur.',
    trainings: trainings.value.filter((training) => training.category === 'pole')
  }
])

/** Employés à ajouter : ni déjà dans l'équipe, ni en période d'essai ou en formation. */
function candidatesFor(training: Training) {
  return employees.value.filter((employee) => !employee.in_formation && memberStatus(training, employee) === null)
}

/** Rôle donné à un employé ajouté à une formation. */
const addStatus = reactive<Record<number, MemberStatus>>({})

async function load() {
  try {
    const data = await $fetch<TrainingPage>('/api/trainings', { credentials: 'include' })
    trainings.value = data.trainings
    employees.value = data.employees
    members.value = data.members
    canManage.value = data.can_manage
    canAssignLead.value = data.can_assign_lead
    ownEmployeeId.value = data.employee_id
    permissionOptions.value = data.permission_options
    loadError.value = ''
  } catch (cause) {
    loadError.value = messageFromError(cause, 'Impossible de charger les formations.')
  } finally {
    loaded.value = true
  }
}

// --- Validation d'une formation pour un employé ---

/**
 * Donne un rôle à l'employé dans la formation (« validated » pour une simple
 * validation), ou l'en retire avec `null` : l'emoji suit le rôle.
 */
async function setStatus(training: Training, employee: TrainingEmployee, status: MemberStatus | null) {
  const key = `${training.id}:${employee.id}`
  if (busy.value.includes(key)) return
  busy.value = [...busy.value, key]
  try {
    const updated = await $fetch<TrainingEmployee>(`/api/trainings/${training.id}/employees/${employee.id}`, {
      method: status ? 'PUT' : 'DELETE',
      body: status ? { status } : undefined,
      credentials: 'include'
    })
    employee.competencies = updated.competencies
    members.value = members.value.filter((item) => item.training_id !== training.id || item.employee_id !== employee.id)
    if (status && status !== 'validated') {
      members.value = [...members.value, { training_id: training.id, employee_id: employee.id, status }]
    }
  } catch (cause) {
    toast.error(messageFromError(cause, 'Validation de la formation impossible.'))
  } finally {
    busy.value = busy.value.filter((item) => item !== key)
  }
}

function onAddSelect(training: Training, event: Event) {
  const select = event.target as HTMLSelectElement
  const employee = employees.value.find((item) => item.id === Number(select.value))
  select.value = ''
  if (employee) void setStatus(training, employee, addStatus[training.id] ?? 'validated')
}

// --- Ajout, modification et suppression d'une formation ---

const dialog = ref<HTMLDialogElement | null>(null)
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive({ name: '', emoji: '', category: 'pole' as TrainingCategory, permissions: [] as string[] })

/** Ouvre la fenêtre pour une formation de la catégorie de la section (elle ne se choisit pas). */
async function openDialog(category: TrainingCategory, training?: Training) {
  editingId.value = training?.id ?? null
  form.category = category
  form.name = training?.name ?? ''
  form.emoji = training?.emoji ?? ''
  form.permissions = [...(training?.permissions ?? [])]
  await nextTick()
  if (!dialog.value?.open) dialog.value?.showModal()
  dialog.value?.querySelector<HTMLInputElement>('input[name="name"]')?.focus()
}

function closeDialog() {
  if (!saving.value) dialog.value?.close()
}

async function saveTraining() {
  if (saving.value || !form.name.trim() || !form.emoji.trim()) return
  saving.value = true
  try {
    const body = { name: form.name, emoji: form.emoji, category: form.category, permissions: form.permissions }
    if (editingId.value) {
      await $fetch<Training>(`/api/trainings/${editingId.value}`, { method: 'PATCH', body, credentials: 'include' })
    } else {
      await $fetch<Training>('/api/trainings', { method: 'POST', body, credentials: 'include' })
    }
    dialog.value?.close()
    await load()
  } catch (cause) {
    toast.error(messageFromError(cause, 'Enregistrement de la formation impossible.'))
  } finally {
    saving.value = false
  }
}

const deleting = ref<Training | null>(null)
const deleteVisible = ref(false)
const deleteMessage = computed(() => {
  const training = deleting.value
  if (!training) return ''
  const count = validatedFor(training).length
  return count
    ? `L’emoji ${training.emoji} sera retiré des compétences de ${count} employé${count > 1 ? 's' : ''}.`
    : 'Aucun employé ne l’a validée.'
})

function askDelete(training: Training) {
  deleting.value = training
  deleteVisible.value = true
}

async function deleteTraining() {
  const training = deleting.value
  if (!training) return
  try {
    await $fetch(`/api/trainings/${training.id}`, { method: 'DELETE', credentials: 'include' })
    await load()
  } catch (cause) {
    toast.error(messageFromError(cause, 'Suppression de la formation impossible.'))
  } finally {
    deleting.value = null
  }
}

/** Rafraîchissement en arrière-plan, sauf pendant une saisie. */
function refresh() {
  if (saving.value || busy.value.length || dialog.value?.open || deleteVisible.value) return
  void load()
}

// --- Sections repliables : retenues par le navigateur, d'une visite à l'autre ---

const COLLAPSED_KEY = 'bces.poles.collapsed'
const collapsed = reactive<Record<TrainingCategory, boolean>>({ pole: false, specialty: false })

function toggleSection(category: TrainingCategory) {
  collapsed[category] = !collapsed[category]
  try {
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify(collapsed))
  } catch {
    // Stockage indisponible (navigation privée…) : l'état reste pour cette visite.
  }
}

function restoreCollapsed() {
  try {
    const saved = JSON.parse(localStorage.getItem(COLLAPSED_KEY) ?? '{}') as Partial<Record<TrainingCategory, unknown>>
    for (const category of Object.keys(collapsed) as TrainingCategory[]) collapsed[category] = saved[category] === true
  } catch {
    // Valeur illisible ou stockage indisponible : tout reste ouvert.
  }
}

let refreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  restoreCollapsed()
  void load()
  refreshTimer = setInterval(refresh, 10_000)
  window.addEventListener('focus', refresh)
})
onBeforeUnmount(() => {
  clearInterval(refreshTimer)
  window.removeEventListener('focus', refresh)
})
</script>

<template>
  <main class="training-page">
    <section class="training-bar">
      <div class="training-bar__title">
        <span class="training-bar__icon"><Icon name="lucide:badge-check" size="20" /></span>
        <div>
          <h1>Pôles &amp; Spé</h1>
          <p>Valider une formation ajoute son emoji aux compétences de l’employé (Ressources humaines).</p>
        </div>
      </div>
      <div class="training-bar__counts">
        <span><strong>{{ trainings.length }}</strong> formation{{ trainings.length > 1 ? 's' : '' }}</span>
        <span><strong>{{ employees.length }}</strong> employé{{ employees.length > 1 ? 's' : '' }} actif{{ employees.length > 1 ? 's' : '' }}</span>
      </div>
    </section>

    <p v-if="loadError" class="training-error"><Icon name="lucide:circle-alert" size="15" /> {{ loadError }}</p>
    <div v-else-if="!loaded" class="training-empty"><Icon name="lucide:loader-circle" size="20" class="training-spin" /></div>
    <template v-else>
    <section
      v-for="section in sections"
      :key="section.category"
      class="training-section"
      :class="{ 'is-collapsed': collapsed[section.category] }"
    >
      <header class="training-section__head">
        <button
          type="button"
          class="training-section__toggle"
          :aria-expanded="!collapsed[section.category]"
          :aria-controls="`training-section-${section.category}`"
          :title="collapsed[section.category] ? 'Afficher la liste' : 'Réduire la liste'"
          @click="toggleSection(section.category)"
        >
          <Icon name="lucide:chevron-down" size="16" class="training-section__chevron" />
          <span class="training-section__label">
            <span class="training-section__title">{{ section.title }} <span class="training-count">{{ section.trainings.length }}</span></span>
            <span class="training-section__detail">{{ section.detail }}</span>
          </span>
        </button>
        <button v-if="canManage" type="button" class="training-button" @click="openDialog(section.category)">
          <Icon name="lucide:plus" size="14" /> Ajouter
        </button>
      </header>
      <div v-show="!collapsed[section.category]" :id="`training-section-${section.category}`" class="training-section__body">
      <p v-if="!section.trainings.length" class="training-muted">Aucun{{ section.category === 'specialty' ? 'e spécialité' : ' pôle' }}.</p>
      <div v-else class="training-cards">
        <article v-for="training in section.trainings" :key="training.id" class="training-card">
          <header class="training-card__head">
            <span class="training-card__emoji">{{ training.emoji }}</span>
            <div>
              <div class="training-card__title">
                <h3>{{ training.name }}</h3>
                <span
                  v-for="key in training.permissions"
                  :key="key"
                  class="training-right"
                  title="Droit donné à ceux qui ont validé la formation"
                ><Icon name="lucide:key-round" size="11" /> {{ permissionLabel(key) }}</span>
              </div>
              <p>{{ validatedFor(training).length }} validé{{ validatedFor(training).length > 1 ? 's' : '' }}</p>
            </div>
            <span v-if="canManage" class="training-head__actions">
              <button type="button" :aria-label="`Modifier ${training.name}`" title="Modifier" @click="openDialog(section.category, training)"><Icon name="lucide:pencil" size="13" /></button>
              <button type="button" class="is-danger" :aria-label="`Supprimer ${training.name}`" title="Supprimer" @click="askDelete(training)"><Icon name="lucide:trash-2" size="13" /></button>
            </span>
          </header>
          <ul v-if="rosterFor(training).length" class="training-roster">
            <li v-for="row in rosterFor(training)" :key="row.employee.id" class="training-roster__row">
              <select
                v-if="canEditRow(training, row.status)"
                class="training-status"
                :class="`is-${row.status}`"
                :value="row.status"
                :disabled="busy.includes(`${training.id}:${row.employee.id}`)"
                :aria-label="`Rôle de ${row.employee.name}`"
                @change="setStatus(training, row.employee, ($event.target as HTMLSelectElement).value as MemberStatus)"
              >
                <option v-for="status in assignableStatuses(training)" :key="status.value" :value="status.value">{{ status.label }}</option>
              </select>
              <span v-else class="training-status" :class="`is-${row.status}`">{{ STATUSES[STATUS_RANK[row.status]]?.label }}</span>
              <span class="training-roster__name">{{ row.employee.name }}</span>
              <span class="training-roster__phone">{{ row.employee.phone || '—' }}</span>
              <button
                v-if="canEditRow(training, row.status)"
                type="button"
                class="training-roster__remove"
                :disabled="busy.includes(`${training.id}:${row.employee.id}`)"
                :aria-label="`Retirer ${row.employee.name} de la formation`"
                title="Retirer de la formation"
                @click="setStatus(training, row.employee, null)"
              ><Icon name="lucide:x" size="12" /></button>
            </li>
          </ul>
          <p v-else class="training-muted">Personne pour l’instant.</p>
          <div v-if="canEditRoster(training) && candidatesFor(training).length" class="training-add">
            <select
              :value="addStatus[training.id] ?? 'validated'"
              :aria-label="`Rôle à donner dans ${training.name}`"
              @change="addStatus[training.id] = ($event.target as HTMLSelectElement).value as MemberStatus"
            >
              <option v-for="status in assignableStatuses(training)" :key="status.value" :value="status.value">{{ status.label }}</option>
            </select>
            <select value="" :aria-label="`Ajouter un employé à ${training.name}`" @change="onAddSelect(training, $event)">
              <option value="">+ Ajouter un employé…</option>
              <option v-for="employee in candidatesFor(training)" :key="employee.id" :value="employee.id">
                {{ employee.name }}{{ employee.grade_name ? ` · ${employee.grade_name}` : '' }}
              </option>
            </select>
          </div>
        </article>
      </div>
      </div>
    </section>
    </template>

    <dialog ref="dialog" class="training-dialog" aria-labelledby="training-dialog-title" @cancel.prevent="closeDialog">
      <form @submit.prevent="saveTraining">
        <header class="training-dialog__head">
          <div>
            <h2 id="training-dialog-title">{{ editingId ? 'Modifier la formation' : 'Ajouter une formation' }}</h2>
            <p>{{ CATEGORY_LABELS[form.category] }}</p>
          </div>
          <button type="button" class="training-dialog__close" aria-label="Fermer" :disabled="saving" @click="closeDialog">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>
        <div class="training-form">
          <EmojiField v-model="form.emoji" label="Emoji" :maxlength="16" />
          <label>
            <span>Nom de la formation</span>
            <input v-model="form.name" name="name" required maxlength="64" placeholder="Ex. Pilote Medicopter">
          </label>
          <fieldset class="training-rights-field">
            <legend>Droits donnés à ceux qui l’ont validée</legend>
            <label
              v-for="option in permissionOptions"
              :key="option.key"
              class="training-right-option"
              :class="{ 'is-selected': form.permissions.includes(option.key) }"
            >
              <input v-model="form.permissions" type="checkbox" :value="option.key">
              <span class="training-right-option__text">
                <strong>{{ option.label }}</strong>
                <small v-if="PERMISSION_HINTS[option.key]">{{ PERMISSION_HINTS[option.key] }}</small>
              </span>
            </label>
            <p class="training-muted">Le compte lié à la tuile de l’employé reçoit ces droits tant qu’il a l’emoji de la formation.</p>
          </fieldset>
          <p v-if="editingId" class="training-muted">Un nouvel emoji remplace l’ancien chez les employés qui ont validé la formation.</p>
        </div>
        <footer class="training-dialog__foot">
          <button type="button" class="training-button" :disabled="saving" @click="closeDialog">Annuler</button>
          <button type="submit" class="training-button training-button--primary" :disabled="saving || !form.name.trim() || !form.emoji.trim()">
            <Icon :name="saving ? 'lucide:loader-circle' : 'lucide:save'" size="14" :class="{ 'training-spin': saving }" />
            {{ saving ? 'Enregistrement…' : editingId ? 'Enregistrer' : 'Créer la formation' }}
          </button>
        </footer>
      </form>
    </dialog>

    <ConfirmDialog
      v-model:visible="deleteVisible"
      :title="deleting ? `Supprimer « ${deleting.emoji} ${deleting.name} » ?` : 'Supprimer la formation ?'"
      :message="deleteMessage"
      confirm-label="Supprimer"
      danger
      @confirm="deleteTraining"
      @cancel="deleting = null"
    />
  </main>
</template>

<style scoped>
.training-page { display: flex; flex: 1; min-height: 0; flex-direction: column; gap: 12px; overflow: auto; padding: 16px; background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }

.training-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 14px 22px; padding: 14px 16px; border: 1px solid var(--dp-line); border-radius: 16px; background: var(--dp-panel); }
.training-bar__title { display: flex; flex: 1; align-items: center; gap: 11px; min-width: 240px; }
.training-bar__icon { display: grid; width: 38px; height: 38px; flex-shrink: 0; place-items: center; border: 1px solid var(--dp-accent-line); border-radius: 11px; color: var(--dp-accent); background: var(--dp-accent-soft); }
.training-bar h1 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
.training-bar__title p { margin: 3px 0 0; color: var(--dp-text-dim); font-size: 11px; }
.training-bar__counts { display: flex; gap: 14px; color: var(--dp-text-2); font-size: 11px; }
.training-bar__counts strong { color: var(--dp-text); font-size: 14px; font-variant-numeric: tabular-nums; }

.training-button { display: inline-flex; min-height: 34px; align-items: center; gap: 7px; padding: 0 13px; border: 1px solid var(--dp-line-strong); border-radius: 9px; color: var(--dp-text); background: var(--dp-panel-2); font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; }
.training-button:disabled { opacity: .5; cursor: not-allowed; }
.training-button--primary { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }

.training-section { display: grid; gap: 12px; min-width: 0; padding: 14px 16px; border: 1px solid var(--dp-line); border-radius: 16px; background: var(--dp-panel); }
.training-section__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.training-section__label { display: grid; gap: 3px; min-width: 0; }
.training-section__title { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--dp-text); font-size: 14px; font-weight: 700; }
.training-section__detail { color: var(--dp-text-dim); font-size: 11px; }
/* Titre cliquable : réduit ou rouvre la liste. */
.training-section__toggle { display: flex; flex: 1; align-items: flex-start; gap: 8px; min-width: 0; margin: -4px; padding: 4px; border: 0; border-radius: 9px; color: inherit; background: transparent; font: inherit; text-align: left; cursor: pointer; }
.training-section__toggle:hover { background: var(--dp-panel-2); }
.training-section__toggle:focus-visible { outline: 2px solid var(--dp-accent-line); outline-offset: 1px; }
.training-section__chevron { flex-shrink: 0; margin-top: 1px; color: var(--dp-text-2); transition: transform .15s; }
.training-section.is-collapsed .training-section__chevron { transform: rotate(-90deg); }
.training-section__body { display: grid; gap: 12px; min-width: 0; }
.training-count { padding: 1px 8px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-dim); font-size: 10px; font-weight: 600; }
.training-muted { margin: 0; color: var(--dp-text-dim); font-size: 11px; }
.training-error { display: flex; align-items: center; gap: 8px; margin: 0; padding: 12px 14px; border: 1px solid var(--dp-danger-line); border-radius: 12px; color: var(--dp-danger); background: var(--dp-danger-soft); font-size: 12px; }
.training-empty { display: grid; min-height: 160px; place-items: center; color: var(--dp-text-dim); }
.training-spin { animation: training-spin 1s linear infinite; }
@keyframes training-spin { to { transform: rotate(360deg); } }

.training-head__actions { display: inline-flex; gap: 2px; }
.training-head__actions button { display: grid; width: 22px; height: 22px; place-items: center; border: 0; border-radius: 6px; color: var(--dp-text-dim); background: transparent; cursor: pointer; }
.training-head__actions button:hover { color: var(--dp-text); background: var(--dp-panel); }
.training-head__actions button.is-danger:hover { color: var(--dp-danger); background: var(--dp-danger-soft); }

.training-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(380px, 100%), 1fr)); gap: 10px; }
.training-card { display: grid; align-content: start; gap: 10px; padding: 12px; border: 1px solid var(--dp-line); border-radius: 12px; background: var(--dp-panel-2); }
.training-card__head { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px; }
.training-card__emoji { display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid var(--dp-line); border-radius: 10px; background: var(--dp-bg); font-size: 19px; }
/* Nom de la formation et, à côté, les droits qu'elle donne. */
.training-card__title { display: flex; align-items: center; gap: 6px; min-width: 0; }
.training-card h3 { min-width: 0; margin: 0; overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.training-card__head p { margin: 2px 0 0; color: var(--dp-text-dim); font-size: 10px; }
.training-right { display: inline-flex; flex-shrink: 0; white-space: nowrap; align-items: center; gap: 4px; padding: 2px 8px; border: 1px solid color-mix(in srgb, var(--dp-info) 45%, transparent); border-radius: 999px; color: var(--dp-info); background: var(--dp-info-soft); font-size: 10px; font-weight: 650; }
.training-roster { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
/* Le nom du médecin a toute la place restante et passe à la ligne plutôt que d'être coupé. */
.training-roster__row { display: grid; grid-template-columns: 104px minmax(0, 1fr) auto auto; align-items: center; gap: 8px; min-height: 28px; font-size: 11px; }
.training-roster__name { min-width: 0; color: var(--dp-text); font-size: 12px; font-weight: 600; overflow-wrap: anywhere; }
.training-roster__phone { color: var(--dp-text-2); font-variant-numeric: tabular-nums; white-space: nowrap; }
.training-roster__remove { display: grid; width: 22px; height: 22px; place-items: center; border: 0; border-radius: 50%; color: var(--dp-text-dim); background: transparent; cursor: pointer; }
.training-roster__remove:hover { color: var(--dp-danger); background: var(--dp-danger-soft); }
/* Rôle : Responsable et Second en jaune, Validé en vert, En cours en gris. */
.training-status { box-sizing: border-box; width: 104px; min-height: 24px; padding: 0 6px; border: 1px solid var(--dp-line); border-radius: 999px; color: var(--dp-text-2); background: var(--dp-bg); font: inherit; font-size: 10px; font-weight: 650; text-align: center; }
span.training-status { display: inline-grid; place-items: center; }
.training-status.is-lead, .training-status.is-second { border-color: color-mix(in srgb, var(--dp-warn) 55%, transparent); color: var(--dp-warn); background: var(--dp-warn-soft); }
/* La liste déroulante garde le style des autres listes : texte clair sur fond sombre. */
.training-status option { color: var(--dp-text); background: var(--dp-bg); font-weight: 500; }
.training-status.is-validated { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.training-add { display: grid; grid-template-columns: 104px minmax(0, 1fr); gap: 8px; padding-top: 8px; border-top: 1px solid var(--dp-line); }
.training-add select { min-height: 32px; min-width: 0; padding: 0 9px; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; }

.training-dialog { position: fixed; inset: 50% auto auto 50%; width: min(520px, calc(100vw - 24px)); max-height: 90dvh; margin: 0; overflow: auto; transform: translate(-50%, -50%); padding: 0; border: 1px solid var(--dp-line-strong); border-radius: 16px; color: var(--dp-text); background: var(--dp-panel); box-shadow: 0 24px 80px rgba(0, 0, 0, .55); }
.training-dialog::backdrop { background: rgba(0, 0, 0, .55); }
.training-dialog__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 18px; border-bottom: 1px solid var(--dp-line); }
.training-dialog__head h2 { margin: 0; font-size: 15px; }
.training-dialog__head p { margin: 3px 0 0; color: var(--dp-text-dim); font-size: 11px; }
.training-dialog__close { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text-2); background: transparent; cursor: pointer; }
/* « dense » : le nom reste à côté de l'emoji quand le menu des emojis s'ouvre en dessous. */
.training-form { display: grid; grid-template-columns: 80px minmax(0, 1fr); grid-auto-flow: row dense; gap: 12px; padding: 16px 18px; }
.training-form > label { display: grid; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.training-form input:not([type='radio']):not([type='checkbox']) { width: 100%; min-height: 36px; box-sizing: border-box; padding: 0 10px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.training-rights-field, .training-form > .training-muted { grid-column: 1 / -1; }
.training-rights-field { display: grid; gap: 6px; min-width: 0; margin: 0; padding: 0; border: 0; }
.training-rights-field legend { margin-bottom: 6px; padding: 0; color: var(--dp-text-2); font-size: 10px; }
.training-rights-field > .training-muted { margin-top: 2px; font-size: 10px; }
.training-right-option { display: flex; align-items: center; gap: 11px; padding: 9px 12px; border: 1px solid var(--dp-line); border-radius: 10px; background: var(--dp-bg); cursor: pointer; transition: border-color .15s, background-color .15s; }
.training-right-option:hover { border-color: var(--dp-line-strong); }
.training-right-option.is-selected { border-color: var(--dp-accent-line); background: var(--dp-accent-soft); }
.training-right-option input { flex-shrink: 0; width: 16px; height: 16px; margin: 0; accent-color: var(--dp-accent); cursor: pointer; }
.training-right-option__text { display: grid; gap: 2px; min-width: 0; }
.training-right-option__text strong { color: var(--dp-text); font-size: 12px; }
.training-right-option__text small { color: var(--dp-text-dim); font-size: 10px; }
.training-dialog__foot { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 18px; border-top: 1px solid var(--dp-line); }

@media (max-width: 640px) {
  .training-page { padding: 12px; }
  .training-section__head { flex-direction: column; }
  .training-form { grid-template-columns: 1fr; }
}
</style>
