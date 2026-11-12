<script setup lang="ts">
import type { Ref } from 'vue'

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

/** « radio » : fréquence BCES ; « shared » : fréquence commune, partagée avec les autres services. */
type FrequencyKind = 'radio' | 'shared'

interface FrequencySetting {
  kind: FrequencyKind
  current: string
  /** Bornes incluses, `null` tant qu'elles ne sont pas réglées. */
  min: number | null
  max: number | null
}

interface FleetVehicle {
  id: number
  name: string
  plate: string | null
  model: string | null
}

interface VehicleImportResult {
  created: number
  updated: number
  deleted: number
  vehicles: FleetVehicle[]
}

interface ParkingSpot {
  id: number
  name: string
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
const [
  { data: initialUsers },
  { data: initialRoles },
  { data: permissionOptions },
  { data: initialRequests },
  { data: initialSettings },
  { data: initialVehicles },
  { data: initialParkingSpots },
  { data: initialFrequencies }
] =
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
    ),
    useAsyncData('admin-vehicles', () =>
      $fetch<FleetVehicle[]>('/api/admin/vehicles', { credentials: 'include', headers: requestHeaders })
    ),
    useAsyncData('admin-parking-spots', () =>
      $fetch<ParkingSpot[]>('/api/admin/parking-spots', { credentials: 'include', headers: requestHeaders })
    ),
    useAsyncData('admin-frequencies', () =>
      $fetch<FrequencySetting[]>('/api/admin/frequencies', { credentials: 'include', headers: requestHeaders })
    )
  ])

const users = ref<AppUser[]>(initialUsers.value ?? [])
const roles = ref<AppRole[]>(initialRoles.value ?? [])
const registrations = ref<Registration[]>(initialRequests.value?.users ?? [])
const settings = reactive<AppSettings>(initialSettings.value ?? { registration_open: true })
const persistedRegistrationOpen = ref(settings.registration_open)
const roleForm = reactive({ name: '', pages: [] as string[], permissions: [] as string[] })
const error = ref('')
const savingSettings = ref(false)
const userSearch = ref('')
const registrationSearch = ref('')
const processingRegistrationIds = ref<number[]>([])
const workingUserIds = ref<number[]>([])
const savingRole = ref(false)
const savingRoleIds = ref<number[]>([])
const deletingRoleIds = ref<number[]>([])
const adminSections = ['registrations', 'users', 'roles', 'vehicles', 'parking', 'settings'] as const
const activeAdminSection = ref<(typeof adminSections)[number]>(
  registrations.value.length ? 'registrations' : 'users'
)

// --- Flotte : véhicules et emplacements de stationnement ---
/** Par modèle (Z → A) puis par plaque (A → Z) ; sans modèle ou sans plaque en dernier (même ordre que l'API). */
const byModelAndPlate = (a: FleetVehicle, b: FleetVehicle) =>
  Number(a.model === null) - Number(b.model === null)
  || (b.model ?? '').localeCompare(a.model ?? '', 'fr', { sensitivity: 'base' })
  || Number(a.plate === null) - Number(b.plate === null)
  || (a.plate ?? '').localeCompare(b.plate ?? '', 'fr', { sensitivity: 'base' })
  || a.name.localeCompare(b.name, 'fr')
  || a.id - b.id
const bySpotName = (a: ParkingSpot, b: ParkingSpot) => a.name.localeCompare(b.name, 'fr')

const vehicles = ref<FleetVehicle[]>(initialVehicles.value ?? [])
const parkingSpots = ref<ParkingSpot[]>(initialParkingSpots.value ?? [])
const vehicleForm = reactive({ name: '', plate: '', model: '' })
const spotForm = reactive({ name: '' })
const savingVehicle = ref(false)
const savingSpot = ref(false)
const workingVehicleIds = ref<number[]>([])
const workingSpotIds = ref<number[]>([])

const filteredUsers = computed(() => {
  const query = userSearch.value.trim().toLocaleLowerCase('fr')
  if (!query) return users.value
  return users.value.filter((user) =>
    [user.first_name, user.last_name, user.discord_username, user.role_name, statusLabel(user.status)]
      .filter(Boolean)
      .join(' ')
      .toLocaleLowerCase('fr')
      .includes(query)
  )
})

const filteredRegistrations = computed(() => {
  const query = registrationSearch.value.trim().toLocaleLowerCase('fr')
  if (!query) return registrations.value
  return registrations.value.filter((registration) =>
    [registration.prenom_rp, registration.nom_rp, registration.discord_username, registration.phone]
      .filter(Boolean)
      .join(' ')
      .toLocaleLowerCase('fr')
      .includes(query)
  )
})

const activeUserCount = computed(() => users.value.filter((user) => user.status === 'active').length)

function moveAdminTab(direction: -1 | 1) {
  const currentIndex = adminSections.indexOf(activeAdminSection.value)
  const nextIndex = (currentIndex + direction + adminSections.length) % adminSections.length
  const nextSection = adminSections[nextIndex]
  if (!nextSection) return
  activeAdminSection.value = nextSection
  nextTick(() => document.querySelector<HTMLElement>(`#admin-tab-${activeAdminSection.value}`)?.focus())
}

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
  if (savingRole.value || !roleForm.name.trim()) return
  error.value = ''
  savingRole.value = true
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
  } finally {
    savingRole.value = false
  }
}

async function saveRole(role: AppRole) {
  if (savingRoleIds.value.includes(role.id)) return
  error.value = ''
  savingRoleIds.value.push(role.id)
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
  } finally {
    savingRoleIds.value = savingRoleIds.value.filter((id) => id !== role.id)
  }
}

async function refreshRoles() {
  roles.value = await $fetch<AppRole[]>('/api/admin/roles', { credentials: 'include' })
}

async function deleteRole(role: AppRole) {
  if (deletingRoleIds.value.includes(role.id)) return
  if (!window.confirm(`Supprimer le rôle « ${role.name} » ?`)) return
  error.value = ''
  deletingRoleIds.value.push(role.id)
  try {
    await $fetch(`/api/admin/roles/${role.id}`, { method: 'DELETE', credentials: 'include' })
    roles.value = roles.value.filter((item) => item.id !== role.id)
  } catch (cause) {
    error.value = messageFromError(cause, 'Suppression du rôle impossible.')
  } finally {
    deletingRoleIds.value = deletingRoleIds.value.filter((id) => id !== role.id)
  }
}

async function assignRole(user: AppUser, event: Event) {
  if (workingUserIds.value.includes(user.id)) return
  const rawId = (event.target as HTMLSelectElement).value
  const roleId = rawId ? Number(rawId) : null
  error.value = ''
  workingUserIds.value.push(user.id)
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
  } finally {
    workingUserIds.value = workingUserIds.value.filter((id) => id !== user.id)
  }
}

