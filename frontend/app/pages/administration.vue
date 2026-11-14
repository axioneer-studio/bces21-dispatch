<script setup lang="ts">
import { onMounted } from 'vue'
import type { Ref } from 'vue'

definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Administration • BCES' })

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
  super_admin_enabled: boolean
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

interface GoogleSheetsConfig {
  configured: boolean
  enabled: boolean
  spreadsheet_id: string
  sheet_name: string
  timeout_seconds: number
  service_account_configured: boolean
  connection_status: string
  connection_error: string | null

  // Configuration de lecture (disponibilités LSES/BCES/SAFD), stockée séparément.
  read_enabled: boolean
  read_spreadsheet_id: string
  read_sheet_name: string
  read_lses_cell: string
  read_safd_cell: string

  // Configuration d'écriture (statut Dispatch), stockée séparément.
  write_name_cell: string
  write_phone_cell: string
  write_hospital_cell: string
  write_info_cell: string
}

interface GoogleSheetsTestResponse {
  connected: boolean
  error: string | null
  spreadsheet_title: string | null
  sheet_names: string[]
  target_sheet_found: boolean
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
  { data: initialParkingSpots }
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
    )
  ])

const users = ref<AppUser[]>(initialUsers.value ?? [])
const roles = ref<AppRole[]>(initialRoles.value ?? [])
const registrations = ref<Registration[]>(initialRequests.value?.users ?? [])
const settings = reactive<AppSettings>(initialSettings.value ?? { registration_open: true })
const persistedRegistrationOpen = ref(settings.registration_open)

  // Load Google Sheets config after component is mounted to ensure proper initialization
  onMounted(() => {
    loadGoogleSheetsConfig()
  })

// --- Google Sheets configuration ---
const googleSheetsConfig = reactive<GoogleSheetsConfig>({
  configured: false,
  enabled: false,
  spreadsheet_id: '',
  sheet_name: '',
  timeout_seconds: 15,
  service_account_configured: false,
  connection_status: 'non_configuré',
  connection_error: null,

  // Configuration de lecture (disponibilités LSES/BCES/SAFD)
  read_enabled: false,
  read_spreadsheet_id: '',
  read_sheet_name: '',
  read_lses_cell: 'B3',
  read_safd_cell: 'D3',

  // Configuration d'écriture (statut Dispatch)
  write_name_cell: 'A1',
  write_phone_cell: 'B1',
  write_hospital_cell: 'C1',
  write_info_cell: 'D1',
})
const googleSheetsLoading = ref(false)
const googleSheetsError = ref('')
const adminError = ref('')

// Ensure googleSheetsLoading is properly initialized before use
watch(googleSheetsLoading, (val) => {
  // This watch ensures the reactive property is properly tracked
  // eslint-disable-next-line no-console
  console.log('googleSheetsLoading changed to:', val)
})
const googleSheetsSaving = ref(false)
const googleSheetsTesting = ref(false)
const googleSheetsUploading = ref(false)
const serviceAccountFile = ref<File | null>(null)
const serviceAccountInput = ref<HTMLInputElement | null>(null)
const roleForm = reactive({ name: '', pages: [] as string[], permissions: [] as string[] })
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
  adminError.value = ''
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
    adminError.value = messageFromError(cause, 'Création du rôle impossible.')
  } finally {
    savingRole.value = false
  }
}

async function saveRole(role: AppRole) {
  if (savingRoleIds.value.includes(role.id)) return
  adminError.value = ''
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
    adminError.value = messageFromError(cause, 'Modification du rôle impossible.')
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
  adminError.value = ''
  deletingRoleIds.value.push(role.id)
  try {
    await $fetch(`/api/admin/roles/${role.id}`, { method: 'DELETE', credentials: 'include' })
    roles.value = roles.value.filter((item) => item.id !== role.id)
  } catch (cause) {
    adminError.value = messageFromError(cause, 'Suppression du rôle impossible.')
  } finally {
    deletingRoleIds.value = deletingRoleIds.value.filter((id) => id !== role.id)
  }
}

async function assignRole(user: AppUser, event: Event) {
  if (workingUserIds.value.includes(user.id)) return
  const rawId = (event.target as HTMLSelectElement).value
  const roleId = rawId ? Number(rawId) : null
  adminError.value = ''
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
    adminError.value = messageFromError(cause, 'Attribution du rôle impossible.')
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
  adminError.value = ''
  workingUserIds.value.push(user.id)
  try {
    await $fetch(`/api/admin/users/${user.id}/activation`, {
      method: 'PATCH',
      body: { is_active: isActive },
      credentials: 'include'
    })
    user.status = isActive ? 'active' : 'disabled'
  } catch (cause) {
    adminError.value = messageFromError(cause, 'Modification du compte impossible.')
  } finally {
    workingUserIds.value = workingUserIds.value.filter((id) => id !== user.id)
  }
}

