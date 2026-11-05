<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Administration · BCES' })

interface AppRole {
  id: number
  name: string
  pages: string[]
  permissions: string[]
  users_count: number
}

interface AppPermission {
  key: string
  label: string
}

interface AppUser {
  id: number
  discord_username: string
  first_name: string | null
  last_name: string | null
  status: string
  role_id: number | null
  role_name: string | null
  is_super_admin: boolean
  created_at: string
}

interface Registration {
  id: number
  discord_username: string
  discord_avatar: string | null
  prenom_rp: string | null
  nom_rp: string | null
  phone: string | null
  created_at: string
}

interface AppSettings {
  registration_open: boolean
}

const pageOptions = [
  { key: 'dashboard', label: 'Accueil' },
  { key: 'dispatch', label: 'Dispatch' },
  { key: 'agenda', label: 'Agenda' },
  { key: 'human-resources', label: 'Ressources humaines' },
  { key: 'direction', label: 'Direction' },
  { key: 'administration', label: 'Administration' }
]

const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
const [{ data: initialUsers }, { data: initialRoles }, { data: permissionOptions }, { data: initialRequests }, { data: initialSettings }] =
  await Promise.all([
    useAsyncData('admin-users', () =>
      $fetch<AppUser[]>('/api/admin/users', { credentials: 'include', headers: requestHeaders })
    ),
    useAsyncData('admin-roles', () =>
      $fetch<AppRole[]>('/api/admin/roles', { credentials: 'include', headers: requestHeaders })
    ),
    useAsyncData('admin-permissions', () =>
      $fetch<AppPermission[]>('/api/admin/permissions', { credentials: 'include', headers: requestHeaders })
    ),
    useAsyncData('admin-registrations', () =>
      $fetch<{ users: Registration[]; count: number }>('/api/auth/pending', {
        credentials: 'include',
        headers: requestHeaders
      })
    ),
    useAsyncData('admin-settings', () =>
      $fetch<AppSettings>('/api/admin/settings', { credentials: 'include', headers: requestHeaders })
    )
  ])

const users = ref<AppUser[]>(initialUsers.value ?? [])
const roles = ref<AppRole[]>(initialRoles.value ?? [])
const registrations = ref<Registration[]>(initialRequests.value?.users ?? [])
const settings = reactive<AppSettings>(initialSettings.value ?? { registration_open: true })
const roleForm = reactive({ name: '', pages: [] as string[], permissions: [] as string[] })
const error = ref('')
const savingSettings = ref(false)

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === 'object' && cause !== null && 'data' in cause) {
    const data = cause.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
  }
  return fallback
}

async function createRole() {
  error.value = ''
  try {
    const role = await $fetch<AppRole>('/api/admin/roles', {
      method: 'POST',
      body: roleForm,
      credentials: 'include'
    })
    roles.value.push(role)
    roleForm.name = ''
    roleForm.pages = []
    roleForm.permissions = []
  } catch (cause) {
    error.value = messageFromError(cause, 'Création du rôle impossible.')
  }
}

async function saveRole(role: AppRole) {
  error.value = ''
  try {
    const updated = await $fetch<AppRole>(`/api/admin/roles/${role.id}`, {
      method: 'PATCH',
      body: { name: role.name, pages: role.pages, permissions: role.permissions },
      credentials: 'include'
    })
    Object.assign(role, updated)
    await refreshRoles()
  } catch (cause) {
    error.value = messageFromError(cause, 'Modification du rôle impossible.')
  }
}

async function refreshRoles() {
  roles.value = await $fetch<AppRole[]>('/api/admin/roles', { credentials: 'include' })
}

async function deleteRole(role: AppRole) {
  if (!window.confirm(`Supprimer le rôle « ${role.name} » ?`)) return
  error.value = ''
  try {
    await $fetch(`/api/admin/roles/${role.id}`, { method: 'DELETE', credentials: 'include' })
    roles.value = roles.value.filter((item) => item.id !== role.id)
  } catch (cause) {
    error.value = messageFromError(cause, 'Suppression du rôle impossible.')
  }
}

async function assignRole(user: AppUser, event: Event) {
  const rawId = (event.target as HTMLSelectElement).value
  const roleId = rawId ? Number(rawId) : null
  error.value = ''
  try {
    await $fetch(`/api/admin/users/${user.id}/role`, {
      method: 'PATCH',
      body: { role_id: roleId },
      credentials: 'include'
    })
    user.role_id = roleId
    user.role_name = roles.value.find((role) => role.id === roleId)?.name ?? null
  } catch (cause) {
    error.value = messageFromError(cause, 'Attribution du rôle impossible.')
    await refreshUsers()
  }
}