async function refreshUsers() {
  users.value = await $fetch<AppUser[]>('/api/admin/users', { credentials: 'include' })
}

async function setActivation(user: AppUser) {
  if (workingUserIds.value.includes(user.id)) return
  const isActive = user.status !== 'active'
  error.value = ''
  workingUserIds.value.push(user.id)
  try {
    await $fetch(`/api/admin/users/${user.id}/activation`, {
      method: 'PATCH',
      body: { is_active: isActive },
      credentials: 'include'
    })
    user.status = isActive ? 'active' : 'disabled'
  } catch (cause) {
    error.value = messageFromError(cause, 'Modification du compte impossible.')
  } finally {
    workingUserIds.value = workingUserIds.value.filter((id) => id !== user.id)
  }
}

async function deleteUser(user: AppUser) {
  if (workingUserIds.value.includes(user.id)) return
  const displayName = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.discord_username
  if (!window.confirm(`Supprimer définitivement le compte de ${displayName} ? Sa tuile employé sera conservée sans compte lié.`)) return
  error.value = ''
  workingUserIds.value.push(user.id)
  try {
    await $fetch(`/api/admin/users/${user.id}`, {
      method: 'DELETE',
      credentials: 'include'
    })
    users.value = users.value.filter((item) => item.id !== user.id)
    registrations.value = registrations.value.filter((item) => item.id !== user.id)
  } catch (cause) {
    error.value = messageFromError(cause, 'Suppression du compte impossible.')
  } finally {
    workingUserIds.value = workingUserIds.value.filter((id) => id !== user.id)
  }
}

async function resolveRegistration(registration: Registration, action: 'approve' | 'reject') {
  if (processingRegistrationIds.value.includes(registration.id)) return
  error.value = ''
  processingRegistrationIds.value.push(registration.id)
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
  } finally {
    processingRegistrationIds.value = processingRegistrationIds.value.filter((id) => id !== registration.id)
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
    persistedRegistrationOpen.value = saved.registration_open
  } catch (cause) {
    settings.registration_open = persistedRegistrationOpen.value
    error.value = messageFromError(cause, 'Enregistrement des paramètres impossible.')
  } finally {
    savingSettings.value = false
  }
}

// --- Fréquences radio : [borne basse] < [fréquence actuelle] < [borne haute] ---

type FrequencyField = 'min' | 'current' | 'max'
type FrequencyForm = Record<FrequencyField, string>

const FREQUENCY_LABELS: Record<FrequencyKind, string> = {
  radio: 'Fréquence Radio BCES',
  shared: 'Fréquence Radio Commune'
}
const FREQUENCY_FIELDS: { field: FrequencyField; label: string }[] = [
  { field: 'min', label: 'Borne basse' },
  { field: 'current', label: 'Fréquence actuelle' },
  { field: 'max', label: 'Borne haute' }
]

const formFromSetting = (setting: FrequencySetting): FrequencyForm => ({
  min: setting.min?.toString() ?? '',
  current: setting.current,
  max: setting.max?.toString() ?? ''
})

const frequencySettings = ref<FrequencySetting[]>(initialFrequencies.value ?? [])
const frequencyForms = reactive<Partial<Record<FrequencyKind, FrequencyForm>>>(
  Object.fromEntries(frequencySettings.value.map((setting) => [setting.kind, formFromSetting(setting)]))
)
const frequencyErrors = reactive<Partial<Record<FrequencyKind, string>>>({})
/** Ligne en cours de saisie : le rafraîchissement en direct ne l'écrase pas. */
const editingFrequency = ref<FrequencyKind | null>(null)
const savingFrequency = ref<FrequencyKind | null>(null)

/** N'accepte que des chiffres (5 au maximum). */
function onFrequencyInput(kind: FrequencyKind, field: FrequencyField, event: Event) {
  const input = event.target as HTMLInputElement
  const digits = input.value.replace(/\D/g, '').slice(0, 5)
  input.value = digits
  const form = frequencyForms[kind]
  if (form) form[field] = digits
  delete frequencyErrors[kind]
}

function frequencyProblem(form: FrequencyForm): string {
  if (!form.min || !form.current || !form.max) return 'Remplissez les trois champs.'
  const [low, current, high] = [Number(form.min), Number(form.current), Number(form.max)]
  if (low > high) return 'La borne basse doit être inférieure ou égale à la borne haute.'
  if (current < low || current > high) return `La fréquence doit être comprise entre ${low} et ${high} (incluses).`
  return ''
}

/** Enregistre la ligne quand le focus la quitte (ou sur Entrée), si elle a changé. */
async function saveFrequency(kind: FrequencyKind) {
  editingFrequency.value = null
  const form = frequencyForms[kind]
  const saved = frequencySettings.value.find((setting) => setting.kind === kind)
  if (!form || !saved) return
  const savedForm = formFromSetting(saved)
  if (form.min === savedForm.min && form.current === savedForm.current && form.max === savedForm.max) return
  const problem = frequencyProblem(form)
  if (problem) {
    frequencyErrors[kind] = problem
    return
  }
  savingFrequency.value = kind
  try {
    const updated = await $fetch<FrequencySetting>(`/api/admin/frequencies/${kind}`, {
      method: 'PUT',
      body: { min: Number(form.min), current: Number(form.current), max: Number(form.max) },
      credentials: 'include'
    })
    frequencySettings.value = frequencySettings.value.map((setting) => (setting.kind === kind ? updated : setting))
    frequencyForms[kind] = formFromSetting(updated)
    delete frequencyErrors[kind]
  } catch (cause) {
    frequencyErrors[kind] = messageFromError(cause, 'Enregistrement de la fréquence impossible.')
  } finally {
    savingFrequency.value = null
  }
}

function onFrequencyFocusOut(kind: FrequencyKind, event: FocusEvent) {
  // Le focus passe d'un champ à l'autre de la même ligne : on attend la sortie de la ligne.
  if ((event.currentTarget as HTMLElement).contains(event.relatedTarget as Node | null)) return
  saveFrequency(kind)
}

/**
 * Suit les changements faits depuis le Dispatch (double-clic) : rechargement à
 * l'ouverture de l'onglet, au retour sur la fenêtre et toutes les 5 s tant que
 * l'onglet est affiché. Une ligne en cours de saisie, d'enregistrement ou en
 * erreur n'est pas écrasée.
 */
async function refreshFrequencies() {
  try {
    const latest = await $fetch<FrequencySetting[]>('/api/admin/frequencies', { credentials: 'include' })
    frequencySettings.value = latest
    for (const setting of latest) {
      const busy = editingFrequency.value === setting.kind
        || savingFrequency.value === setting.kind
        || Boolean(frequencyErrors[setting.kind])
      if (!busy) frequencyForms[setting.kind] = formFromSetting(setting)
    }
  } catch {
    // Rafraîchissement silencieux : on réessaiera au prochain passage.
  }
}