async function deleteUser(user: AppUser) {
  if (workingUserIds.value.includes(user.id)) return
  const displayName = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.discord_username
  if (!window.confirm(`Supprimer définitivement le compte de ${displayName} ? Sa tuile employé sera conservée sans compte lié.`)) return
  adminError.value = ''
  workingUserIds.value.push(user.id)
  try {
    await $fetch(`/api/admin/users/${user.id}`, {
      method: 'DELETE',
      credentials: 'include'
    })
    users.value = users.value.filter((item) => item.id !== user.id)
    registrations.value = registrations.value.filter((item) => item.id !== user.id)
  } catch (cause) {
    adminError.value = messageFromError(cause, 'Suppression du compte impossible.')
  } finally {
    workingUserIds.value = workingUserIds.value.filter((id) => id !== user.id)
  }
}

async function resolveRegistration(registration: Registration, action: 'approve' | 'reject') {
  if (processingRegistrationIds.value.includes(registration.id)) return
  adminError.value = ''
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
    adminError.value = messageFromError(cause, 'Traitement de la demande impossible.')
  } finally {
    processingRegistrationIds.value = processingRegistrationIds.value.filter((id) => id !== registration.id)
  }
}

async function saveSettings() {
  savingSettings.value = true
  adminError.value = ''
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
    adminError.value = messageFromError(cause, 'Enregistrement des paramètres impossible.')
  } finally {
    savingSettings.value = false
  }
}

async function withWorking(ids: Ref<number[]>, id: number, task: () => Promise<void>) {
  if (ids.value.includes(id)) return
  adminError.value = ''
  ids.value.push(id)
  try {
    await task()
  } finally {
    ids.value = ids.value.filter((item) => item !== id)
  }
}

async function createVehicle() {
  if (savingVehicle.value || !vehicleForm.name.trim()) return
  adminError.value = ''
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
    adminError.value = messageFromError(cause, 'Création du véhicule impossible.')
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
      adminError.value = messageFromError(cause, 'Modification du véhicule impossible.')
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
      adminError.value = messageFromError(cause, 'Suppression du véhicule impossible.')
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
  adminError.value = ''

  let imported: ImportedVehicle[]
  try {
    imported = parseGarageJson(await file.text())
  } catch (cause) {
    adminError.value = cause instanceof Error ? cause.message : 'Lecture du fichier impossible.'
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
    adminError.value = messageFromError(cause, 'Import des véhicules impossible.')
  } finally {
    importingVehicles.value = false
  }
}

async function createSpot() {
  if (savingSpot.value || !spotForm.name.trim()) return
  adminError.value = ''
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
    adminError.value = messageFromError(cause, 'Création de l’emplacement impossible.')
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
      adminError.value = messageFromError(cause, 'Modification de l’emplacement impossible.')
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
      adminError.value = messageFromError(cause, 'Suppression de l’emplacement impossible.')
    }
  })
}

async function loadGoogleSheetsConfig() {
  googleSheetsLoading.value = true
  googleSheetsError.value = ''
  try {
    const config = await $fetch<GoogleSheetsConfig>('/api/admin/settings/google-sheets', {
      credentials: 'include'
    })
    Object.assign(googleSheetsConfig, {
      configured: config.configured,
      enabled: config.enabled ?? false,
      spreadsheet_id: config.spreadsheet_id,
      sheet_name: config.sheet_name,
      timeout_seconds: config.timeout_seconds ?? 15,
      service_account_configured: config.service_account_configured,
      connection_status: config.connection_status,
      connection_error: config.connection_error,
      read_enabled: config.read_enabled ?? false,
      read_spreadsheet_id: config.read_spreadsheet_id ?? '',
      read_sheet_name: config.read_sheet_name ?? '',
      read_lses_cell: config.read_lses_cell ?? 'B3',
      read_safd_cell: config.read_safd_cell ?? 'D3',
      write_name_cell: config.write_name_cell ?? 'A1',
      write_phone_cell: config.write_phone_cell ?? 'B1',
      write_hospital_cell: config.write_hospital_cell ?? 'C1',
      write_info_cell: config.write_info_cell ?? 'D1',
    })
  } catch (cause) {
    googleSheetsError.value = messageFromError(cause, 'Impossible de charger la configuration Google Sheets.')
  } finally {
    googleSheetsLoading.value = false
  }
}

