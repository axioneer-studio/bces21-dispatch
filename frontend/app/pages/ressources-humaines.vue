<script setup lang="ts">
import type { Agent } from '~/utils/agent'
import { sortAgentsByGradeAndArrival } from '~/utils/agent'

definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Ressources humaines • BCES' })

interface AccountOption {
  id: number
  name: string
  discord_username: string
}

interface GradeOption {
  id: number
  name: string
  level: number
  color: string
}

interface CurrentUser {
  is_super_admin: boolean
  app_permissions: string[]
  grade_permissions: string[]
}

const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
const { data: currentUser } = await useAsyncData('hr-current-user', () =>
  $fetch<CurrentUser>('/api/me', {
    credentials: 'include',
    headers: requestHeaders
  })
)
const canManageEmployees = computed(() =>
  currentUser.value?.is_super_admin ||
  currentUser.value?.grade_permissions.includes('human_resources.manage_employees')
)
const canLinkAccounts = computed(() =>
  currentUser.value?.is_super_admin ||
  currentUser.value?.app_permissions.includes('human_resources.link_accounts')
)
const [{ data: initialEmployees }, { data: initialGrades }] = await Promise.all([
  useAsyncData('hr-employees', () =>
    $fetch<Agent[]>('/api/employees', {
      credentials: 'include',
      headers: requestHeaders
    })
  ),
  useAsyncData('hr-grades', () =>
    $fetch<GradeOption[]>('/api/employee-grades', {
      credentials: 'include',
      headers: requestHeaders
    })
  )
])
const { data: accounts } = await useAsyncData('hr-accounts', () =>
  canLinkAccounts.value
    ? $fetch<AccountOption[]>('/api/employee-accounts', {
        credentials: 'include',
        headers: requestHeaders
      })
    : Promise.resolve([])
)

const employees = ref<Agent[]>(initialEmployees.value ?? [])
const accountOptions = accounts.value ?? []
const grades = initialGrades.value ?? []
const accountLinkSelections = reactive<Record<number, string>>({})
for (const employee of employees.value) {
  accountLinkSelections[employee.id] = employee.account_user_id ? String(employee.account_user_id) : ''
}
const actionError = ref('')
const employeeDialogError = ref('')
const savingEmployee = ref(false)
const workingEmployeeIds = ref<number[]>([])
const editingEmployeeId = ref<number | null>(null)
const employeeDialog = ref<HTMLDialogElement | null>(null)
const search = ref('')
const showInactive = ref(false)
const revealedEmails = ref<number[]>([])
const employeeForm = reactive({
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  arrival_date: '',
  competencies: '',
  grade_id: ''
})

const visibleEmployees = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('fr')
  return sortAgentsByGradeAndArrival(
    employees.value.filter((employee) => {
      if (!showInactive.value && !employee.is_active) return false
      const text = [
        employee.first_name,
        employee.last_name,
        employee.phone,
        employee.email,
        employee.account_username,
        employee.grade_name,
        ...employee.competencies
      ].join(' ').toLocaleLowerCase('fr')
      return !query || text.includes(query)
    })
  )
})
const activeEmployeeCount = computed(() => employees.value.filter((employee) => employee.is_active).length)
const inactiveEmployeeCount = computed(() => employees.value.length - activeEmployeeCount.value)

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === 'object' && cause !== null && 'data' in cause) {
    const data = cause.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
  }
  return fallback
}

function resetEmployeeForm() {
  editingEmployeeId.value = null
  employeeForm.first_name = ''
  employeeForm.last_name = ''
  employeeForm.phone = ''
  employeeForm.email = ''
  employeeForm.arrival_date = ''
  employeeForm.competencies = ''
  employeeForm.grade_id = ''
}

async function openEmployeeDialog(employee?: Agent) {
  resetEmployeeForm()
  employeeDialogError.value = ''
  if (employee) {
    editingEmployeeId.value = employee.id
    employeeForm.first_name = employee.first_name
    employeeForm.last_name = employee.last_name
    employeeForm.phone = employee.phone ?? ''
    employeeForm.email = employee.email ?? ''
    employeeForm.arrival_date = employee.arrival_date ?? ''
    employeeForm.competencies = employee.competencies.join(', ')
    employeeForm.grade_id = employee.grade_id ? String(employee.grade_id) : ''
  }
  actionError.value = ''
  await nextTick()
  if (!employeeDialog.value?.open) employeeDialog.value?.showModal()
  employeeDialog.value?.querySelector<HTMLInputElement>('[autocomplete="given-name"]')?.focus()
}