async function refreshUsers() {
  users.value = await $fetch<AppUser[]>('/api/admin/users', { credentials: 'include' })
}

async function setActivation(user: AppUser) {
  const isActive = user.status !== 'active'
  error.value = ''
  try {
    await $fetch(`/api/admin/users/${user.id}/activation`, {
      method: 'PATCH',
      body: { is_active: isActive },
      credentials: 'include'
    })
    user.status = isActive ? 'active' : 'disabled'
  } catch (cause) {
    error.value = messageFromError(cause, 'Modification du compte impossible.')
  }
}

async function deleteUser(user: AppUser) {
  const displayName = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.discord_username
  if (!window.confirm(`Supprimer définitivement le compte de ${displayName} ? Sa tuile employé sera conservée sans compte lié.`)) return
  error.value = ''
  try {
    await $fetch(`/api/admin/users/${user.id}`, {
      method: 'DELETE',
      credentials: 'include'
    })
    users.value = users.value.filter((item) => item.id !== user.id)
    registrations.value = registrations.value.filter((item) => item.id !== user.id)
  } catch (cause) {
    error.value = messageFromError(cause, 'Suppression du compte impossible.')
  }
}

async function resolveRegistration(registration: Registration, action: 'approve' | 'reject') {
  error.value = ''
  try {
    await $fetch(`/api/admin/registrations/${registration.id}/${action}`, {
      method: 'POST',
      credentials: 'include'
    })
    registrations.value = registrations.value.filter((item) => item.id !== registration.id)
    const user = users.value.find((item) => item.id === registration.id)
    if (user) user.status = action === 'approve' ? 'active' : 'rejected'
    else await refreshUsers()
  } catch (cause) {
    error.value = messageFromError(cause, 'Traitement de la demande impossible.')
  }
}

async function saveSettings() {
  savingSettings.value = true
  error.value = ''
  try {
    const saved = await $fetch<AppSettings>('/api/admin/settings', {
      method: 'PUT',
      body: { registration_open: settings.registration_open },
      credentials: 'include'
    })
    settings.registration_open = saved.registration_open
  } catch (cause) {
    error.value = messageFromError(cause, 'Enregistrement des paramètres impossible.')
  } finally {
    savingSettings.value = false
  }
}

function statusLabel(status: string) {
  if (status === 'pending') return 'En attente'
  if (status === 'disabled') return 'Désactivé'
  if (status === 'rejected') return 'Refusé'
  return 'Actif'
}
</script>