async function testGoogleSheetsConnection() {
  googleSheetsTesting.value = true
  googleSheetsError.value = ''
  try {
    const result = await $fetch<GoogleSheetsTestResponse>('/api/admin/settings/google-sheets/test', {
      credentials: 'include'
    })
    if (result.connected) {
          Object.assign(googleSheetsConfig, {
        configured: true,
            enabled: googleSheetsConfig.enabled,
            spreadsheet_id: result.spreadsheet_title || googleSheetsConfig.spreadsheet_id,
            sheet_name: googleSheetsConfig.sheet_name,
            timeout_seconds: googleSheetsConfig.timeout_seconds,
            service_account_configured: googleSheetsConfig.service_account_configured,
        connection_status: 'connecté',
        connection_error: null,
            read_enabled: googleSheetsConfig.read_enabled,
            read_spreadsheet_id: googleSheetsConfig.read_spreadsheet_id,
            read_sheet_name: googleSheetsConfig.read_sheet_name,
            read_lses_cell: googleSheetsConfig.read_lses_cell,
            read_safd_cell: googleSheetsConfig.read_safd_cell,
          })
    } else {
          Object.assign(googleSheetsConfig, {
            configured: googleSheetsConfig.configured,
            enabled: googleSheetsConfig.enabled,
            spreadsheet_id: googleSheetsConfig.spreadsheet_id,
            sheet_name: googleSheetsConfig.sheet_name,
            timeout_seconds: googleSheetsConfig.timeout_seconds,
            service_account_configured: googleSheetsConfig.service_account_configured,
        connection_status: 'erreur',
        connection_error: result.error || 'Erreur de connexion inconnue.',
            read_enabled: googleSheetsConfig.read_enabled,
            read_spreadsheet_id: googleSheetsConfig.read_spreadsheet_id,
            read_sheet_name: googleSheetsConfig.read_sheet_name,
            read_lses_cell: googleSheetsConfig.read_lses_cell,
            read_safd_cell: googleSheetsConfig.read_safd_cell,
            write_name_cell: googleSheetsConfig.write_name_cell,
            write_phone_cell: googleSheetsConfig.write_phone_cell,
            write_hospital_cell: googleSheetsConfig.write_hospital_cell,
            write_info_cell: googleSheetsConfig.write_info_cell,
          })
    }
  } catch (cause) {
    googleSheetsError.value = messageFromError(cause, 'Erreur lors du test de connexion.')
  } finally {
    googleSheetsTesting.value = false
  }
}

async function saveGoogleSheetsConfig() {
  if (googleSheetsSaving.value) return
  googleSheetsSaving.value = true
  googleSheetsError.value = ''
  console.log('Saving Google Sheets config...', googleSheetsConfig)
  try {
    const response = await $fetch('/api/admin/settings/google-sheets', {
      method: 'PUT',
      body: {
        spreadsheet_id: googleSheetsConfig.spreadsheet_id,
        sheet_name: googleSheetsConfig.sheet_name,
        enabled: googleSheetsConfig.enabled,
        timeout_seconds: googleSheetsConfig.timeout_seconds,
        read_spreadsheet_id: googleSheetsConfig.read_spreadsheet_id,
        read_sheet_name: googleSheetsConfig.read_sheet_name,
        read_lses_cell: googleSheetsConfig.read_lses_cell,
        read_safd_cell: googleSheetsConfig.read_safd_cell,
        read_enabled: googleSheetsConfig.read_enabled,
        write_name_cell: googleSheetsConfig.write_name_cell,
        write_phone_cell: googleSheetsConfig.write_phone_cell,
        write_hospital_cell: googleSheetsConfig.write_hospital_cell,
        write_info_cell: googleSheetsConfig.write_info_cell,
      },
      credentials: 'include'
    })
    console.log('Save response:', response)
    // Recharger la config
    await loadGoogleSheetsConfig()
    // Afficher un message de succès discret
    googleSheetsSaving.value = false
  } catch (cause) {
    console.error('Save error:', cause)
    googleSheetsError.value = messageFromError(cause, 'Impossible de sauvegarder la configuration Google Sheets.')
    googleSheetsSaving.value = false
  }
}

async function uploadGoogleServiceAccount() {
  if (googleSheetsUploading.value) return
  if (!serviceAccountFile.value) {
    googleSheetsError.value = 'Veuillez sélectionner un fichier JSON.'
    return
  }
  googleSheetsUploading.value = true
  googleSheetsError.value = ''
  try {
    const formData = new FormData()
    formData.append('file', serviceAccountFile.value)
    await $fetch('/api/admin/settings/google-sheets/service-account', {
      method: 'POST',
      body: formData,
      credentials: 'include'
    })
    await loadGoogleSheetsConfig()
    serviceAccountFile.value = null
    googleSheetsUploading.value = false
  } catch (cause) {
    googleSheetsError.value = messageFromError(cause, 'Échec du upload du compte de service.')
    googleSheetsUploading.value = false
  }
}