function closeEmployeeDialog() {
  if (savingEmployee.value) return
  employeeDialog.value?.close()
}

function onEmployeeDialogClose() {
  resetEmployeeForm()
  employeeDialogError.value = ''
}

async function saveEmployee() {
  if (savingEmployee.value) return
  employeeDialogError.value = ''
  savingEmployee.value = true
  const payload = {
    first_name: employeeForm.first_name.trim(),
    last_name: employeeForm.last_name.trim(),
    phone: employeeForm.phone.trim() || null,
    email: employeeForm.email.trim() || null,
    arrival_date: employeeForm.arrival_date || null,
    competencies: [...new Set(employeeForm.competencies.split(',').map((item) => item.trim()).filter(Boolean))],
    grade_id: employeeForm.grade_id ? Number(employeeForm.grade_id) : null
  }
  try {
    const saved = editingEmployeeId.value
      ? await $fetch<Agent>(`/api/employees/${editingEmployeeId.value}`, {
          method: 'PATCH',
          body: payload,
          credentials: 'include'
        })
      : await $fetch<Agent>('/api/employees', {
          method: 'POST',
          body: payload,
          credentials: 'include'
        })
    const existingIndex = employees.value.findIndex((employee) => employee.id === saved.id)
    if (existingIndex < 0) employees.value.push(saved)
    else employees.value.splice(existingIndex, 1, saved)
    accountLinkSelections[saved.id] = saved.account_user_id ? String(saved.account_user_id) : ''
    employeeDialog.value?.close()
  } catch (cause) {
    employeeDialogError.value = messageFromError(cause, 'Enregistrement de l’employé impossible.')
  } finally {
    savingEmployee.value = false
  }
}

async function saveEmployeeAccountLink(employee: Agent) {
  if (workingEmployeeIds.value.includes(employee.id)) return
  actionError.value = ''
  workingEmployeeIds.value.push(employee.id)
  try {
    const accountId = accountLinkSelections[employee.id]
    const updated = await $fetch<Agent>(`/api/employees/${employee.id}/account`, {
      method: 'PATCH',
      body: { account_user_id: accountId ? Number(accountId) : null },
      credentials: 'include'
    })
    employees.value.splice(employees.value.findIndex((item) => item.id === updated.id), 1, updated)
    accountLinkSelections[updated.id] = updated.account_user_id ? String(updated.account_user_id) : ''
  } catch (cause) {
    actionError.value = messageFromError(cause, 'Liaison du compte impossible.')
    accountLinkSelections[employee.id] = employee.account_user_id ? String(employee.account_user_id) : ''
  } finally {
    workingEmployeeIds.value = workingEmployeeIds.value.filter((id) => id !== employee.id)
  }
}

function toggleEmail(employeeId: number) {
  revealedEmails.value = revealedEmails.value.includes(employeeId)
    ? revealedEmails.value.filter((id) => id !== employeeId)
    : [...revealedEmails.value, employeeId]
}

function formatArrivalDate(value: string | null) {
  if (!value) return 'Date d’arrivée non renseignée'
  const [year, month, day] = value.slice(0, 10).split('-')
  return `Arrivée le ${day}/${month}/${year}`
}

async function setEmployeeActive(employee: Agent) {
  if (workingEmployeeIds.value.includes(employee.id)) return
  actionError.value = ''
  workingEmployeeIds.value.push(employee.id)
  try {
    const updated = await $fetch<Agent>(`/api/employees/${employee.id}`, {
      method: 'PATCH',
      body: { is_active: !employee.is_active },
      credentials: 'include'
    })
    employees.value.splice(employees.value.findIndex((item) => item.id === updated.id), 1, updated)
  } catch (cause) {
    actionError.value = messageFromError(cause, 'Changement de statut impossible.')
  } finally {
    workingEmployeeIds.value = workingEmployeeIds.value.filter((id) => id !== employee.id)
  }
}