<template>
  <main class="admin-page">
    <header class="admin-header">
      <div>
        <p class="admin-eyebrow">BCES · CONFIGURATION</p>
        <h1>Administration</h1>
        <p>Gérez les comptes, les rôles applicatifs et les paramètres de l’application.</p>
      </div>
      <div class="admin-count"><Icon name="lucide:users" size="18" /><strong>{{ users.length }}</strong><span>comptes</span></div>
    </header>

    <div v-if="error" class="admin-error" role="alert">
      <Icon name="lucide:circle-alert" size="17" /><span>{{ error }}</span>
      <button type="button" aria-label="Fermer" @click="error = ''"><Icon name="lucide:x" size="15" /></button>
    </div>

    <section class="admin-section">
      <div class="admin-section__heading">
        <div><h2>Demandes d’inscription</h2><p>{{ registrations.length }} demande{{ registrations.length > 1 ? 's' : '' }} en attente de validation.</p></div>
      </div>
      <article v-for="registration in registrations" :key="registration.id" class="admin-row">
        <div class="admin-row__identity">
          <strong>{{ registration.prenom_rp }} {{ registration.nom_rp }}</strong>
          <small>{{ registration.discord_username }}<span v-if="registration.phone"> · {{ registration.phone }}</span></small>
        </div>
        <div class="admin-row__actions">
          <button type="button" class="admin-button admin-button--allow" @click="resolveRegistration(registration, 'approve')">
            <Icon name="lucide:check" size="14" /> Valider
          </button>
          <button type="button" class="admin-button admin-button--danger" @click="resolveRegistration(registration, 'reject')">
            <Icon name="lucide:x" size="14" /> Refuser
          </button>
        </div>
      </article>
      <div v-if="!registrations.length" class="admin-empty">Aucune demande en attente.</div>
    </section>

    <section class="admin-section">
      <div class="admin-section__heading">
        <div><h2>Utilisateurs</h2><p>Attribuez les rôles applicatifs et gérez l’état des comptes.</p></div>
      </div>
      <article v-for="user in users" :key="user.id" class="admin-row">
        <div class="admin-row__identity">
          <strong>{{ user.first_name || user.discord_username }} {{ user.last_name || '' }}</strong>
          <small>{{ user.discord_username }} · {{ statusLabel(user.status) }}<span v-if="user.is_super_admin"> · Super-admin</span></small>
        </div>
        <label class="admin-role">
          <span class="sr-only">Rôle applicatif de {{ user.discord_username }}</span>
          <select :value="user.role_id ?? ''" @change="assignRole(user, $event)">
            <option value="">Aucun rôle</option>
            <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
          </select>
        </label>
        <button
          v-if="user.status !== 'pending'"
          type="button"
          class="admin-button"
          :class="user.status === 'active' ? 'admin-button--danger' : 'admin-button--allow'"
          @click="setActivation(user)"
        >
          <Icon :name="user.status === 'active' ? 'lucide:user-round-x' : 'lucide:user-round-check'" size="14" />
          {{ user.status === 'active' ? 'Désactiver' : 'Activer' }}
        </button>
        <button
          type="button"
          class="admin-button admin-button--danger"
          :aria-label="`Supprimer le compte de ${user.discord_username}`"
          @click="deleteUser(user)"
        >
          <Icon name="lucide:trash-2" size="14" /> Supprimer
        </button>
      </article>
      <div v-if="!users.length" class="admin-empty">Aucun utilisateur à afficher.</div>
    </section>

    <section class="admin-section">
      <div class="admin-section__heading">
        <div><h2>Rôles applicatifs</h2><p>Définissez les pages accessibles et les actions autorisées pour chaque rôle.</p></div>
      </div>
      <form class="admin-role-create" @submit.prevent="createRole">
        <label><span>Nom du rôle</span><input v-model="roleForm.name" required maxlength="64" placeholder="Ex. RH"></label>
        <fieldset>
          <legend>Pages accessibles</legend>
          <label v-for="page in pageOptions" :key="page.key">
            <input v-model="roleForm.pages" type="checkbox" :value="page.key">{{ page.label }}
          </label>
        </fieldset>
        <fieldset>
          <legend>Permissions applicatives</legend>
          <label v-for="permission in permissionOptions" :key="permission.key">
            <input v-model="roleForm.permissions" type="checkbox" :value="permission.key">{{ permission.label }}
          </label>
        </fieldset>
        <button class="admin-button admin-button--primary" type="submit" :disabled="!roleForm.name.trim()">
          <Icon name="lucide:plus" size="14" /> Créer le rôle
        </button>
      </form>
      <article v-for="role in roles" :key="role.id" class="admin-role-card">
        <div class="admin-role-card__top">
          <label><span>Nom du rôle</span><input v-model="role.name" maxlength="64"></label>
          <small>{{ role.users_count }} utilisateur{{ role.users_count > 1 ? 's' : '' }}</small>
        </div>
        <fieldset>
          <legend>Pages accessibles</legend>
          <label v-for="page in pageOptions" :key="page.key">
            <input v-model="role.pages" type="checkbox" :value="page.key">{{ page.label }}
          </label>
        </fieldset>
        <fieldset>
          <legend>Permissions applicatives</legend>
          <label v-for="permission in permissionOptions" :key="permission.key">
            <input v-model="role.permissions" type="checkbox" :value="permission.key">{{ permission.label }}
          </label>
        </fieldset>
        <div class="admin-row__actions">
          <button type="button" class="admin-button" @click="saveRole(role)"><Icon name="lucide:save" size="14" /> Enregistrer</button>
          <button type="button" class="admin-button admin-button--danger" @click="deleteRole(role)"><Icon name="lucide:trash-2" size="14" /> Supprimer</button>
        </div>
      </article>
      <div v-if="!roles.length" class="admin-empty">Aucun rôle applicatif créé.</div>
    </section>

    <section class="admin-section admin-setting">
      <div class="admin-section__heading">
        <div><h2>Paramètres généraux</h2><p>Contrôlez l’ouverture des nouvelles inscriptions.</p></div>
      </div>
      <label class="admin-toggle">
        <span><strong>Inscriptions ouvertes</strong><small>Autoriser la création de nouveaux comptes via Discord.</small></span>
        <input v-model="settings.registration_open" type="checkbox" @change="saveSettings">
      </label>
      <span v-if="savingSettings" class="admin-muted">Enregistrement…</span>
    </section>
  </main>
</template>