let frequencyTimer: ReturnType<typeof setInterval> | undefined
const refreshVisibleFrequencies = () => {
  if (activeAdminSection.value === 'settings' && document.visibilityState === 'visible') refreshFrequencies()
}

watch(activeAdminSection, (section) => {
  if (section === 'settings') refreshFrequencies()
})

onMounted(() => {
  frequencyTimer = setInterval(refreshVisibleFrequencies, 5000)
  window.addEventListener('focus', refreshVisibleFrequencies)
})

onBeforeUnmount(() => {
  if (frequencyTimer) clearInterval(frequencyTimer)
  window.removeEventListener('focus', refreshVisibleFrequencies)
})

async function withWorking(ids: Ref<number[]>, id: number, task: () => Promise<void>) {
  if (ids.value.includes(id)) return
  error.value = ''
  ids.value.push(id)
  try {
    await task()
  } finally {
    ids.value = ids.value.filter((item) => item !== id)
  }
}

async function createVehicle() {
  if (savingVehicle.value || !vehicleForm.name.trim()) return
  error.value = ''
  savingVehicle.value = true
  try {
    const vehicle = await $fetch<FleetVehicle>('/api/admin/vehicles', {
      method: 'POST',
      body: { name: vehicleForm.name, plate: vehicleForm.plate || null, model: vehicleForm.model || null },
      credentials: 'include'
    })
    vehicles.value = [...vehicles.value, vehicle].sort(byModelAndPlate)
    vehicleForm.name = ''
    vehicleForm.plate = ''
    vehicleForm.model = ''
  } catch (cause) {
    error.value = messageFromError(cause, 'Création du véhicule impossible.')
  } finally {
    savingVehicle.value = false
  }
}

async function saveVehicle(vehicle: FleetVehicle) {
  await withWorking(workingVehicleIds, vehicle.id, async () => {
    try {
      const saved = await $fetch<FleetVehicle>(`/api/admin/vehicles/${vehicle.id}`, {
        method: 'PATCH',
        body: { name: vehicle.name, plate: vehicle.plate || null, model: vehicle.model || null },
        credentials: 'include'
      })
      Object.assign(vehicle, saved)
      vehicles.value = [...vehicles.value].sort(byModelAndPlate)
    } catch (cause) {
      error.value = messageFromError(cause, 'Modification du véhicule impossible.')
    }
  })
}

async function deleteVehicle(vehicle: FleetVehicle) {
  if (!window.confirm(`Supprimer le véhicule « ${vehicle.name} » ? Il sera retiré des lignes de la flotte.`)) return
  await withWorking(workingVehicleIds, vehicle.id, async () => {
    try {
      await $fetch(`/api/admin/vehicles/${vehicle.id}`, { method: 'DELETE', credentials: 'include' })
      vehicles.value = vehicles.value.filter((item) => item.id !== vehicle.id)
    } catch (cause) {
      error.value = messageFromError(cause, 'Suppression du véhicule impossible.')
    }
  })
}

// --- Import du garage (JSON exporté du jeu) : seuls nom, plaque et modèle sont repris ---

type ImportedVehicle = { name: string; plate: string | null; model: string | null }

const toast = useAppToast()
const vehicleFileInput = ref<HTMLInputElement | null>(null)
const importingVehicles = ref(false)

const optionalText = (value: unknown) =>
  typeof value === 'string' && value.trim() ? value.trim() : null

function parseGarageJson(text: string): ImportedVehicle[] {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error('Le fichier n’est pas un JSON valide.')
  }
  if (!Array.isArray(data)) throw new Error('Le JSON doit contenir une liste de véhicules.')
  return data.map((item, index) => {
    const entry = (item ?? {}) as Record<string, unknown>
    const name = optionalText(entry.name)
    if (!name) throw new Error(`Le véhicule n°${index + 1} n’a pas de nom.`)
    if (name.length > 64) throw new Error(`Le nom « ${name} » dépasse 64 caractères.`)
    const plate = optionalText(entry.plateText)?.toUpperCase() ?? null
    if (plate && plate.length > 16) throw new Error(`La plaque « ${plate} » dépasse 16 caractères.`)
    const model = optionalText(entry.model)
    if (model && model.length > 64) throw new Error(`Le modèle « ${model} » dépasse 64 caractères.`)
    return { name, plate, model }
  })
}

/** Véhicules actuels absents du fichier (reconnus par plaque, ou par nom sans plaque). */
function vehiclesMissingFrom(imported: ImportedVehicle[]): FleetVehicle[] {
  const plates = new Set(imported.flatMap((vehicle) => (vehicle.plate ? [vehicle.plate] : [])))
  const plateless = imported.filter((vehicle) => !vehicle.plate).map((vehicle) => vehicle.name)
  return vehicles.value.filter((vehicle) => {
    if (vehicle.plate) return !plates.has(vehicle.plate.toUpperCase())
    const index = plateless.indexOf(vehicle.name)
    if (index < 0) return true
    plateless.splice(index, 1)
    return false
  })
}

async function importVehicles(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || importingVehicles.value) return
  error.value = ''

  let imported: ImportedVehicle[]
  try {
    imported = parseGarageJson(await file.text())
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Lecture du fichier impossible.'
    return
  }

  const missing = vehiclesMissingFrom(imported)
  const warning = missing.length
    ? `\n\nVéhicules absents du fichier, supprimés et retirés des lignes de la flotte (${missing.length}) :\n${missing.map((vehicle) => `• ${vehicle.name}`).join('\n')}`
    : ''
  if (!window.confirm(`Remplacer la liste par les ${imported.length} véhicules du fichier « ${file.name} » ?${warning}`)) return

  importingVehicles.value = true
  try {
    const result = await $fetch<VehicleImportResult>('/api/admin/vehicles/import', {
      method: 'PUT',
      body: { vehicles: imported },
      credentials: 'include'
    })
    vehicles.value = result.vehicles
    toast.success(`Import terminé : ${result.created} ajouté(s), ${result.updated} modifié(s), ${result.deleted} supprimé(s).`)
  } catch (cause) {
    error.value = messageFromError(cause, 'Import des véhicules impossible.')
  } finally {
    importingVehicles.value = false
  }
}

async function createSpot() {
  if (savingSpot.value || !spotForm.name.trim()) return
  error.value = ''
  savingSpot.value = true
  try {
    const spot = await $fetch<ParkingSpot>('/api/admin/parking-spots', {
      method: 'POST',
      body: { name: spotForm.name },
      credentials: 'include'
    })
    parkingSpots.value = [...parkingSpots.value, spot].sort(bySpotName)
    spotForm.name = ''
  } catch (cause) {
    error.value = messageFromError(cause, 'Création de l’emplacement impossible.')
  } finally {
    savingSpot.value = false
  }
}