async function deleteEmployee(employee: Agent) {
  if (!window.confirm(`Supprimer définitivement ${employee.first_name} ${employee.last_name} ?`)) return
  if (workingEmployeeIds.value.includes(employee.id)) return
  actionError.value = ''
  workingEmployeeIds.value.push(employee.id)
  try {
    await $fetch(`/api/employees/${employee.id}`, { method: 'DELETE', credentials: 'include' })
    employees.value = employees.value.filter((item) => item.id !== employee.id)
    if (editingEmployeeId.value === employee.id) closeEmployeeDialog()
  } catch (cause) {
    actionError.value = messageFromError(cause, 'Suppression de l’employé impossible.')
  } finally {
    workingEmployeeIds.value = workingEmployeeIds.value.filter((id) => id !== employee.id)
  }
}

</script>

<template>
  <main class="hr-page">
    <header class="hr-header">
      <div>
        <p class="hr-eyebrow">BCES · ÉQUIPE</p>
        <h1>Ressources humaines</h1>
        <p>Gérez les employés, leurs compétences et leur grade de service.</p>
      </div>
      <div class="hr-overview" aria-label="Effectifs">
        <div class="hr-total">
          <Icon name="lucide:users-round" size="18" />
          <strong>{{ activeEmployeeCount }}</strong>
          <span>actifs</span>
        </div>
        <div class="hr-total hr-total--muted">
          <Icon name="lucide:user-round-x" size="18" />
          <strong>{{ inactiveEmployeeCount }}</strong>
          <span>inactifs</span>
        </div>
      </div>
    </header>

    <div v-if="actionError" class="hr-error" role="alert">
      <Icon name="lucide:circle-alert" size="17" />
      <span>{{ actionError }}</span>
      <button type="button" aria-label="Fermer" @click="actionError = ''"><Icon name="lucide:x" size="15" /></button>
    </div>

    <section class="hr-section">
      <div class="hr-section__heading">
        <div class="hr-section__title">
          <h2>Employés</h2>
          <p>Les employés peuvent être ajoutés avant d’avoir un compte utilisateur.</p>
        </div>
        <div class="hr-section__tools">
          <label class="hr-filter">
            <Icon name="lucide:search" size="15" />
            <input v-model="search" type="search" aria-label="Rechercher dans les employés" placeholder="Nom, compétence, grade…">
          </label>
          <button v-if="canManageEmployees" type="button" class="hr-primary hr-add" @click="openEmployeeDialog()">
            <Icon name="lucide:plus" size="17" /> Ajouter un employé
          </button>
        </div>
      </div>

      <dialog
        v-if="canManageEmployees"
        ref="employeeDialog"
        class="hr-dialog"
        aria-labelledby="hr-dialog-title"
        @click.self="closeEmployeeDialog"
        @keydown.esc.prevent="closeEmployeeDialog"
        @cancel.prevent="closeEmployeeDialog"
        @close="onEmployeeDialogClose"
      >
        <form class="hr-dialog__content" @submit.prevent="saveEmployee">
          <header class="hr-dialog__header">
            <div class="hr-dialog__icon"><Icon :name="editingEmployeeId ? 'lucide:user-round-pen' : 'lucide:user-round-plus'" size="19" /></div>
            <div>
              <p class="hr-eyebrow">BCES · ÉQUIPE</p>
              <h2 id="hr-dialog-title">{{ editingEmployeeId ? 'Modifier un employé' : 'Ajouter un employé' }}</h2>
              <p>Renseignez les informations de l’agent. Vous pourrez les modifier à tout moment.</p>
            </div>
            <button type="button" class="hr-dialog__close" aria-label="Fermer la fenêtre" :disabled="savingEmployee" @click="closeEmployeeDialog">
              <Icon name="lucide:x" size="18" />
            </button>
          </header>
          <div v-if="employeeDialogError" class="hr-error" role="alert">
            <Icon name="lucide:circle-alert" size="17" /><span>{{ employeeDialogError }}</span>
          </div>
          <div class="hr-fields">
            <label>
              <span>Prénom <i>*</i></span>
              <input v-model="employeeForm.first_name" required maxlength="64" autocomplete="given-name">
            </label>
            <label>
              <span>Nom</span>
              <input v-model="employeeForm.last_name" maxlength="64" autocomplete="family-name">
            </label>
            <label>
              <span>Téléphone</span>
              <input v-model="employeeForm.phone" maxlength="20" autocomplete="tel">
            </label>
            <label>
              <span>E-mail</span>
              <input v-model="employeeForm.email" type="email" maxlength="254" autocomplete="email">
            </label>
            <label>
              <span>Date d’arrivée</span>
              <input v-model="employeeForm.arrival_date" type="date">
            </label>
            <label>
              <span>Compétences</span>
              <input v-model="employeeForm.competencies" placeholder="Ex. 🚑, 🩺, 🚒">
            </label>
            <label class="hr-fields__wide">
              <span>Grade</span>
              <select v-model="employeeForm.grade_id">
                <option value="">Aucun grade</option>
                <option v-for="grade in grades" :key="grade.id" :value="String(grade.id)">
                  {{ grade.name }} · niveau {{ grade.level }}
                </option>
              </select>
            </label>
          </div>
          <footer class="hr-dialog__footer">
            <button class="hr-quiet" type="button" :disabled="savingEmployee" @click="closeEmployeeDialog">Annuler</button>
            <button class="hr-primary" type="submit" :disabled="savingEmployee || !employeeForm.first_name.trim()">
              <Icon :name="savingEmployee ? 'lucide:loader-circle' : 'lucide:check'" size="16" :class="{ 'hr-spin': savingEmployee }" />
              {{ savingEmployee ? 'Enregistrement…' : editingEmployeeId ? 'Enregistrer les modifications' : 'Créer l’employé' }}
            </button>
          </footer>
        </form>
      </dialog>

      <div class="hr-list__toolbar">
        <span>{{ visibleEmployees.length }} résultat{{ visibleEmployees.length > 1 ? 's' : '' }} sur {{ employees.length }}</span>
        <label><input v-model="showInactive" type="checkbox"> Afficher les inactifs</label>
      </div>
      <div v-if="visibleEmployees.length" class="hr-list">
        <article v-for="employee in visibleEmployees" :key="employee.id" class="hr-employee" :class="{ 'is-inactive': !employee.is_active }">
          <div class="hr-employee__avatar"><Icon name="lucide:user-round" size="19" /></div>
          <div class="hr-employee__main">
            <div class="hr-employee__name">
              <h3>{{ employee.first_name }} {{ employee.last_name }}</h3>
              <span class="hr-status" :class="{ 'is-inactive': !employee.is_active }">{{ employee.is_active ? 'Actif' : 'Inactif' }}</span>
            </div>
            <p class="hr-employee__meta">
              <span>{{ employee.phone || 'Pas de téléphone' }}</span>
              <span>{{ formatArrivalDate(employee.arrival_date) }}</span>
              <span v-if="employee.email" class="hr-email">
                {{ revealedEmails.includes(employee.id) ? employee.email : '••••••••••••' }}
                <button
                  type="button"
                  :aria-label="revealedEmails.includes(employee.id) ? 'Masquer l’e-mail' : 'Afficher l’e-mail'"
                  :title="revealedEmails.includes(employee.id) ? 'Masquer l’e-mail' : 'Afficher l’e-mail'"
                  @click="toggleEmail(employee.id)"
                >
                  <Icon :name="revealedEmails.includes(employee.id) ? 'lucide:eye-off' : 'lucide:eye'" size="13" />
                </button>
              </span>
              <span v-else>Aucun e-mail</span>
              <span>{{ employee.account_username ? `Compte : ${employee.account_username}` : 'Sans compte lié' }}</span>
              <span class="hr-grade" :style="employee.grade_color ? { '--hr-grade-color': employee.grade_color } : undefined">
                <i v-if="employee.grade_color" aria-hidden="true"></i>
                {{ employee.grade_name ? `${employee.grade_name} · niveau ${employee.grade_level}` : 'Aucun grade' }}
              </span>
            </p>
            <div v-if="employee.competencies.length" class="hr-tags">
              <span v-for="skill in employee.competencies" :key="skill">{{ skill }}</span>
            </div>
            <div v-if="canLinkAccounts" class="hr-account-link">
              <label>
                <span>Compte associé</span>
                <select v-model="accountLinkSelections[employee.id]">
                  <option value="">Aucun compte lié</option>
                  <option v-for="account in accountOptions" :key="account.id" :value="String(account.id)">
                    {{ account.name }} · {{ account.discord_username }}
                  </option>
                </select>
              </label>
              <button
                type="button"
                class="hr-quiet"
                :disabled="workingEmployeeIds.includes(employee.id) || (accountLinkSelections[employee.id] ?? '') === (employee.account_user_id ? String(employee.account_user_id) : '')"
                @click="saveEmployeeAccountLink(employee)"
              >
                {{ workingEmployeeIds.includes(employee.id) ? 'Enregistrement…' : employee.account_user_id ? 'Enregistrer' : 'Lier le compte' }}
              </button>
            </div>
          </div>
          <div v-if="canManageEmployees" class="hr-employee__actions">
            <button type="button" :aria-label="`Modifier ${employee.first_name}`" title="Modifier" :disabled="workingEmployeeIds.includes(employee.id)" @click="openEmployeeDialog(employee)">
              <Icon name="lucide:pencil" size="16" />
            </button>
            <button type="button" :aria-label="employee.is_active ? 'Désactiver' : 'Réactiver'" :title="employee.is_active ? 'Désactiver' : 'Réactiver'" :disabled="workingEmployeeIds.includes(employee.id)" @click="setEmployeeActive(employee)">
              <Icon :name="employee.is_active ? 'lucide:user-round-x' : 'lucide:user-round-check'" size="16" />
            </button>
            <button v-if="!employee.account_user_id" type="button" class="is-danger" :aria-label="`Supprimer ${employee.first_name}`" title="Supprimer" :disabled="workingEmployeeIds.includes(employee.id)" @click="deleteEmployee(employee)">
              <Icon name="lucide:trash-2" size="16" />
            </button>
          </div>
        </article>
      </div>
      <div v-else class="hr-empty">
        <Icon :name="search ? 'lucide:search-x' : 'lucide:users-round'" size="22" />
        <p>{{ search ? 'Aucun employé ne correspond à votre recherche.' : showInactive ? 'Aucun employé à afficher.' : 'Aucun employé actif pour le moment.' }}</p>
        <button v-if="search" type="button" class="hr-quiet" @click="search = ''">Effacer la recherche</button>
      </div>
    </section>

  </main>