<style scoped>
.admin-page { flex: 1; min-height: 0; overflow: auto; padding: clamp(18px, 3vw, 36px); background: var(--dp-bg); }
.admin-header, .admin-section, .admin-error { width: min(1120px, 100%); margin-right: auto; margin-left: auto; }
.admin-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.admin-eyebrow { margin-bottom: 6px; color: var(--dp-accent); font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.admin-header h1 { margin: 0; font-size: clamp(24px, 3vw, 34px); }
.admin-header p, .admin-section__heading p { margin: 7px 0 0; color: var(--dp-text-2); font-size: 12px; }
.admin-count { display: grid; grid-template-columns: auto auto; align-items: center; gap: 2px 9px; padding: 12px 15px; border: 1px solid var(--dp-line); background: var(--dp-panel); color: var(--dp-accent); }
.admin-count strong { color: var(--dp-text); font-size: 18px; }.admin-count span { grid-column: 2; color: var(--dp-text-2); font-size: 10px; }
.admin-section { margin-bottom: 16px; padding: 19px; border: 1px solid var(--dp-line); background: var(--dp-panel); }
.admin-section__heading { margin-bottom: 15px; }.admin-section h2 { margin: 0; font-size: 16px; }
.admin-row { display: flex; align-items: center; gap: 14px; min-height: 58px; padding: 9px 10px; border: 1px solid var(--dp-line); background: #151a1f; }
.admin-row + .admin-row, .admin-role-card + .admin-role-card { margin-top: 7px; }
.admin-row__identity { display: grid; flex: 1; min-width: 150px; gap: 4px; }.admin-row__identity strong { font-size: 12px; }.admin-row__identity small, .admin-muted { color: var(--dp-text-dim); font-size: 10px; }
.admin-role, .admin-role-card__top > label { display: grid; min-width: 150px; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.admin-role select, .admin-role-create input:not([type='checkbox']), .admin-role-card input:not([type='checkbox']) { width: 100%; min-height: 34px; border: 1px solid var(--dp-line); border-radius: 4px; padding: 0 9px; color: var(--dp-text); background: #101419; font: inherit; font-size: 11px; }
.admin-row__actions { display: flex; flex-wrap: wrap; gap: 6px; }
.admin-button { display: inline-flex; min-height: 32px; align-items: center; justify-content: center; gap: 6px; padding: 0 10px; border: 1px solid var(--dp-line); border-radius: 4px; color: var(--dp-text-2); background: transparent; font-size: 10px; font-weight: 650; cursor: pointer; }
.admin-button--allow { color: var(--dp-accent); background: var(--dp-accent-soft); }.admin-button--danger { color: var(--dp-danger); background: var(--dp-danger-soft); }.admin-button--primary { color: #0c1710; border-color: transparent; background: var(--dp-accent); }
.admin-button:disabled { opacity: .5; cursor: not-allowed; }
.admin-role-create, .admin-role-card { display: grid; gap: 12px; padding: 13px; border: 1px solid var(--dp-line); background: var(--dp-panel-2); }
.admin-role-create { grid-template-columns: minmax(160px, .7fr) minmax(0, 2fr) auto; align-items: end; margin-bottom: 8px; }
.admin-role-create > label { display: grid; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.admin-role-create fieldset, .admin-role-card fieldset { display: flex; flex-wrap: wrap; gap: 8px 13px; min-width: 0; margin: 0; padding: 8px; border: 1px solid var(--dp-line); }
.admin-role-create legend, .admin-role-card legend { padding: 0 5px; color: var(--dp-text-dim); font-size: 9px; }
.admin-role-create fieldset label, .admin-role-card fieldset label { display: inline-flex; align-items: center; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.admin-role-card__top { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; }.admin-role-card__top small { color: var(--dp-text-dim); font-size: 10px; }
.admin-empty { padding: 17px; color: var(--dp-text-dim); text-align: center; font-size: 11px; }
.admin-toggle { display: flex; align-items: center; justify-content: space-between; gap: 16px; }.admin-toggle span { display: grid; gap: 4px; }.admin-toggle strong { font-size: 12px; }.admin-toggle small { color: var(--dp-text-dim); font-size: 10px; }
.admin-error { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; padding: 10px 12px; border: 1px solid var(--dp-danger-line); color: #f0a29d; background: var(--dp-danger-soft); font-size: 11px; }.admin-error span { flex: 1; }.admin-error button { color: inherit; }
@media (max-width: 800px) { .admin-row { align-items: flex-start; flex-wrap: wrap; }.admin-role-create { grid-template-columns: 1fr; }.admin-role-create .admin-button { justify-self: start; } }
</style>
