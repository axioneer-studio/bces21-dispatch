<script setup lang="ts">
import type { Agent } from '~/utils/agent'
import { sortAgentsByGradeAndArrival } from '~/utils/agent'

definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Ressources humaines · BCES' })

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
const savingEmployee = ref(false)
const editingEmployeeId = ref<number | null>(null)
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
        employee.account_username,
        ...employee.competencies
      ].join(' ').toLocaleLowerCase('fr')
      return !query || text.includes(query)
    })
  )
})

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

function editEmployee(employee: Agent) {
  editingEmployeeId.value = employee.id
  employeeForm.first_name = employee.first_name
  employeeForm.last_name = employee.last_name
  employeeForm.phone = employee.phone ?? ''
  employeeForm.email = employee.email ?? ''
  employeeForm.arrival_date = employee.arrival_date ?? ''
  employeeForm.competencies = employee.competencies.join(', ')
  employeeForm.grade_id = employee.grade_id ? String(employee.grade_id) : ''
  actionError.value = ''
  document.querySelector('.hr-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

async function saveEmployee() {
  if (savingEmployee.value) return
  actionError.value = ''
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
    resetEmployeeForm()
  } catch (cause) {
    actionError.value = messageFromError(cause, 'Enregistrement de l’employé impossible.')
  } finally {
    savingEmployee.value = false
  }
}

async function saveEmployeeAccountLink(employee: Agent) {
  actionError.value = ''
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
  actionError.value = ''
  try {
    const updated = await $fetch<Agent>(`/api/employees/${employee.id}`, {
      method: 'PATCH',
      body: { is_active: !employee.is_active },
      credentials: 'include'
    })
    employees.value.splice(employees.value.findIndex((item) => item.id === updated.id), 1, updated)
  } catch (cause) {
    actionError.value = messageFromError(cause, 'Changement de statut impossible.')
  }
}

async function deleteEmployee(employee: Agent) {
  if (!window.confirm(`Supprimer définitivement ${employee.first_name} ${employee.last_name} ?`)) return
  actionError.value = ''
  try {
    await $fetch(`/api/employees/${employee.id}`, { method: 'DELETE', credentials: 'include' })
    employees.value = employees.value.filter((item) => item.id !== employee.id)
    if (editingEmployeeId.value === employee.id) resetEmployeeForm()
  } catch (cause) {
    actionError.value = messageFromError(cause, 'Suppression de l’employé impossible.')
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
      <div class="hr-total">
        <Icon name="lucide:users-round" size="19" />
        <strong>{{ employees.filter((employee) => employee.is_active).length }}</strong>
        <span>employés actifs</span>
      </div>
    </header>

    <div v-if="actionError" class="hr-error" role="alert">
      <Icon name="lucide:circle-alert" size="17" />
      <span>{{ actionError }}</span>
      <button type="button" aria-label="Fermer" @click="actionError = ''"><Icon name="lucide:x" size="15" /></button>
    </div>

    <section class="hr-section">
      <div class="hr-section__heading">
        <div>
          <h2>Employés</h2>
          <p>Les employés peuvent être ajoutés avant d’avoir un compte utilisateur.</p>
        </div>
        <label class="hr-filter">
          <Icon name="lucide:search" size="15" />
          <input v-model="search" type="search" placeholder="Rechercher un employé">
        </label>
      </div>

      <form v-if="canManageEmployees" class="hr-form" @submit.prevent="saveEmployee">
        <div class="hr-form__title">
          <h3>{{ editingEmployeeId ? 'Modifier un employé' : 'Créer une tuile employé' }}</h3>
          <button v-if="editingEmployeeId" type="button" class="hr-quiet" @click="resetEmployeeForm">Annuler</button>
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
          <label>
            <span>Grade</span>
            <select v-model="employeeForm.grade_id">
              <option value="">Aucun grade</option>
              <option v-for="grade in grades" :key="grade.id" :value="String(grade.id)">
                {{ grade.name }} · niveau {{ grade.level }}
              </option>
            </select>
          </label>
          <button class="hr-primary" type="submit" :disabled="savingEmployee || !employeeForm.first_name.trim()">
            <Icon :name="savingEmployee ? 'lucide:loader-circle' : 'lucide:plus'" size="16" :class="{ 'hr-spin': savingEmployee }" />
            {{ savingEmployee ? 'Enregistrement…' : editingEmployeeId ? 'Enregistrer' : 'Créer l’employé' }}
          </button>
        </div>
      </form>

      <div class="hr-list__toolbar">
        <span>{{ visibleEmployees.length }} résultat{{ visibleEmployees.length > 1 ? 's' : '' }}</span>
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
                :disabled="(accountLinkSelections[employee.id] ?? '') === (employee.account_user_id ? String(employee.account_user_id) : '')"
                @click="saveEmployeeAccountLink(employee)"
              >
                {{ employee.account_user_id ? 'Enregistrer' : 'Lier le compte' }}
              </button>
            </div>
          </div>
          <div v-if="canManageEmployees" class="hr-employee__actions">
            <button type="button" :aria-label="`Modifier ${employee.first_name}`" title="Modifier" @click="editEmployee(employee)">
              <Icon name="lucide:pencil" size="16" />
            </button>
            <button type="button" :aria-label="employee.is_active ? 'Désactiver' : 'Réactiver'" :title="employee.is_active ? 'Désactiver' : 'Réactiver'" @click="setEmployeeActive(employee)">
              <Icon :name="employee.is_active ? 'lucide:user-round-x' : 'lucide:user-round-check'" size="16" />
            </button>
            <button v-if="!employee.account_user_id" type="button" class="is-danger" :aria-label="`Supprimer ${employee.first_name}`" title="Supprimer" @click="deleteEmployee(employee)">
              <Icon name="lucide:trash-2" size="16" />
            </button>
          </div>
        </article>
      </div>
      <div v-else class="hr-empty">
        <Icon name="lucide:users-round" size="22" />
        <p>Aucun employé ne correspond à cette recherche.</p>
      </div>
    </section>

  </main>
</template>

<style scoped>
.hr-page { flex: 1; min-height: 0; overflow: auto; padding: clamp(18px, 3vw, 36px); background: var(--dp-bg); }
.hr-header, .hr-section { width: min(1120px, 100%); margin: 0 auto; }
.hr-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.hr-eyebrow { margin-bottom: 6px; color: var(--dp-accent); font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.hr-header h1 { margin: 0; font-size: clamp(24px, 3vw, 34px); }
.hr-header p, .hr-section__heading p, .hr-users__heading p { margin: 7px 0 0; color: var(--dp-text-2); font-size: 12px; }
.hr-total { display: grid; grid-template-columns: auto auto; align-items: center; gap: 2px 9px; padding: 12px 15px; border: 1px solid var(--dp-line); background: var(--dp-panel); color: var(--dp-accent); }
.hr-total strong { color: var(--dp-text); font-size: 18px; }
.hr-total span { grid-column: 2; color: var(--dp-text-2); font-size: 10px; }
.hr-section { margin-bottom: 18px; padding: 20px; border: 1px solid var(--dp-line); background: var(--dp-panel); }
.hr-section__heading, .hr-form__title, .hr-list__toolbar, .hr-employee__name, .hr-employee__actions, .hr-role__top, .hr-role__actions, .hr-users__heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.hr-section__heading { margin-bottom: 18px; }
.hr-section h2 { margin: 0; font-size: 17px; }
.hr-section h3 { margin: 0; font-size: 13px; }
.hr-filter { display: flex; align-items: center; gap: 8px; width: min(260px, 100%); padding: 0 10px; border: 1px solid var(--dp-line); color: var(--dp-text-dim); }
.hr-filter input, .hr-fields input, .hr-fields select, .hr-role-create input:not([type='checkbox']), .hr-role input, .hr-user select { width: 100%; min-width: 0; min-height: 36px; border: 1px solid var(--dp-line); border-radius: 4px; outline: none; padding: 0 10px; color: var(--dp-text); background: #101419; font: inherit; font-size: 12px; }
.hr-filter input { min-height: 35px; border: 0; padding: 0; }
.hr-fields input:focus, .hr-fields select:focus, .hr-filter:focus-within, .hr-role input:focus, .hr-user select:focus { border-color: var(--dp-accent); }
.hr-form { margin-bottom: 16px; padding: 16px; border: 1px solid var(--dp-line); background: var(--dp-panel-2); }
.hr-form__title { margin-bottom: 12px; }
.hr-fields { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); align-items: end; gap: 12px; }
.hr-fields > label, .hr-role-create__name, .hr-role__top > label { display: grid; gap: 6px; color: var(--dp-text-2); font-size: 10px; font-weight: 650; }
.hr-fields label i { color: var(--dp-danger); font-style: normal; }
.hr-fields small { color: var(--dp-text-dim); font-weight: 400; }
.hr-account-link { display: flex; flex-wrap: wrap; align-items: end; gap: 8px; margin-top: 8px; }
.hr-account-link label { display: grid; gap: 5px; width: min(390px, 100%); color: var(--dp-text-2); font-size: 10px; font-weight: 650; }
.hr-account-link select { min-height: 32px; border: 1px solid var(--dp-line); border-radius: 4px; padding: 0 8px; color: var(--dp-text); background: #101419; font: inherit; font-size: 11px; }
.hr-account-link .hr-quiet:disabled { cursor: not-allowed; opacity: .5; }
.hr-primary, .hr-quiet, .hr-danger { display: inline-flex; min-height: 36px; align-items: center; justify-content: center; gap: 7px; padding: 0 12px; border: 1px solid transparent; border-radius: 4px; font-size: 11px; font-weight: 700; cursor: pointer; }
.hr-primary { color: #0c1710; background: var(--dp-accent); }
.hr-primary:disabled { cursor: not-allowed; opacity: .5; }
.hr-quiet { border-color: var(--dp-line); color: var(--dp-text-2); background: transparent; }
.hr-danger { color: var(--dp-danger); background: var(--dp-danger-soft); }
.hr-list__toolbar { margin: 16px 0 8px; color: var(--dp-text-dim); font-size: 10px; }
.hr-list__toolbar label, .hr-role-create fieldset label, .hr-role fieldset label, .hr-user__admin { display: inline-flex; align-items: center; gap: 6px; color: var(--dp-text-2); font-size: 10px; font-weight: 500; }
.hr-list { display: grid; gap: 6px; }
.hr-employee { display: flex; align-items: center; gap: 12px; min-width: 0; padding: 11px; border: 1px solid var(--dp-line); background: #151a1f; }
.hr-employee.is-inactive { opacity: .64; }
.hr-employee__avatar { display: grid; width: 38px; height: 38px; flex: 0 0 38px; place-items: center; border: 1px solid var(--dp-accent-line); border-radius: 50%; color: var(--dp-accent); background: var(--dp-accent-soft); }
.hr-employee__main { flex: 1; min-width: 0; }
.hr-employee__name { justify-content: flex-start; }
.hr-employee__name h3 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hr-status { padding: 3px 7px; border-radius: 10px; color: var(--dp-accent); background: var(--dp-accent-soft); font-size: 9px; }
.hr-status.is-inactive { color: var(--dp-text-2); background: var(--dp-panel-3); }
.hr-employee__meta { display: flex; flex-wrap: wrap; gap: 3px 12px; margin: 4px 0; color: var(--dp-text-dim); font-size: 10px; }
.hr-email { display: inline-flex; align-items: center; gap: 4px; }.hr-email button { display: inline-grid; width: 20px; height: 20px; place-items: center; color: var(--dp-text-2); }.hr-email button:hover { color: var(--dp-accent); }
.hr-grade { display: inline-flex; align-items: center; gap: 5px; }.hr-grade i { width: 7px; height: 7px; border-radius: 50%; background: var(--hr-grade-color); }
.hr-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.hr-tags span { padding: 2px 6px; border: 1px solid var(--dp-line); border-radius: 3px; color: var(--dp-text-2); font-size: 10px; }
.hr-employee__actions { gap: 4px; }
.hr-employee__actions button { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 4px; color: var(--dp-text-dim); }
.hr-employee__actions button:hover { color: var(--dp-accent); background: var(--dp-accent-soft); }
.hr-employee__actions button.is-danger:hover { color: var(--dp-danger); background: var(--dp-danger-soft); }
.hr-empty { display: grid; min-height: 90px; place-content: center; justify-items: center; gap: 8px; color: var(--dp-text-dim); font-size: 11px; }
.hr-error { display: flex; align-items: center; gap: 9px; width: min(1120px, 100%); margin: 0 auto 12px; padding: 10px 12px; border: 1px solid var(--dp-danger-line); color: #f0a29d; background: var(--dp-danger-soft); font-size: 11px; }
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
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@keyframes hr-spin { to { transform: rotate(360deg); } }
@media (max-width: 900px) { .hr-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); }.hr-role-create { grid-template-columns: 1fr; }.hr-role-create .hr-primary { justify-self: start; } }
@media (max-width: 600px) {
  .hr-page { padding: 14px; }
  .hr-header { align-items: flex-start; flex-direction: column; }
  .hr-total { display: none; }
  .hr-section { padding: 13px; }
  .hr-section__heading { align-items: flex-start; flex-direction: column; }
  .hr-filter { width: 100%; }
  .hr-fields { grid-template-columns: 1fr 1fr; gap: 9px; }
  .hr-fields > .hr-primary { grid-column: span 2; }
  .hr-employee { align-items: flex-start; gap: 8px; padding: 9px; }
  .hr-employee__avatar { width: 30px; height: 30px; flex-basis: 30px; }
  .hr-employee__actions { flex-direction: column; }
  .hr-user { grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
  .hr-user__role { grid-column: 1 / -1; grid-row: 2; }
}
</style>