</template>

<style scoped>
.hr-page { flex: 1; min-height: 0; overflow: auto; padding: clamp(22px, 4vw, 48px); background: var(--dp-bg); }
.hr-header, .hr-section { width: min(1180px, 100%); margin: 0 auto; }
.hr-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.hr-eyebrow { margin-bottom: 9px; color: var(--dp-accent); font-size: 10px; font-weight: 800; letter-spacing: .15em; }
.hr-header h1 { margin: 0; font-size: clamp(28px, 3.2vw, 38px); letter-spacing: -.04em; }
.hr-header p, .hr-section__heading p, .hr-users__heading p { margin: 9px 0 0; color: var(--dp-text-2); font-size: 13px; line-height: 1.6; }
.hr-total { display: grid; min-width: 126px; grid-template-columns: auto auto; align-items: center; gap: 3px 10px; padding: 14px 16px; border: 1px solid var(--dp-line); border-radius: 14px; background: linear-gradient(145deg, rgba(255,255,255,.025), transparent 70%), var(--dp-panel); color: var(--dp-accent); }
.hr-total strong { color: var(--dp-text); font-size: 21px; font-variant-numeric: tabular-nums; }
.hr-total span { grid-column: 2; color: var(--dp-text-2); font-size: 11px; }
.hr-overview { display: flex; gap: 8px; }
.hr-total--muted { color: var(--dp-text-dim); }
.hr-section { margin-bottom: 18px; padding: clamp(18px, 2.5vw, 28px); border: 1px solid var(--dp-line); border-radius: 18px; background: var(--dp-panel); box-shadow: 0 16px 40px rgba(0, 0, 0, .14); }
.hr-section__heading, .hr-form__title, .hr-list__toolbar, .hr-employee__name, .hr-employee__actions, .hr-role__top, .hr-role__actions, .hr-users__heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.hr-section__heading { align-items: flex-end; margin-bottom: 22px; }
.hr-section h2 { margin: 0; font-size: 20px; letter-spacing: -.02em; }
.hr-section h3 { margin: 0; font-size: 14px; }
.hr-filter { display: flex; min-height: 42px; align-items: center; gap: 9px; width: min(300px, 100%); padding: 0 12px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-dim); background: var(--dp-bg); }
.hr-filter input, .hr-fields input, .hr-fields select, .hr-role-create input:not([type='checkbox']), .hr-role input, .hr-user select { width: 100%; min-width: 0; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; outline: none; padding: 0 11px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.hr-filter input { min-height: 38px; border: 0; padding: 0; }
.hr-fields input:focus, .hr-fields select:focus, .hr-filter:focus-within, .hr-role input:focus, .hr-user select:focus { border-color: var(--dp-accent); }
.hr-form { margin-bottom: 16px; padding: 16px; border: 1px solid var(--dp-line); background: var(--dp-panel-2); }
.hr-form__title { margin-bottom: 12px; }
.hr-fields { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); align-items: end; gap: 12px; }
.hr-fields > label, .hr-role-create__name, .hr-role__top > label { display: grid; gap: 6px; color: var(--dp-text-2); font-size: 10px; font-weight: 650; }
.hr-fields label i { color: var(--dp-danger); font-style: normal; }
.hr-fields small { color: var(--dp-text-dim); font-weight: 400; }
.hr-account-link { display: flex; flex-wrap: wrap; align-items: end; gap: 8px; margin-top: 8px; }
.hr-account-link label { display: grid; gap: 5px; width: min(390px, 100%); color: var(--dp-text-2); font-size: 10px; font-weight: 650; }
.hr-account-link select { min-height: 36px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 9px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; }
.hr-account-link .hr-quiet:disabled { cursor: not-allowed; opacity: .5; }
.hr-primary, .hr-quiet, .hr-danger { display: inline-flex; min-height: 40px; align-items: center; justify-content: center; gap: 8px; padding: 0 14px; border: 1px solid transparent; border-radius: 10px; font-size: 11px; font-weight: 700; cursor: pointer; transition: background .16s ease, border-color .16s ease, transform .16s ease; }
.hr-primary { color: #0c1710; background: var(--dp-accent); }
.hr-primary:disabled { cursor: not-allowed; opacity: .5; }
.hr-quiet { border-color: var(--dp-line); color: var(--dp-text-2); background: transparent; }
.hr-danger { color: var(--dp-danger); background: var(--dp-danger-soft); }
.hr-list__toolbar { margin: 22px 0 12px; color: var(--dp-text-dim); font-size: 11px; }
.hr-list__toolbar label, .hr-role-create fieldset label, .hr-role fieldset label, .hr-user__admin { display: inline-flex; align-items: center; gap: 6px; color: var(--dp-text-2); font-size: 10px; font-weight: 500; }
.hr-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 430px), 1fr)); gap: 13px; }
.hr-employee { display: flex; align-items: flex-start; gap: 13px; min-width: 0; padding: 16px; border: 1px solid var(--dp-line); border-radius: 15px; background: var(--dp-panel-2); }
.hr-employee.is-inactive { opacity: .68; }
.hr-employee__avatar { display: grid; width: 42px; height: 42px; flex: 0 0 42px; place-items: center; border: 1px solid var(--dp-accent-line); border-radius: 13px; color: var(--dp-accent); background: var(--dp-accent-soft); }
.hr-employee__main { flex: 1; min-width: 0; }
.hr-employee__name { justify-content: flex-start; }
.hr-employee__name h3 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hr-status { padding: 3px 7px; border-radius: 10px; color: var(--dp-accent); background: var(--dp-accent-soft); font-size: 9px; }
.hr-status.is-inactive { color: var(--dp-text-2); background: var(--dp-panel-3); }
.hr-employee__meta { display: flex; flex-wrap: wrap; gap: 5px 12px; margin: 8px 0; color: var(--dp-text-2); font-size: 11px; line-height: 1.5; }
.hr-email { display: inline-flex; align-items: center; gap: 4px; }.hr-email button { display: inline-grid; width: 20px; height: 20px; place-items: center; color: var(--dp-text-2); }.hr-email button:hover { color: var(--dp-accent); }
.hr-grade { display: inline-flex; align-items: center; gap: 5px; }.hr-grade i { width: 7px; height: 7px; border-radius: 50%; background: var(--hr-grade-color); }
.hr-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.hr-tags span { padding: 4px 9px; border: 1px solid var(--dp-line); border-radius: 999px; color: var(--dp-text-2); background: rgba(255,255,255,.025); font-size: 10px; }
.hr-employee__actions { flex: 0 0 auto; justify-content: flex-end; gap: 5px; }
.hr-employee__actions button { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid transparent; border-radius: 9px; color: var(--dp-text-dim); }
.hr-employee__actions button:hover { color: var(--dp-accent); background: var(--dp-accent-soft); }
.hr-employee__actions button:disabled { cursor: wait; opacity: .45; }
.hr-employee__actions button.is-danger:hover { color: var(--dp-danger); background: var(--dp-danger-soft); }
.hr-empty { display: grid; min-height: 180px; place-content: center; justify-items: center; gap: 10px; border: 1px dashed var(--dp-line-strong); border-radius: 14px; color: var(--dp-text-dim); font-size: 12px; }
.hr-empty p { margin: 0; }
.hr-error { display: flex; align-items: center; gap: 9px; width: min(1180px, 100%); margin: 0 auto 14px; padding: 12px 14px; border: 1px solid var(--dp-danger-line); border-radius: 12px; color: #f0a29d; background: var(--dp-danger-soft); font-size: 12px; }
.hr-error span { flex: 1; }
.hr-error button { color: inherit; }
.hr-super-label { display: inline-flex; align-items: center; gap: 6px; color: var(--dp-accent); font-size: 10px; }
.hr-role-create, .hr-role { display: grid; gap: 12px; padding: 14px; border: 1px solid var(--dp-line); background: var(--dp-panel-2); }
.hr-role-create { grid-template-columns: minmax(150px, .7fr) minmax(0, 2fr) auto; align-items: end; margin-bottom: 10px; }
.hr-role-create fieldset, .hr-role fieldset { display: flex; flex-wrap: wrap; gap: 9px 14px; min-width: 0; margin: 0; padding: 8px; border: 1px solid var(--dp-line); }
.hr-role-create legend, .hr-role legend { padding: 0 5px; color: var(--dp-text-dim); font-size: 9px; }
.hr-role-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr)); gap: 10px; }
.hr-role__top { align-items: end; }
.hr-role__top > label { flex: 1; }
.hr-role__count { color: var(--dp-text-dim); font-size: 10px; }
.hr-role__actions { justify-content: flex-start; }
.hr-users { margin-top: 20px; border-top: 1px solid var(--dp-line); }
.hr-users__heading { justify-content: flex-start; padding: 16px 0 10px; }
.hr-users__heading > div { display: grid; gap: 4px; }
.hr-user { display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, 240px) 140px; align-items: center; gap: 12px; padding: 9px 0; border-top: 1px solid var(--dp-line); }
.hr-user > div { display: grid; gap: 3px; min-width: 0; }
.hr-user strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.hr-user small { color: var(--dp-text-dim); font-size: 9px; }
.hr-user__admin { white-space: nowrap; }
.hr-loading { color: var(--dp-text-dim); font-size: 11px; }
.hr-spin { animation: hr-spin 1s linear infinite; }
.hr-page { background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }
.hr-header { padding: clamp(22px, 3vw, 34px); border: 1px solid var(--dp-line); border-radius: 22px; background: linear-gradient(110deg, rgba(70, 153, 109, .12), transparent 72%), var(--dp-panel); box-shadow: 0 18px 48px rgba(0, 0, 0, .16); }
.hr-header h1 { letter-spacing: -.03em; }
.hr-section { border-color: var(--dp-line); background: linear-gradient(145deg, rgba(255,255,255,.025), transparent 55%), var(--dp-panel); }
.hr-form { border-color: var(--dp-accent-line); }
.hr-employee { transition: border-color .16s ease, background .16s ease; }
.hr-employee:hover { border-color: var(--dp-line-strong); background: #1b2228; }
.hr-fields input:focus-visible, .hr-fields select:focus-visible, .hr-account-link select:focus-visible, .hr-role input:focus-visible, .hr-user select:focus-visible, .hr-filter:focus-within { outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }
.hr-primary:hover:not(:disabled) { filter: brightness(1.08); }
.hr-quiet:hover:not(:disabled) { color: var(--dp-text); border-color: var(--dp-line-strong); background: var(--dp-panel-3); }
.hr-primary:focus-visible, .hr-quiet:focus-visible, .hr-employee__actions button:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: 2px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@keyframes hr-spin { to { transform: rotate(360deg); } }
.hr-section__title { min-width: 180px; }
.hr-section__tools { display: flex; align-items: center; justify-content: flex-end; gap: 9px; }
.hr-add { min-height: 42px; padding: 0 16px; }
.hr-dialog { position: fixed; inset: 50% auto auto 50%; width: min(680px, calc(100vw - 28px)); max-width: 680px; max-height: min(90dvh, 780px); margin: 0; padding: 0; overflow: auto; transform: translate(-50%, -50%); border: 1px solid var(--dp-line-strong); border-radius: 18px; color: var(--dp-text); background: var(--dp-panel); box-shadow: 0 24px 80px rgba(0, 0, 0, .55); }
.hr-dialog::backdrop { background: rgba(5, 8, 11, .76); backdrop-filter: blur(5px); }
.hr-dialog__content { display: grid; gap: 18px; margin: 0; padding: clamp(18px, 4vw, 28px); }
.hr-dialog__header { display: grid; grid-template-columns: 42px minmax(0, 1fr) 34px; align-items: start; gap: 13px; padding-bottom: 17px; border-bottom: 1px solid var(--dp-line); }
.hr-dialog__icon { display: grid; width: 42px; height: 42px; place-items: center; border: 1px solid var(--dp-accent-line); border-radius: 12px; color: var(--dp-accent); background: var(--dp-accent-soft); }
.hr-dialog__header .hr-eyebrow { margin: 1px 0 5px; }
.hr-dialog__header h2 { margin: 0; color: var(--dp-text); font-size: 19px; letter-spacing: -.02em; }
.hr-dialog__header p:last-child { margin: 5px 0 0; color: var(--dp-text-2); font-size: 11px; line-height: 1.5; }
.hr-dialog__close { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid var(--dp-line); color: var(--dp-text-2); background: transparent; cursor: pointer; }
.hr-dialog__close:hover:not(:disabled) { color: var(--dp-text); background: var(--dp-panel-3); }
.hr-dialog__close:disabled { opacity: .5; cursor: wait; }
.hr-dialog .hr-error { width: 100%; margin: 0; }
.hr-dialog .hr-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.hr-dialog .hr-fields > label { font-size: 11px; }
.hr-dialog .hr-fields input, .hr-dialog .hr-fields select { min-height: 40px; font-size: 12px; }
.hr-dialog .hr-fields__wide { grid-column: 1 / -1; }
.hr-dialog__footer { display: flex; justify-content: flex-end; gap: 9px; padding-top: 15px; border-top: 1px solid var(--dp-line); }
.hr-dialog__footer .hr-primary, .hr-dialog__footer .hr-quiet { min-height: 40px; padding: 0 14px; font-size: 11px; }
.hr-dialog[open] { animation: hr-dialog-in .16s ease-out; }
@keyframes hr-dialog-in { from { opacity: 0; transform: translate(-50%, calc(-50% + 8px)) scale(.99); } to { opacity: 1; transform: translate(-50%, -50%) scale(1); } }
@media (max-width: 760px) { .hr-section__heading { align-items: stretch; flex-direction: column; }.hr-section__tools { flex: 1; min-width: 0; flex-wrap: wrap; }.hr-section__tools .hr-filter { flex: 1; }.hr-add { white-space: nowrap; } }
@media (max-width: 900px) { .hr-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); }.hr-role-create { grid-template-columns: 1fr; }.hr-role-create .hr-primary { justify-self: start; } }
@media (max-width: 600px) {
  .hr-page { padding: 14px; }
  .hr-header { align-items: flex-start; flex-direction: column; }
  .hr-overview { width: 100%; }.hr-total { flex: 1; }.hr-total--muted { display: grid; }
  .hr-section { padding: 13px; }
  .hr-section__heading { align-items: stretch; flex-direction: column; }
  .hr-section__tools { width: 100%; flex-direction: column; align-items: stretch; }.hr-filter { width: 100%; }
  .hr-fields { grid-template-columns: 1fr 1fr; gap: 9px; }
  .hr-fields > .hr-primary { grid-column: span 2; }
  .hr-employee { gap: 10px; padding: 13px; }
  .hr-employee__avatar { width: 36px; height: 36px; flex-basis: 36px; }
  .hr-employee__actions { flex-direction: row; }
  .hr-user { grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
  .hr-user__role { grid-column: 1 / -1; grid-row: 2; }
  .hr-dialog { width: calc(100vw - 20px); max-height: 92dvh; }
  .hr-dialog .hr-fields { grid-template-columns: 1fr; }
  .hr-dialog .hr-fields__wide { grid-column: auto; }
  .hr-dialog__header { grid-template-columns: 36px minmax(0, 1fr) 32px; gap: 9px; }
  .hr-dialog__icon { width: 36px; height: 36px; }
  .hr-dialog__footer { flex-direction: column-reverse; }
  .hr-dialog__footer > button { width: 100%; }
}
</style>