async function deleteGoogleServiceAccount() {
  if (!window.confirm('Voulez-vous vraiment supprimer le compte de service Google de S3 ?')) return
  googleSheetsError.value = ''
  try {
    await $fetch('/api/admin/settings/google-sheets/service-account', {
      method: 'DELETE',
      credentials: 'include'
    })
    await loadGoogleSheetsConfig()
  } catch (cause) {
    googleSheetsError.value = messageFromError(cause, 'Échec de la suppression du compte de service.')
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
      <div class="admin-overview" aria-label="Résumé des comptes">
        <div class="admin-count"><Icon name="lucide:users" size="17" /><strong>{{ users.length }}</strong><span>comptes</span></div>
        <div class="admin-count admin-count--muted"><Icon name="lucide:user-round-check" size="17" /><strong>{{ activeUserCount }}</strong><span>actifs</span></div>
        <div class="admin-count admin-count--warning"><Icon name="lucide:inbox" size="17" /><strong>{{ registrations.length }}</strong><span>à valider</span></div>
      </div>
    </header>

    <div v-if="adminError" class="admin-error" role="alert">
          <Icon name="lucide:circle-alert" size="17" /><span>{{ adminError }}</span>
          <button type="button" aria-label="Fermer" @click="adminError = ''"><Icon name="lucide:x" size="15" /></button>
    </div>

    <nav class="admin-nav" role="tablist" aria-label="Sections d’administration" @keydown.left.prevent="moveAdminTab(-1)" @keydown.right.prevent="moveAdminTab(1)">
      <button id="admin-tab-registrations" type="button" role="tab" :aria-selected="activeAdminSection === 'registrations'" aria-controls="admin-registrations" :class="{ 'is-active': activeAdminSection === 'registrations' }" @click="activeAdminSection = 'registrations'">
        <Icon name="lucide:user-round-plus" size="16" /> Inscriptions <span>{{ registrations.length }}</span>
      </button>
      <button id="admin-tab-users" type="button" role="tab" :aria-selected="activeAdminSection === 'users'" aria-controls="admin-users" :class="{ 'is-active': activeAdminSection === 'users' }" @click="activeAdminSection = 'users'">
        <Icon name="lucide:users-round" size="16" /> Comptes <span>{{ users.length }}</span>
      </button>
      <button id="admin-tab-roles" type="button" role="tab" :aria-selected="activeAdminSection === 'roles'" aria-controls="admin-roles" :class="{ 'is-active': activeAdminSection === 'roles' }" @click="activeAdminSection = 'roles'">
        <Icon name="lucide:user-round-shield" size="16" /> Rôles <span>{{ roles.length }}</span>
      </button>
      <button id="admin-tab-vehicles" type="button" role="tab" :aria-selected="activeAdminSection === 'vehicles'" aria-controls="admin-vehicles" :class="{ 'is-active': activeAdminSection === 'vehicles' }" @click="activeAdminSection = 'vehicles'">
        <Icon name="lucide:ambulance" size="16" /> Véhicules <span>{{ vehicles.length }}</span>
      </button>
      <button id="admin-tab-parking" type="button" role="tab" :aria-selected="activeAdminSection === 'parking'" aria-controls="admin-parking" :class="{ 'is-active': activeAdminSection === 'parking' }" @click="activeAdminSection = 'parking'">
        <Icon name="lucide:map-pin" size="16" /> Stationnement <span>{{ parkingSpots.length }}</span>
      </button>
      <button id="admin-tab-settings" type="button" role="tab" :aria-selected="activeAdminSection === 'settings'" aria-controls="admin-settings" :class="{ 'is-active': activeAdminSection === 'settings' }" @click="activeAdminSection = 'settings'">
        <Icon name="lucide:settings-2" size="16" /> Paramètres
      </button>
    </nav>

    <section id="admin-registrations" v-show="activeAdminSection === 'registrations'" class="admin-section" role="tabpanel" aria-labelledby="admin-tab-registrations" tabindex="0">
      <div class="admin-section__heading">
        <div class="admin-section__intro"><span class="admin-section__icon admin-section__icon--warning"><Icon name="lucide:user-round-plus" size="18" /></span><div><h2>Demandes d’inscription</h2><p>{{ registrations.length }} demande{{ registrations.length > 1 ? 's' : '' }} en attente de validation.</p></div></div>
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
          <small>{{ user.discord_username }} <span class="admin-status" :class="`admin-status--${user.status}`">{{ statusLabel(user.status) }}</span><span v-if="user.is_super_admin" class="admin-super-admin" :class="{ 'admin-super-admin--off': !user.super_admin_enabled }" :title="user.super_admin_enabled ? undefined : 'Droits super-admin désactivés par l’utilisateur'"><Icon :name="user.super_admin_enabled ? 'lucide:shield-check' : 'lucide:shield-off'" size="12" /> {{ user.super_admin_enabled ? 'Super-admin' : 'Super-admin désactivé' }}</span></small>
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
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:user-round-shield" size="18" /></span><div><h2>Rôles applicatifs</h2><p>Définissez les pages accessibles et les actions autorisées pour chaque rôle.</p></div></div>
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
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:ambulance" size="18" /></span><div><h2>Véhicules de la flotte</h2><p>Véhicules proposés dans l’encart « Flotte de véhicules » du Dispatch. L’import d’un JSON du garage remplace la liste (nom, plaque et modèle).</p></div></div>
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
        <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:map-pin" size="18" /></span><div><h2>Emplacements de stationnement</h2><p>Lieux proposés pour la flotte. La liste n’est pas exhaustive : le Dispatch peut aussi saisir un lieu librement.</p></div></div>
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
            <div class="admin-section__intro"><span class="admin-section__icon"><Icon name="lucide:settings-2" size="18" /></span><div><h2>Paramètres généraux</h2></div></div>
      </div>

          <div v-if="googleSheetsError" class="admin-error" role="alert">
            <Icon name="lucide:circle-alert" size="17" /><span>{{ googleSheetsError }}</span>
            <button type="button" aria-label="Fermer" @click="googleSheetsError = ''"><Icon name="lucide:x" size="15" /></button>
          </div>

          <!-- Formulaire de configuration Google Sheets (toujours affiché) -->
          <div class="admin-settings-google-sheets">
            <!-- État de connexion global -->
            <div v-if="googleSheetsConfig.connection_status !== 'connecté'" class="admin-alert admin-alert--warning" style="margin-bottom: 20px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <Icon :name="googleSheetsConfig.connection_status === 'erreur' ? 'lucide:alert-triangle' : 'lucide:settings'" size="16" />
                <strong style="font-size: 13px;">{{ googleSheetsConfig.connection_status }}</strong>
              </div>
              <p v-if="googleSheetsConfig.connection_error" style="margin: 4px 0 0 0; font-size: 12px; color: var(--dp-text-dim);">{{ googleSheetsConfig.connection_error }}</p>
              <p v-else style="margin: 4px 0 0 0; font-size: 12px; color: var(--dp-text-dim);">Configuration incomplète : ajoutez les credentials et l'ID du Spreadsheet.</p>
              <div v-if="googleSheetsConfig.connection_status === 'non_configuré'" style="margin-top: 8px; font-size: 11px; color: var(--dp-text-dim);">Non configuré : Spreadsheet ID ou nom d'onglet manquant.</div>
              <div v-if="!googleSheetsConfig.service_account_configured" style="margin-top: 8px; font-size: 11px; color: var(--dp-text-dim);">Credentials du compte de service introuvables sur S3.</div>
            </div>

            <!-- === SECTION 1 : COMPTE DE SERVICE === -->
            <div class="admin-settings-section" style="margin-bottom: 24px; border: 1px solid var(--dp-line); border-radius: 12px; background: var(--dp-panel-2); overflow: hidden;">
              <div style="padding: 16px 20px; border-bottom: 1px solid var(--dp-line); background: var(--dp-panel-3);">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <Icon name="lucide:key" size="16" style="color: var(--dp-accent);" />
                  <h3 style="margin: 0; font-size: 15px; color: var(--dp-text);">Compte de service Google</h3>
                </div>
              </div>
              <div style="padding: 20px;">
                              <p style="margin: 0 0 20px 0; font-size: 12px; color: var(--dp-text-dim);">
                                Le fichier JSON du compte de service Google est stocké de manière sécurisée sur S3 (chiffré, jamais en base de données, jamais exposé au frontend).
                </p>

                              <!-- État du compte de service -->
                              <div class="service-account-status" style="margin-bottom: 20px; padding: 16px; border-radius: 8px; background: var(--dp-bg); border: 1px solid var(--dp-line);">
                                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                                  <div style="display: flex; align-items: center; gap: 10px;">
                                    <div :class="['status-indicator', googleSheetsConfig.service_account_configured ? 'status-ok' : 'status-warning']" style="width: 10px; height: 10px; border-radius: 50%;"></div>
                                    <div>
                                      <div style="font-weight: 600; font-size: 13px; color: var(--dp-text);">
                                        {{ googleSheetsConfig.service_account_configured ? 'Compte de service configuré' : 'Aucun compte de service' }}
                                      </div>
                                      <div style="font-size: 11px; color: var(--dp-text-dim);">
                                        {{ googleSheetsConfig.service_account_configured ? 'Fichier JSON stocké sur S3 (chiffré)' : 'Importez un fichier JSON pour commencer' }}
                                      </div>
                                    </div>
                                  </div>
                                  <div style="display: flex; align-items: center; gap: 8px;">
                                    <button v-if="!googleSheetsConfig.service_account_configured" @click="serviceAccountInput.click()" class="admin-button admin-button--primary" style="min-width: 140px;">
                                      <Icon name="lucide:upload" size="14" /> Importer le JSON
                                    </button>
                                    <button v-if="googleSheetsConfig.service_account_configured" @click="testGoogleSheetsConnection" class="admin-button admin-button--primary" :disabled="googleSheetsTesting" style="min-width: 160px;">
                                      <Icon :name="googleSheetsTesting ? 'lucide:loader-circle' : 'lucide:play'" size="14" :class="{ 'admin-spin': googleSheetsTesting }" />
                                      {{ googleSheetsTesting ? 'Test en cours…' : 'Tester la connexion' }}
                                    </button>
                                  </div>
                                </div>
                              </div>

                              <!-- Zone d'import -->
                              <div v-if="!googleSheetsConfig.service_account_configured" class="import-zone" style="margin-bottom: 20px; padding: 24px; border: 2px dashed var(--dp-line); border-radius: 10px; background: var(--dp-bg); text-align: center; transition: all 0.2s;">
                  <input ref="serviceAccountInput" type="file" accept="application/json,.json" style="display: none;" @change="serviceAccountFile = $event.target.files[0]" aria-hidden="true" tabindex="-1" />
                                <div v-if="!serviceAccountFile" style="cursor: pointer;" @click="serviceAccountInput.click()">
                                  <Icon name="lucide:file-json" size="32" style="color: var(--dp-accent); margin-bottom: 12px;" />
                                  <div style="font-weight: 600; font-size: 14px; color: var(--dp-text); margin-bottom: 4px;">Déposez votre fichier JSON ici</div>
                                  <div style="font-size: 12px; color: var(--dp-text-dim);">ou cliquez pour parcourir</div>
                                  <div style="font-size: 11px; color: var(--dp-text-dim); margin-top: 8px;">Fichier .json du compte de service Google</div>
                                </div>
                                <div v-else style="display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap;">
                                  <div style="display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: var(--dp-panel-2); border-radius: 8px; border: 1px solid var(--dp-line);">
                                    <Icon name="lucide:file-json" size="16" style="color: var(--dp-accent);" />
                                    <span style="font-size: 12px; color: var(--dp-text);">{{ serviceAccountFile.name }}</span>
                                  </div>
                                  <button @click="uploadGoogleServiceAccount()" class="admin-button admin-button--primary" :disabled="googleSheetsUploading">
                                    <Icon :name="googleSheetsUploading ? 'lucide:loader-circle' : 'lucide:upload'" size="14" :class="{ 'admin-spin': googleSheetsUploading }" />
                                    {{ googleSheetsUploading ? 'Upload en cours…' : 'Uploader sur S3' }}
                                  </button>
                                  <button @click="serviceAccountFile = null" class="admin-button" style="margin-left: 8px;">
                                    <Icon name="lucide:x" size="14" /> Annuler
                                  </button>
                                </div>
                              </div>

                              <!-- Test de connexion (toujours visible si configuré) -->
                              <div v-if="googleSheetsConfig.service_account_configured" style="margin-top: 20px; padding: 16px; border-radius: 8px; background: var(--dp-bg); border: 1px solid var(--dp-line);">
                                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                                  <div>
                                    <div style="font-weight: 600; font-size: 13px; color: var(--dp-text);">Test de connexion Google Sheets</div>
                                    <div style="font-size: 11px; color: var(--dp-text-dim);">Vérifie que le compte de service peut accéder à l'API Google Sheets</div>
                                  </div>
                                  <button @click="testGoogleSheetsConnection" class="admin-button admin-button--primary" :disabled="googleSheetsTesting">
                                    <Icon :name="googleSheetsTesting ? 'lucide:loader-circle' : 'lucide:play'" size="14" :class="{ 'admin-spin': googleSheetsTesting }" />
                                    {{ googleSheetsTesting ? 'Test en cours…' : 'Tester la connexion' }}
                                  </button>
                                  <span v-if="googleSheetsTesting" style="font-size: 11px; color: var(--dp-text-dim);">Test en cours...</span>
                                </div>
                </div>

                              <!-- Statut de connexion -->
                              <div v-if="googleSheetsConfig.connection_status" style="margin-top: 16px; padding: 12px 16px; border-radius: 8px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;"
                                :class="googleSheetsConfig.connection_status === 'connecté' ? 'status-ok-bg' : (googleSheetsConfig.connection_status === 'erreur' ? 'status-error-bg' : 'status-warning-bg')">
                                <Icon :name="googleSheetsConfig.connection_status === 'connecté' ? 'lucide:check-circle' : (googleSheetsConfig.connection_status === 'erreur' ? 'lucide:alert-circle' : 'lucide:alert-triangle')" size="16" :style="{ color: googleSheetsConfig.connection_status === 'connecté' ? 'var(--dp-accent)' : (googleSheetsConfig.connection_status === 'erreur' ? 'var(--dp-danger)' : 'var(--dp-warn)') }" />
                                <div style="flex: 1; min-width: 200px;">
                                  <div style="font-weight: 600; font-size: 13px;" :style="{ color: googleSheetsConfig.connection_status === 'connecté' ? 'var(--dp-accent)' : (googleSheetsConfig.connection_status === 'erreur' ? 'var(--dp-danger)' : 'var(--dp-warn)') }">
                                    {{ googleSheetsConfig.connection_status === 'connecté' ? 'Connecté avec succès' : (googleSheetsConfig.connection_status === 'erreur' ? 'Erreur de connexion' : googleSheetsConfig.connection_status) }}
                                  </div>
                                  <div v-if="googleSheetsConfig.connection_error" style="font-size: 11px; color: var(--dp-text-dim); margin-top: 2px;">{{ googleSheetsConfig.connection_error }}</div>
                  </div>
                                <div v-if="googleSheetsConfig.connection_status === 'connecté'" style="font-size: 11px; color: var(--dp-text-dim); white-space: nowrap;">
                                  Spreadsheet : {{ googleSheetsConfig.spreadsheet_id }} · Onglet : {{ googleSheetsConfig.sheet_name }}
                                </div>
                              </div>

                              <!-- Actions rapides -->
                              <div v-if="googleSheetsConfig.service_account_configured" style="margin-top: 20px; display: flex; gap: 8px; flex-wrap: wrap;">
                                <button @click="uploadGoogleServiceAccount()" class="admin-button" :disabled="googleSheetsUploading">
                                  <Icon name="lucide:upload" size="14" /> Remplacer le JSON
                                </button>
                                <button @click="deleteGoogleServiceAccount()" class="admin-button admin-button--danger">
                                  <Icon name="lucide:trash-2" size="14" /> Supprimer le compte de service
                                </button>
                </div>
              </div>
            </div>

            <!-- === SECTION 2 : CONFIGURATION DISPATCH (ÉCRITURE) === -->
            <div class="admin-settings-section" style="margin-bottom: 24px; border: 1px solid var(--dp-line); border-radius: 12px; background: var(--dp-panel-2); overflow: hidden;">
              <div style="padding: 16px 20px; border-bottom: 1px solid var(--dp-line); background: var(--dp-panel-3);">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <Icon name="lucide:edit-3" size="16" style="color: var(--dp-accent);" />
                  <h3 style="margin: 0; font-size: 15px; color: var(--dp-text);">Configuration Dispatch (écriture)</h3>
                </div>
              </div>
              <div style="padding: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                  <div>
                    <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Spreadsheet ID</label>
                    <input v-model="googleSheetsConfig.spreadsheet_id" type="text" placeholder="ID du Google Sheets" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                  </div>
                  <div>
                    <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Nom de l'onglet</label>
                    <input v-model="googleSheetsConfig.sheet_name" type="text" placeholder="Ex. Dispatch" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                  </div>
                </div>
                <div style="margin-top: 16px;">
                  <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Cellule Nom/Prénom (central)</label>
                  <input v-model="googleSheetsConfig.write_name_cell" type="text" placeholder="Ex. A1" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                </div>
                <div style="margin-bottom: 16px;">
                  <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Cellule Téléphone (central)</label>
                  <input v-model="googleSheetsConfig.write_phone_cell" type="text" placeholder="Ex. B1" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                </div>
                <div style="margin-bottom: 16px;">
                  <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Cellule Statut Hôpital</label>
                  <input v-model="googleSheetsConfig.write_hospital_cell" type="text" placeholder="Ex. C1" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                </div>
                <div style="margin-bottom: 16px;">
                  <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Cellule Information supplémentaire</label>
                  <input v-model="googleSheetsConfig.write_info_cell" type="text" placeholder="Ex. D1" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                </div>
                <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
                  <input
                    id="google-sheets-enabled"
                    type="checkbox"
                    v-model="googleSheetsConfig.enabled"
                    class="admin-checkbox"
                  />
                  <label
                    for="google-sheets-enabled"
                    style="display: block; font-size: 12px; color: var(--dp-text-2); margin: 0; cursor: pointer;"
                  >
                    Activer la synchronisation Dispatch vers Google Sheets
                  </label>
                  <span style="font-size: 11px; color: var(--dp-text-dim); margin-left: 8px;">
                    Désactiver pour suspendre sans supprimer la configuration.
                  </span>
                </div>
                <div style="margin-bottom: 16px;">
                  <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Délai d'attente API (secondes)</label>
                  <input
                    v-model.number="googleSheetsConfig.timeout_seconds"
                    type="number"
                    min="1"
                    max="300"
                    placeholder="15"
                    style="width: 120px; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                </div>
              </div>
            </div>

            <!-- === SECTION 3 : CONFIGURATION DISPONIBILITÉ (LECTURE) === -->
            <div class="admin-settings-section" style="margin-bottom: 24px; border: 1px solid var(--dp-line); border-radius: 12px; background: var(--dp-panel-2); overflow: hidden;">
              <div style="padding: 16px 20px; border-bottom: 1px solid var(--dp-line); background: var(--dp-panel-3);">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <Icon name="lucide:eye" size="16" style="color: var(--dp-accent);" />
                  <h3 style="margin: 0; font-size: 15px; color: var(--dp-text);">Configuration Disponibilité (lecture)</h3>
                </div>
              </div>
              <div style="padding: 20px;">
                <p style="margin: 0 0 16px 0; font-size: 12px; color: var(--dp-text-dim);">
                  Lecture des statuts LSES/BCES/SAFD depuis un second Google Sheets. Les credentials du compte de service sont partagés avec la configuration Dispatch.
                </p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                  <div>
                    <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Spreadsheet ID (lecture)</label>
                    <input v-model="googleSheetsConfig.read_spreadsheet_id" type="text" placeholder="ID du Google Sheets de lecture" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                  </div>
                  <div>
                    <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Nom de l'onglet (lecture)</label>
                    <input v-model="googleSheetsConfig.read_sheet_name" type="text" placeholder="Ex. Disponibilités" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                  </div>
                </div>
                <div style="margin-top: 16px;">
                  <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Cellule LSES</label>
                  <input v-model="googleSheetsConfig.read_lses_cell" type="text" placeholder="Ex. B3" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                </div>
                <div style="margin-bottom: 16px;">
                  <label style="display: block; font-size: 12px; color: var(--dp-text-2); margin-bottom: 4px;">Cellule SAFD</label>
                  <input v-model="googleSheetsConfig.read_safd_cell" type="text" placeholder="Ex. D3" style="width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 10px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px;" />
                </div>
                <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
                  <input
                    id="google-sheets-read-enabled"
                    type="checkbox"
                    v-model="googleSheetsConfig.read_enabled"
                    class="admin-checkbox"
                  />
                  <label
                    for="google-sheets-read-enabled"
                    style="display: block; font-size: 12px; color: var(--dp-text-2); margin: 0; cursor: pointer;"
                  >
                    Activer la lecture des disponibilités
                  </label>
                  <span style="font-size: 11px; color: var(--dp-text-dim); margin-left: 8px;">
                    Lorsque activé, les statuts LSES/SAFD sont lus depuis ce Sheet.
                  </span>
                </div>
              </div>
            </div>

            <!-- Actions finales -->
            <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
              <button @click="saveGoogleSheetsConfig" class="admin-button admin-button--primary" style="min-width: 140px;">
                <Icon name="lucide:save" size="14" /> Enregistrer la configuration
              </button>
              <button @click="deleteGoogleServiceAccount" class="admin-button admin-button--danger" style="min-width: 140px;">
                <Icon name="lucide:trash-2" size="14" /> Supprimer la configuration
              </button>
            </div>

            <!-- Statut de connexion -->
            <div v-if="googleSheetsConfig.connection_status === 'connecté'" style="margin-top: 16px; padding: 16px; background: var(--dp-accent-soft); border: 1px solid var(--dp-accent-line); border-radius: 8px;">
              <div style="display: flex; align-items: center; gap: 8px; color: var(--dp-accent); font-size: 12px;">
                <Icon name="lucide:check-circle" size="14" />
                <strong>Connecté avec succès</strong>
              </div>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--dp-text-dim);">Spreadsheet : {{ googleSheetsConfig.spreadsheet_id }}</p>
              <p style="margin: 0; font-size: 12px; color: var(--dp-text-dim);">Onglet : {{ googleSheetsConfig.sheet_name }}</p>
            </div>
            <div v-if="googleSheetsConfig.connection_status !== 'connecté' && googleSheetsConfig.connection_status !== 'non_configuré'" style="margin-top: 16px; padding: 12px; background: var(--dp-danger-soft); border: 1px solid var(--dp-danger-line); border-radius: 8px;">
              <div style="display: flex; align-items: center; gap: 8px; color: var(--dp-danger); font-size: 12px;">
                <Icon name="lucide:alert-circle" size="14" />
                <strong>Erreur de connexion</strong>
              </div>
              <p v-if="googleSheetsConfig.connection_error" style="margin: 4px 0 0 0; font-size: 12px; color: var(--dp-text-dim);">{{ googleSheetsConfig.connection_error }}</p>
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
.admin-super-admin--off { color: var(--dp-text-dim); }
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

.admin-settings-google-sheets .admin-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--dp-warn-line);
  border-radius: 8px;
  background: var(--dp-warn-soft);
  color: var(--dp-text);
  font-size: 12px;
}

.admin-settings-google-sheets .admin-alert--warning {
  border-color: var(--dp-warn-line);
  background: var(--dp-warn-soft);
}

.admin-settings-google-sheets input[type="file"] {
  display: none;
}

.admin-checkbox {
  width: 18px;
  height: 18px;
  accent-color: var(--dp-accent);
  cursor: pointer;
}
</style>