async function saveSpot(spot: ParkingSpot) {
  await withWorking(workingSpotIds, spot.id, async () => {
    try {
      const saved = await $fetch<ParkingSpot>(`/api/admin/parking-spots/${spot.id}`, {
        method: 'PATCH',
        body: { name: spot.name },
        credentials: 'include'
      })
      Object.assign(spot, saved)
      parkingSpots.value = [...parkingSpots.value].sort(bySpotName)
    } catch (cause) {
      error.value = messageFromError(cause, 'Modification de l’emplacement impossible.')
    }
  })
}

async function deleteSpot(spot: ParkingSpot) {
  if (!window.confirm(`Supprimer l’emplacement « ${spot.name} » ?`)) return
  await withWorking(workingSpotIds, spot.id, async () => {
    try {
      await $fetch(`/api/admin/parking-spots/${spot.id}`, { method: 'DELETE', credentials: 'include' })
      parkingSpots.value = parkingSpots.value.filter((item) => item.id !== spot.id)
    } catch (cause) {
      error.value = messageFromError(cause, 'Suppression de l’emplacement impossible.')
    }
  })
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
      <div class="admin-overview" aria-label="Résumé des comptes">
        <div class="admin-count"><Icon name="lucide:users" size="17" /><strong>{{ users.length }}</strong><span>comptes</span></div>
        <div class="admin-count admin-count--muted"><Icon name="lucide:user-round-check" size="17" /><strong>{{ activeUserCount }}</strong><span>actifs</span></div>
        <div class="admin-count admin-count--warning"><Icon name="lucide:inbox" size="17" /><strong>{{ registrations.length }}</strong><span>à valider</span></div>
      </div>
    </header>

    <div v-if="error" class="admin-error" role="alert">
      <Icon name="lucide:circle-alert" size="17" /><span>{{ error }}</span>
      <button type="button" aria-label="Fermer" @click="error = ''"><Icon name="lucide:x" size="15" /></button>
    </div>

    <nav class="admin-nav" role="tablist" aria-label="Sections d’administration" @keydown.left.prevent="moveAdminTab(-1)" @keydown.right.prevent="moveAdminTab(1)">
      <button id="admin-tab-registrations" type="button" role="tab" :aria-selected="activeAdminSection === 'registrations'" aria-controls="admin-registrations" :class="{ 'is-active': activeAdminSection === 'registrations' }" @click="activeAdminSection = 'registrations'">
        <Icon name="lucide:inbox" size="16" /> Inscriptions <span>{{ registrations.length }}</span>
      </button>
      <button id="admin-tab-users" type="button" role="tab" :aria-selected="activeAdminSection === 'users'" aria-controls="admin-users" :class="{ 'is-active': activeAdminSection === 'users' }" @click="activeAdminSection = 'users'">
        <Icon name="lucide:users-round" size="16" /> Comptes <span>{{ users.length }}</span>
      </button>
      <button id="admin-tab-roles" type="button" role="tab" :aria-selected="activeAdminSection === 'roles'" aria-controls="admin-roles" :class="{ 'is-active': activeAdminSection === 'roles' }" @click="activeAdminSection = 'roles'">
        <Icon name="lucide:shield-check" size="16" /> Rôles <span>{{ roles.length }}</span>
      </button>
      <button id="admin-tab-vehicles" type="button" role="tab" :aria-selected="activeAdminSection === 'vehicles'" aria-controls="admin-vehicles" :class="{ 'is-active': activeAdminSection === 'vehicles' }" @click="activeAdminSection = 'vehicles'">
        <Icon name="lucide:car-front" size="16" /> Véhicules <span>{{ vehicles.length }}</span>
      </button>
      <button id="admin-tab-parking" type="button" role="tab" :aria-selected="activeAdminSection === 'parking'" aria-controls="admin-parking" :class="{ 'is-active': activeAdminSection === 'parking' }" @click="activeAdminSection = 'parking'">
        <Icon name="lucide:square-parking" size="16" /> Stationnement <span>{{ parkingSpots.length }}</span>
      </button>
      <button id="admin-tab-settings" type="button" role="tab" :aria-selected="activeAdminSection === 'settings'" aria-controls="admin-settings" :class="{ 'is-active': activeAdminSection === 'settings' }" @click="activeAdminSection = 'settings'">
        <Icon name="lucide:settings-2" size="16" /> Paramètres
      </button>
    </nav>

    <section id="admin-registrations" v-show="activeAdminSection === 'registrations'" class="admin-section" role="tabpanel" aria-labelledby="admin-tab-registrations" tabindex="0">
      <div class="admin-section__heading">
        <div class="admin-section__intro"><span class="admin-section__icon admin-section__icon--warning"><Icon name="lucide:inbox" size="18" /></span><div><h2>Demandes d’inscription</h2><p>{{ registrations.length }} demande{{ registrations.length > 1 ? 's' : '' }} en attente de validation.</p></div></div>
        <label class="admin-search">
          <Icon name="lucide:search" size="15" />
          <input v-model="registrationSearch" type="search" aria-label="Rechercher une demande" placeholder="Nom ou compte Discord">
        </label>
      </div>
      <article v-for="registration in filteredRegistrations" :key="registration.id" class="admin-row">
        <div class="admin-row__identity">
          <strong>{{ [registration.prenom_rp, registration.nom_rp].filter(Boolean).join(' ') || registration.discord_username }}</strong>
          <small>{{ registration.discord_username }}<span v-if="registration.phone"> · {{ registration.phone }}</span></small>
        </div>
        <div class="admin-row__actions">
          <button type="button" class="admin-button admin-button--allow" :disabled="processingRegistrationIds.includes(registration.id)" @click="resolveRegistration(registration, 'approve')">
            <Icon name="lucide:check" size="14" /> {{ processingRegistrationIds.includes(registration.id) ? 'Traitement…' : 'Valider' }}
          </button>
          <button type="button" class="admin-button admin-button--danger" :disabled="processingRegistrationIds.includes(registration.id)" @click="resolveRegistration(registration, 'reject')">
            <Icon name="lucide:x" size="14" /> Refuser
          </button>
        </div>
      </article>
      <div v-if="!filteredRegistrations.length" class="admin-empty">
        <Icon :name="registrationSearch ? 'lucide:search-x' : 'lucide:inbox'" size="21" />
        <p>{{ registrationSearch ? 'Aucune demande ne correspond à cette recherche.' : 'Aucune demande en attente.' }}</p>
        <button v-if="registrationSearch" type="button" class="admin-button" @click="registrationSearch = ''">Effacer la recherche</button>
      </div>
    </section>

    <section id="admin-users" v-show="activeAdminSection === 'users'" class="admin-section" role="tabpanel" aria-labelledby="admin-tab-users" tabindex="0">
      <div class="admin-section__heading">
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:users-round" size="18" /></span><div><h2>Comptes utilisateurs</h2><p>{{ activeUserCount }} actif{{ activeUserCount > 1 ? 's' : '' }} sur {{ users.length }} compte{{ users.length > 1 ? 's' : '' }}. Attribuez les rôles et gérez les accès.</p></div></div>
        <label class="admin-search">
          <Icon name="lucide:search" size="15" />
          <input v-model="userSearch" type="search" aria-label="Rechercher un utilisateur" placeholder="Nom, Discord, rôle…">
        </label>
      </div>
      <article v-for="user in filteredUsers" :key="user.id" class="admin-row">
        <div class="admin-row__identity">
          <strong>{{ user.first_name || user.discord_username }} {{ user.last_name || '' }}</strong>
          <small>{{ user.discord_username }} <span class="admin-status" :class="`admin-status--${user.status}`">{{ statusLabel(user.status) }}</span><span v-if="user.is_super_admin" class="admin-super-admin"><Icon name="lucide:shield-check" size="12" /> Super-admin</span></small>
        </div>
        <label class="admin-role">
          <span class="sr-only">Rôle applicatif de {{ user.discord_username }}</span>
          <select :value="user.role_id ?? ''" :disabled="workingUserIds.includes(user.id)" @change="assignRole(user, $event)">
            <option value="">Aucun rôle</option>
            <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
          </select>
        </label>
        <button
          v-if="user.status !== 'pending'"
          type="button"
          class="admin-button"
          :class="user.status === 'active' ? 'admin-button--danger' : 'admin-button--allow'"
          :disabled="workingUserIds.includes(user.id)"
          @click="setActivation(user)"
        >
          <Icon :name="user.status === 'active' ? 'lucide:user-round-x' : 'lucide:user-round-check'" size="14" />
          {{ user.status === 'active' ? 'Désactiver' : 'Activer' }}
        </button>
        <button
          type="button"
          class="admin-button admin-button--danger"
          :aria-label="`Supprimer le compte de ${user.discord_username}`"
          :disabled="workingUserIds.includes(user.id)"
          @click="deleteUser(user)"
        >
          <Icon name="lucide:trash-2" size="14" /> Supprimer
        </button>
      </article>
      <div v-if="!filteredUsers.length" class="admin-empty">
        <Icon :name="userSearch ? 'lucide:search-x' : 'lucide:users-round'" size="21" />
        <p>{{ userSearch ? 'Aucun utilisateur ne correspond à cette recherche.' : 'Aucun utilisateur à afficher.' }}</p>
        <button v-if="userSearch" type="button" class="admin-button" @click="userSearch = ''">Effacer la recherche</button>
      </div>
    </section>

    <section id="admin-roles" v-show="activeAdminSection === 'roles'" class="admin-section" role="tabpanel" aria-labelledby="admin-tab-roles" tabindex="0">
      <div class="admin-section__heading">
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:shield-check" size="18" /></span><div><h2>Rôles applicatifs</h2><p>Définissez les pages accessibles et les actions autorisées pour chaque rôle.</p></div></div>
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
        <button class="admin-button admin-button--primary" type="submit" :disabled="savingRole || !roleForm.name.trim()">
          <Icon :name="savingRole ? 'lucide:loader-circle' : 'lucide:plus'" size="14" :class="{ 'admin-spin': savingRole }" /> {{ savingRole ? 'Création…' : 'Ajouter ce rôle' }}
        </button>
      </form>
      <details v-for="role in roles" :key="role.id" class="admin-role-card">
        <summary class="admin-role-card__summary">
          <span class="admin-role-card__badge"><Icon name="lucide:shield" size="16" /></span>
          <span class="admin-role-card__summary-name">{{ role.name }}</span>
          <small>{{ role.pages.length }} page{{ role.pages.length > 1 ? 's' : '' }} · {{ role.users_count }} compte{{ role.users_count > 1 ? 's' : '' }}</small>
          <Icon class="admin-role-card__chevron" name="lucide:chevron-down" size="16" />
        </summary>
        <div class="admin-role-card__content">
          <div class="admin-role-card__top">
            <label><span>Nom du rôle</span><input v-model="role.name" maxlength="64"></label>
            <span class="admin-role-card__usage"><Icon name="lucide:users-round" size="14" /> {{ role.users_count }} compte{{ role.users_count > 1 ? 's' : '' }} lié{{ role.users_count > 1 ? 's' : '' }}</span>
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
            <button type="button" class="admin-button admin-button--primary" :disabled="savingRoleIds.includes(role.id)" @click="saveRole(role)">
              <Icon :name="savingRoleIds.includes(role.id) ? 'lucide:loader-circle' : 'lucide:save'" size="14" :class="{ 'admin-spin': savingRoleIds.includes(role.id) }" />
              {{ savingRoleIds.includes(role.id) ? 'Enregistrement…' : 'Enregistrer les changements' }}
            </button>
              <button type="button" class="admin-button admin-button--danger" :disabled="deletingRoleIds.includes(role.id)" @click="deleteRole(role)">
                <Icon name="lucide:trash-2" size="14" /> {{ deletingRoleIds.includes(role.id) ? 'Suppression…' : 'Supprimer le rôle' }}
            </button>
          </div>
        </div>
      </details>
      <div v-if="!roles.length" class="admin-empty">Aucun rôle applicatif créé.</div>
    </section>

    <section id="admin-vehicles" v-show="activeAdminSection === 'vehicles'" class="admin-section" role="tabpanel" aria-labelledby="admin-tab-vehicles" tabindex="0">
      <div class="admin-section__heading">
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:car-front" size="18" /></span><div><h2>Véhicules de la flotte</h2><p>Véhicules proposés dans l’encart « Flotte de véhicules » du Dispatch. L’import d’un JSON du garage remplace la liste (nom, plaque et modèle).</p></div></div>
        <input ref="vehicleFileInput" type="file" accept="application/json,.json" class="sr-only" tabindex="-1" aria-hidden="true" @change="importVehicles">
        <button type="button" class="admin-button" :disabled="importingVehicles" @click="vehicleFileInput?.click()">
          <Icon :name="importingVehicles ? 'lucide:loader-circle' : 'lucide:file-up'" size="14" :class="{ 'admin-spin': importingVehicles }" /> {{ importingVehicles ? 'Import…' : 'Importer un JSON' }}
        </button>
      </div>
      <form class="admin-catalog-create" @submit.prevent="createVehicle">
        <label><span>Nom du véhicule</span><input v-model="vehicleForm.name" required maxlength="64" placeholder="Ex. Ambulance"></label>
        <label><span>Plaque d’immatriculation</span><input v-model="vehicleForm.plate" maxlength="16" placeholder="Facultative"></label>
        <label><span>Modèle</span><input v-model="vehicleForm.model" maxlength="64" placeholder="Facultatif"></label>
        <button class="admin-button admin-button--primary" type="submit" :disabled="savingVehicle || !vehicleForm.name.trim()">
          <Icon :name="savingVehicle ? 'lucide:loader-circle' : 'lucide:plus'" size="14" :class="{ 'admin-spin': savingVehicle }" /> {{ savingVehicle ? 'Création…' : 'Ajouter ce véhicule' }}
        </button>
      </form>
      <form v-for="vehicle in vehicles" :key="vehicle.id" class="admin-row admin-catalog-row" @submit.prevent="saveVehicle(vehicle)">
        <label><span class="sr-only">Nom du véhicule</span><input v-model="vehicle.name" required maxlength="64"></label>
        <label><span class="sr-only">Plaque de {{ vehicle.name }}</span><input v-model="vehicle.plate" maxlength="16" placeholder="Sans plaque"></label>
        <label><span class="sr-only">Modèle de {{ vehicle.name }}</span><input v-model="vehicle.model" maxlength="64" placeholder="Modèle inconnu"></label>
        <div class="admin-row__actions">
          <button type="submit" class="admin-button" :disabled="workingVehicleIds.includes(vehicle.id) || !vehicle.name.trim()">
            <Icon name="lucide:save" size="14" /> Enregistrer
          </button>
          <button type="button" class="admin-button admin-button--danger" :disabled="workingVehicleIds.includes(vehicle.id)" @click="deleteVehicle(vehicle)">
            <Icon name="lucide:trash-2" size="14" /> Supprimer
          </button>
        </div>
      </form>
      <div v-if="!vehicles.length" class="admin-empty">
        <Icon name="lucide:car-front" size="21" />
        <p>Aucun véhicule enregistré.</p>
      </div>
    </section>

    <section id="admin-parking" v-show="activeAdminSection === 'parking'" class="admin-section" role="tabpanel" aria-labelledby="admin-tab-parking" tabindex="0">
      <div class="admin-section__heading">
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:square-parking" size="18" /></span><div><h2>Emplacements de stationnement</h2><p>Lieux proposés pour la flotte. La liste n’est pas exhaustive : le Dispatch peut aussi saisir un lieu librement.</p></div></div>
      </div>
      <form class="admin-catalog-create admin-catalog-create--single" @submit.prevent="createSpot">
        <label><span>Nom de l’emplacement</span><input v-model="spotForm.name" required maxlength="64" placeholder="Ex. Parking Hôpital"></label>
        <button class="admin-button admin-button--primary" type="submit" :disabled="savingSpot || !spotForm.name.trim()">
          <Icon :name="savingSpot ? 'lucide:loader-circle' : 'lucide:plus'" size="14" :class="{ 'admin-spin': savingSpot }" /> {{ savingSpot ? 'Création…' : 'Ajouter cet emplacement' }}
        </button>
      </form>
      <form v-for="spot in parkingSpots" :key="spot.id" class="admin-row admin-catalog-row admin-catalog-row--single" @submit.prevent="saveSpot(spot)">
        <label><span class="sr-only">Nom de l’emplacement</span><input v-model="spot.name" required maxlength="64"></label>
        <div class="admin-row__actions">
          <button type="submit" class="admin-button" :disabled="workingSpotIds.includes(spot.id) || !spot.name.trim()">
            <Icon name="lucide:save" size="14" /> Enregistrer
          </button>
          <button type="button" class="admin-button admin-button--danger" :disabled="workingSpotIds.includes(spot.id)" @click="deleteSpot(spot)">
            <Icon name="lucide:trash-2" size="14" /> Supprimer
          </button>
        </div>
      </form>
      <div v-if="!parkingSpots.length" class="admin-empty">
        <Icon name="lucide:square-parking" size="21" />
        <p>Aucun emplacement enregistré.</p>
      </div>
    </section>

    <section id="admin-settings" v-show="activeAdminSection === 'settings'" class="admin-section admin-setting" role="tabpanel" aria-labelledby="admin-tab-settings" tabindex="0">
      <div class="admin-section__heading">
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:settings-2" size="18" /></span><div><h2>Paramètres généraux</h2><p>Contrôlez l’ouverture des nouvelles inscriptions.</p></div></div>
      </div>
      <label class="admin-toggle">
        <span><strong>Inscriptions ouvertes</strong><small>Autoriser la création de nouveaux comptes via Discord.</small></span>
        <input v-model="settings.registration_open" type="checkbox" :disabled="savingSettings" @change="saveSettings">
      </label>
      <span v-if="savingSettings" class="admin-muted">Enregistrement…</span>
      <span v-else class="admin-saved"><Icon name="lucide:check" size="13" /> Paramètre synchronisé</span>

      <div class="admin-frequencies">
        <div>
          <strong>Fréquences radio</strong>
          <small>Bornes incluses. Un double-clic sur une fréquence dans le Dispatch en tire une nouvelle au hasard entre ces bornes.</small>
        </div>
        <div
          v-for="setting in frequencySettings"
          :key="setting.kind"
          class="admin-frequency"
          @focusin="editingFrequency = setting.kind"
          @focusout="onFrequencyFocusOut(setting.kind, $event)"
        >
          <span class="admin-frequency__label">{{ FREQUENCY_LABELS[setting.kind] }}</span>
          <div class="admin-frequency__fields">
            <template v-for="(item, index) in FREQUENCY_FIELDS" :key="item.field">
              <span v-if="index > 0" class="admin-frequency__sep" aria-hidden="true">&lt;</span>
              <input
                class="admin-frequency__input"
                :class="{ 'admin-frequency__input--current': item.field === 'current', 'admin-frequency__input--invalid': frequencyErrors[setting.kind] }"
                type="text"
                inputmode="numeric"
                pattern="[0-9]*"
                maxlength="5"
                autocomplete="off"
                :value="frequencyForms[setting.kind]?.[item.field] ?? ''"
                :placeholder="item.field === 'current' ? '—' : '?'"
                :aria-label="`${FREQUENCY_LABELS[setting.kind]} : ${item.label}`"
                :disabled="savingFrequency === setting.kind"
                @input="onFrequencyInput(setting.kind, item.field, $event)"
                @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
              >
            </template>
            <Icon v-if="savingFrequency === setting.kind" name="lucide:loader-circle" size="14" class="admin-spin" />
          </div>
          <p v-if="frequencyErrors[setting.kind]" class="admin-frequency__error" role="alert">{{ frequencyErrors[setting.kind] }}</p>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.admin-page { flex: 1; min-height: 0; overflow: auto; padding: clamp(22px, 4vw, 48px); background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }
.admin-header, .admin-section, .admin-error { width: min(1180px, 100%); margin-right: auto; margin-left: auto; }
.admin-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 22px; padding: clamp(22px, 3vw, 34px); border: 1px solid var(--dp-line); border-radius: 22px; background: linear-gradient(110deg, rgba(70, 153, 109, .12), transparent 72%), var(--dp-panel); box-shadow: 0 18px 48px rgba(0, 0, 0, .16); }
.admin-eyebrow { margin-bottom: 9px; color: var(--dp-accent); font-size: 10px; font-weight: 800; letter-spacing: .15em; }
.admin-header h1 { margin: 0; font-size: clamp(28px, 3.2vw, 38px); letter-spacing: -.04em; }
.admin-header p, .admin-section__heading p { margin: 9px 0 0; color: var(--dp-text-2); font-size: 13px; line-height: 1.6; }
.admin-count { display: grid; min-width: 112px; grid-template-columns: auto auto; align-items: center; gap: 3px 9px; padding: 13px 15px; border: 1px solid var(--dp-line); border-radius: 13px; background: rgba(15, 18, 22, .45); color: var(--dp-accent); }
.admin-count strong { color: var(--dp-text); font-size: 20px; font-variant-numeric: tabular-nums; }.admin-count span { grid-column: 2; color: var(--dp-text-2); font-size: 10px; }
.admin-overview { display: flex; gap: 9px; }.admin-count--muted { color: var(--dp-text-dim); }.admin-count--warning { color: var(--dp-warn); }
.admin-nav { display: flex; gap: 6px; width: min(1180px, 100%); margin: 0 auto 16px; padding: 7px; overflow-x: auto; border: 1px solid var(--dp-line); border-radius: 14px; background: var(--dp-panel); }
.admin-nav button { position: relative; display: inline-flex; min-height: 42px; align-items: center; gap: 8px; padding: 0 14px; border: 1px solid transparent; border-radius: 9px; color: var(--dp-text-2); background: transparent; font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; white-space: nowrap; transition: background .15s ease, color .15s ease; }
.admin-nav button:hover { color: var(--dp-text); background: var(--dp-panel-2); }
.admin-nav button.is-active { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.admin-nav button:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: -2px; }
.admin-nav button span { display: grid; min-width: 20px; height: 20px; place-items: center; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text); background: var(--dp-panel-3); font-size: 9px; font-variant-numeric: tabular-nums; }
.admin-nav button.is-active span { border-color: var(--dp-accent-line); color: var(--dp-accent); background: rgba(70, 153, 109, .13); }
.admin-section { min-height: 300px; margin: 0 auto 16px; padding: clamp(18px, 3vw, 28px); border: 1px solid var(--dp-line); border-radius: 18px; background: linear-gradient(140deg, rgba(255,255,255,.025), transparent 55%), var(--dp-panel); box-shadow: 0 16px 40px rgba(0, 0, 0, .14); }
.admin-section__heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 22px; }.admin-section h2 { margin: 0; font-size: 20px; letter-spacing: -.02em; }
.admin-section__intro { display: flex; align-items: center; gap: 12px; }
.admin-section__icon { display: grid; width: 44px; height: 44px; flex: 0 0 44px; place-items: center; border: 1px solid var(--dp-accent-line); border-radius: 13px; color: var(--dp-accent); background: var(--dp-accent-soft); }
.admin-section__icon--warning { border-color: var(--dp-warn-line); color: var(--dp-warn); background: var(--dp-warn-soft); }
.admin-search { display: flex; min-width: min(280px, 100%); min-height: 42px; align-items: center; gap: 9px; padding: 0 12px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-dim); background: var(--dp-bg); }
.admin-search:focus-within { border-color: var(--dp-accent-line); }
.admin-search input { width: 100%; min-width: 0; min-height: 38px; border: 0; outline: 0; color: var(--dp-text); background: transparent; font: inherit; font-size: 12px; }
.admin-row { display: flex; align-items: center; gap: 14px; min-height: 64px; padding: 12px 14px; border: 1px solid var(--dp-line); border-radius: 12px; background: var(--dp-panel-2); }
.admin-row:hover { border-color: var(--dp-line-strong); }
.admin-row + .admin-row, .admin-role-card + .admin-role-card { margin-top: 9px; }
.admin-row__identity { display: grid; flex: 1; min-width: 150px; gap: 4px; }.admin-row__identity strong { font-size: 12px; }.admin-row__identity small, .admin-muted { color: var(--dp-text-dim); font-size: 10px; }
.admin-status { display: inline-flex; align-items: center; margin-left: 5px; padding: 2px 7px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-2); font-size: 9px; }
.admin-status--active { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.admin-status--pending { border-color: var(--dp-warn-line); color: var(--dp-warn); background: var(--dp-warn-soft); }
.admin-status--disabled, .admin-status--rejected { color: var(--dp-text-dim); background: var(--dp-panel-3); }
.admin-super-admin { display: inline-flex; align-items: center; gap: 3px; margin-left: 7px; color: var(--dp-accent); }
.admin-role, .admin-role-card__top > label { display: grid; min-width: 150px; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.admin-role select, .admin-role-create input:not([type='checkbox']), .admin-role-card input:not([type='checkbox']) { width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; }
.admin-row__actions { display: flex; flex-wrap: wrap; gap: 6px; }
.admin-button { display: inline-flex; min-height: 36px; align-items: center; justify-content: center; gap: 7px; padding: 0 12px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text-2); background: transparent; font-size: 10px; font-weight: 650; cursor: pointer; transition: background .15s ease, border-color .15s ease, transform .15s ease; }
.admin-button--allow { color: var(--dp-accent); background: var(--dp-accent-soft); }.admin-button--danger { color: var(--dp-danger); background: var(--dp-danger-soft); }.admin-button--primary { color: #0c1710; border-color: transparent; background: var(--dp-accent); }
.admin-button:disabled { opacity: .5; cursor: not-allowed; }
.admin-role-create, .admin-role-card { display: grid; gap: 14px; padding: 16px; border: 1px solid var(--dp-line); border-radius: 14px; background: var(--dp-panel-2); }
.admin-role-create { grid-template-columns: minmax(160px, .7fr) minmax(0, 2fr) auto; align-items: end; margin-bottom: 8px; }
.admin-role-create > label { display: grid; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.admin-role-create fieldset, .admin-role-card fieldset { display: flex; flex-wrap: wrap; gap: 9px 14px; min-width: 0; margin: 0; padding: 12px; border: 1px solid var(--dp-line); border-radius: 10px; }
.admin-role-create legend, .admin-role-card legend { padding: 0 5px; color: var(--dp-text-dim); font-size: 9px; }
.admin-role-create fieldset label, .admin-role-card fieldset label { display: inline-flex; align-items: center; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.admin-role-card { display: block; padding: 0; overflow: hidden; transition: border-color .15s ease, background .15s ease; }.admin-role-card:hover { border-color: var(--dp-line-strong); background: #202730; }
.admin-role-card__summary { display: flex; min-height: 68px; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; list-style: none; }
.admin-role-card__summary::-webkit-details-marker { display: none; }
.admin-role-card__badge { display: grid; width: 38px; height: 38px; flex: 0 0 38px; place-items: center; border: 1px solid var(--dp-accent-line); border-radius: 11px; color: var(--dp-accent); background: var(--dp-accent-soft); }
.admin-role-card__summary-name { flex: 1; min-width: 0; overflow: hidden; color: var(--dp-text); font-size: 12px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.admin-role-card__summary > small { color: var(--dp-text-dim); font-size: 10px; white-space: nowrap; }
.admin-role-card__chevron { color: var(--dp-text-dim); transition: transform .15s ease; }.admin-role-card[open] .admin-role-card__chevron { transform: rotate(180deg); }
.admin-role-card__content { display: grid; gap: 16px; padding: 18px; border-top: 1px solid var(--dp-line); }
.admin-role-card__top { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; }.admin-role-card__top small { color: var(--dp-text-dim); font-size: 10px; }
.admin-role-card__usage { display: inline-flex; align-items: center; gap: 5px; color: var(--dp-text-dim); font-size: 10px; white-space: nowrap; }
.admin-role-card__summary:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: -2px; }
.admin-empty { display: grid; min-height: 170px; justify-items: center; align-content: center; gap: 10px; padding: 24px; border: 1px dashed var(--dp-line-strong); border-radius: 14px; color: var(--dp-text-dim); text-align: center; font-size: 12px; }.admin-empty p { margin: 0; }
.admin-toggle { display: flex; align-items: center; justify-content: space-between; gap: 16px; }.admin-toggle span { display: grid; gap: 4px; }.admin-toggle strong { font-size: 12px; }.admin-toggle small { color: var(--dp-text-dim); font-size: 10px; }
.admin-saved { display: inline-flex; align-items: center; gap: 5px; margin-top: 10px; color: var(--dp-accent); font-size: 10px; }
.admin-frequencies { display: grid; gap: 12px; margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--dp-line); }
.admin-frequencies > div:first-child { display: grid; gap: 4px; }.admin-frequencies strong { font-size: 12px; }.admin-frequencies small { color: var(--dp-text-dim); font-size: 10px; }
.admin-frequency { display: grid; grid-template-columns: minmax(160px, 220px) auto; align-items: center; gap: 6px 16px; }
.admin-frequency__label { color: var(--dp-text-2); font-size: 11px; font-weight: 650; }
.admin-frequency__fields { display: flex; align-items: center; gap: 8px; }
.admin-frequency__sep { color: var(--dp-text-dim); font-size: 12px; font-weight: 700; }
.admin-frequency__input { width: 64px; min-height: 36px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 8px; color: var(--dp-text-2); background: var(--dp-bg); font: inherit; font-size: 12px; font-variant-numeric: tabular-nums; text-align: center; }
.admin-frequency__input--current { width: 76px; border-color: var(--dp-accent-line); color: var(--dp-text); font-weight: 700; }
.admin-frequency__input:focus { border-color: var(--dp-accent-line); outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }
.admin-frequency__input--invalid { border-color: var(--dp-danger); }
.admin-frequency__input:disabled { opacity: .6; cursor: wait; }
.admin-frequency__error { grid-column: 2; margin: 0; color: var(--dp-danger); font-size: 10px; }
@media (max-width: 520px) { .admin-frequency { grid-template-columns: 1fr; }.admin-frequency__error { grid-column: 1; } }
.admin-error { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; padding: 12px 14px; border: 1px solid var(--dp-danger-line); border-radius: 12px; color: #f0a29d; background: var(--dp-danger-soft); font-size: 12px; }.admin-error span { flex: 1; }.admin-error button { color: inherit; }
.admin-catalog-create { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(110px, .5fr) minmax(140px, .8fr) auto; align-items: end; gap: 14px; margin-bottom: 8px; padding: 16px; border: 1px solid var(--dp-line); border-radius: 14px; background: var(--dp-panel-2); }
.admin-catalog-create--single { grid-template-columns: minmax(160px, 1fr) auto; }
.admin-catalog-create > label { display: grid; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.admin-catalog-row { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(110px, .5fr) minmax(140px, .8fr) auto; }
.admin-catalog-row--single { grid-template-columns: minmax(160px, 1fr) auto; }
.admin-catalog-row + .admin-catalog-row { margin-top: 9px; }
.admin-catalog-create input, .admin-catalog-row input { width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; }
.admin-catalog-create input:focus, .admin-catalog-row input:focus { border-color: var(--dp-accent-line); outline: 0; }
.admin-spin { animation: admin-spin 1s linear infinite; }@keyframes admin-spin { to { transform: rotate(360deg); } }
@media (max-width: 800px) { .admin-header { align-items: flex-start; flex-direction: column; }.admin-overview { width: 100%; }.admin-count { flex: 1; }.admin-row { align-items: flex-start; flex-wrap: wrap; }.admin-role-create { grid-template-columns: 1fr; }.admin-role-create .admin-button { justify-self: start; }.admin-catalog-create, .admin-catalog-row { grid-template-columns: 1fr; }.admin-catalog-create .admin-button { justify-self: start; }.admin-section__heading { align-items: flex-start; flex-direction: column; }.admin-search { width: 100%; } }
@media (max-width: 520px) { .admin-page { padding: 18px 14px; }.admin-header { padding: 20px 17px; }.admin-overview { gap: 6px; }.admin-count { min-width: 0; padding: 10px; }.admin-count span { font-size: 9px; }.admin-nav { gap: 3px; }.admin-nav button { gap: 6px; padding: 0 10px; }.admin-section { min-height: 250px; padding: 15px; }.admin-section__heading { gap: 12px; }.admin-row__identity { min-width: 100%; }.admin-role { flex: 1; }.admin-toggle { align-items: flex-start; }.admin-role-card__summary { gap: 8px; padding: 10px; }.admin-role-card__summary > small { max-width: 105px; overflow: hidden; text-overflow: ellipsis; }.admin-role-card__content { padding: 13px; }.admin-role-card__top { align-items: flex-start; flex-direction: column; } }
</style>
