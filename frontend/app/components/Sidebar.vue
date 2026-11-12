<script setup lang="ts">
type SidebarMode = 'collapsed' | 'expanded' | 'hover'

const STORAGE_KEY = 'bces:sidebar-mode'
const mode = ref<SidebarMode>('hover')
const hovering = ref(false)
const settingsOpen = ref(false)
const modeWrap = ref<HTMLElement | null>(null)
let hoverTimer: ReturnType<typeof setTimeout> | null = null
const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
const { data: currentUser } = await useAsyncData('sidebar-current-user', async () => {
  try {
    return await $fetch<{
      is_super_admin: boolean
      super_admin_available: boolean
      super_admin_enabled: boolean
      page_access: string[]
    }>('/api/me', { credentials: 'include', headers: requestHeaders })
  } catch {
    return null
  }
})

const modeOptions: ReadonlyArray<{ value: SidebarMode; label: string; icon: string }> = [
  { value: 'collapsed', label: 'Réduite', icon: 'lucide:panel-left-close' },
  { value: 'expanded', label: 'Étendue', icon: 'lucide:panel-left-open' },
  { value: 'hover', label: 'Au survol', icon: 'lucide:mouse-pointer-2' }
]
const fallbackMode: { value: SidebarMode; label: string; icon: string } = {
  value: 'hover',
  label: 'Au survol',
  icon: 'lucide:mouse-pointer-2'
}

const expanded = computed(() => mode.value === 'expanded' || (mode.value === 'hover' && hovering.value))

interface NavItem {
  to: string
  label: string
  icon: string
  page: string
}

const items: NavItem[] = [
  { to: '/dashboard', label: 'Accueil', icon: 'lucide:layout-dashboard', page: 'dashboard' },
  { to: '/dispatch', label: 'Dispatch', icon: 'lucide:radio', page: 'dispatch' },
  { to: '/agenda', label: 'Agenda', icon: 'lucide:calendar-days', page: 'agenda' },
  { to: '/ressources-humaines', label: 'Ressources humaines', icon: 'lucide:users-round', page: 'human-resources' },
  { to: '/direction', label: 'Direction', icon: 'lucide:shield', page: 'direction' },
  { to: '/administration', label: 'Administration', icon: 'lucide:settings-2', page: 'administration' }
]

const visibleItems = computed(() => items.filter((item) =>
  item.page === 'agenda'
    ? Boolean(currentUser.value)
    : currentUser.value?.is_super_admin || currentUser.value?.page_access.includes(item.page)
))

function setMode(next: SidebarMode) {
  mode.value = next
  hovering.value = false
  settingsOpen.value = false
  if (import.meta.client) localStorage.setItem(STORAGE_KEY, next)
}

function onMouseEnter() {
  if (mode.value !== 'hover') return
  hoverTimer = setTimeout(() => {
    hovering.value = true
  }, 500)
}

function onMouseLeave() {
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = null
  hovering.value = false
  settingsOpen.value = false
}

onMounted(() => {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'collapsed' || stored === 'expanded' || stored === 'hover') mode.value = stored
})

onBeforeUnmount(() => {
  if (hoverTimer) clearTimeout(hoverTimer)
  if (import.meta.client) document.removeEventListener('pointerdown', onDocumentPointerDown)
})

const currentMode = computed(() => modeOptions.find((option) => option.value === mode.value) ?? fallbackMode)

function toggleSettings() {
  settingsOpen.value = !settingsOpen.value
}

function onDocumentPointerDown(event: PointerEvent) {
  if (!settingsOpen.value) return
  if (modeWrap.value && !modeWrap.value.contains(event.target as Node)) settingsOpen.value = false
}

watch(settingsOpen, (open) => {
  if (import.meta.client) {
    if (open) document.addEventListener('pointerdown', onDocumentPointerDown)
    else document.removeEventListener('pointerdown', onDocumentPointerDown)
  }
})

// --- Bouton « Superadmin » : le super-admin coupe ou rétablit ses propres droits ---

const toast = useAppToast()
const route = useRoute()
const togglingSuperAdmin = ref(false)
const superAdminEnabled = computed(() => Boolean(currentUser.value?.super_admin_enabled))
const superAdminLabel = computed(() =>
  superAdminEnabled.value
    ? 'Superadmin activé : cliquer pour n’avoir que les accès de votre rôle'
    : 'Superadmin désactivé : cliquer pour récupérer tous les accès'
)

/**
 * Un seul changement à la fois : le bouton reste grisé, avec un indicateur de
 * chargement, du premier clic jusqu'au rechargement de la page. Il ne redevient
 * cliquable qu'en cas d'erreur.
 */
async function toggleSuperAdmin() {
  if (togglingSuperAdmin.value) return
  togglingSuperAdmin.value = true
  try {
    currentUser.value = await $fetch<NonNullable<typeof currentUser.value>>('/api/me/super-admin', {
      method: 'PATCH',
      body: { enabled: !superAdminEnabled.value },
      credentials: 'include'
    })
  } catch {
    toast.error('Changement du mode superadmin impossible.')
    togglingSuperAdmin.value = false
    return
  }
  // Rechargement complet : menus, pages et accès sont tous recalculés, et
  // la page actuelle redirige si le rôle seul n'y donne pas accès.
  // `force` : sans lui, un second clic dans les 10 s est ignoré (anti-boucle).
  reloadNuxtApp({ path: route.fullPath, force: true })
}

async function logout() {
  await $fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
  await navigateTo('/')
}
</script>

<template>
  <aside
    class="sidebar"
    :class="{ 'sidebar--expanded': expanded }"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
  >
    <div class="sidebar__brand">
      <img src="/images/logo.webp" alt="BCES" class="sidebar__logo" width="28" height="28" />
      <span v-if="expanded" class="sidebar__brand-name">BCES</span>
    </div>

    <nav class="sidebar__nav">
      <NuxtLink
        v-for="item in visibleItems"
        :key="item.to"
        :to="item.to"
        class="sidebar__link"
        :aria-label="item.label"
        :title="item.label"
        active-class="sidebar__link--active"
      >
        <Icon :name="item.icon" size="20" />
        <span v-if="expanded" class="sidebar__label">{{ item.label }}</span>
      </NuxtLink>
    </nav>

    <div class="sidebar__bottom">
      <div ref="modeWrap" class="sidebar__mode-wrap" @keydown.esc="settingsOpen = false">
        <button
          type="button"
          class="sidebar__mode"
          :class="{ 'sidebar__mode--open': settingsOpen }"
          :title="currentMode.label"
          aria-haspopup="listbox"
          :aria-expanded="settingsOpen"
          :aria-label="`Affichage de la navigation : ${currentMode.label}`"
          @click="toggleSettings"
        >
          <Icon :name="currentMode.icon" size="15" />
          <span v-if="expanded" class="sidebar__mode-label">{{ currentMode.label }}</span>
          <Icon
            v-if="expanded"
            name="lucide:chevron-up"
            size="13"
            class="sidebar__mode-chevron"
            :class="{ 'sidebar__mode-chevron--open': settingsOpen }"
          />
        </button>
        <ul v-if="settingsOpen" class="sidebar__mode-menu" role="listbox" aria-label="Affichage de la navigation">
          <li
            v-for="option in modeOptions"
            :key="option.value"
            role="option"
            :aria-selected="mode === option.value"
            class="sidebar__mode-option"
            :class="{ 'sidebar__mode-option--active': mode === option.value }"
            tabindex="0"
            @click="setMode(option.value)"
            @keydown.enter.prevent="setMode(option.value)"
            @keydown.space.prevent="setMode(option.value)"
          >
            <Icon :name="option.icon" size="14" />
            <span>{{ option.label }}</span>
            <Icon v-if="mode === option.value" name="lucide:check" size="13" class="sidebar__mode-check" />
          </li>
        </ul>
      </div>
      <button
        v-if="currentUser?.super_admin_available"
        type="button"
        class="sidebar__link sidebar__superadmin"
        :class="{ 'sidebar__superadmin--off': !superAdminEnabled }"
        role="switch"
        :aria-checked="superAdminEnabled"
        :aria-label="togglingSuperAdmin ? 'Changement du mode superadmin en cours' : superAdminLabel"
        :aria-busy="togglingSuperAdmin"
        :title="togglingSuperAdmin ? 'Changement en cours…' : superAdminLabel"
        :disabled="togglingSuperAdmin"
        @click="toggleSuperAdmin"
      >
        <Icon v-if="togglingSuperAdmin" name="lucide:loader-circle" size="20" class="sidebar__spin" />
        <Icon v-else :name="superAdminEnabled ? 'lucide:shield-check' : 'lucide:shield-off'" size="20" />
        <template v-if="expanded">
          <span class="sidebar__label">{{ togglingSuperAdmin ? 'Changement…' : 'Superadmin' }}</span>
          <span v-if="!togglingSuperAdmin" class="sidebar__switch" aria-hidden="true" />
        </template>
      </button>
      <button
        type="button"
        class="sidebar__link sidebar__link--button"
        aria-label="Déconnexion"
        @click="logout"
      >
        <Icon name="lucide:log-out" size="20" />
        <span v-if="expanded" class="sidebar__label">Déconnexion</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 56px;
  background: var(--dp-panel-2);
  border-right: 1px solid var(--dp-line);
  display: flex;
  flex-direction: column;
  transition: width 0.18s ease;
  flex-shrink: 0;
  height: 100vh;
  position: sticky;
  top: 0;
}

.sidebar--expanded {
  width: 200px;
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px;
  border-bottom: 1px solid var(--dp-line);
  height: 56px;
  flex-shrink: 0;
}

.sidebar__logo {
  width: 28px;
  height: 28px;
  filter: drop-shadow(0 2px 4px rgba(70, 153, 109, 0.4));
  flex-shrink: 0;
}

.sidebar__brand-name {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dp-accent);
  white-space: nowrap;
}

.sidebar__nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 6px;
}

.sidebar__bottom {
  padding: 8px 6px;
  border-top: 1px solid var(--dp-line);
}

.sidebar__mode-wrap {
  position: relative;
  padding-bottom: 8px;
}

.sidebar__mode {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  min-height: 30px;
  padding: 7px 8px;
  color: var(--dp-text-dim);
  background: transparent;
  border: 1px solid transparent;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
}

.sidebar__mode:hover,
.sidebar__mode--open {
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
  border-color: rgba(70, 153, 109, 0.25);
}

.sidebar:not(.sidebar--expanded) .sidebar__mode {
  justify-content: center;
  padding: 7px 0;
}

.sidebar:not(.sidebar--expanded) .sidebar__link {
  justify-content: center;
  padding: 9px 0;
}

.sidebar__mode-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar__mode-chevron {
  flex-shrink: 0;
  transition: transform 0.15s ease;
}

.sidebar__mode-chevron--open {
  transform: rotate(180deg);
}

.sidebar__mode-menu {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% - 4px);
  z-index: 40;
  margin: 0;
  padding: 4px;
  list-style: none;
  background: var(--dp-panel-2);
  border: 1px solid rgba(70, 153, 109, 0.25);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.sidebar:not(.sidebar--expanded) .sidebar__mode-menu {
  left: calc(100% - 4px);
  right: auto;
  bottom: 0;
  width: 160px;
}

.sidebar__mode-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  color: var(--dp-text-dim);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease;
}

.sidebar__mode-option span {
  flex: 1;
}

.sidebar__mode-option:hover,
.sidebar__mode-option:focus-visible {
  color: var(--dp-text);
  background: rgba(70, 153, 109, 0.08);
  outline: none;
}

.sidebar__mode-option--active,
.sidebar__mode-option--active:hover {
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}

.sidebar__mode-check {
  flex-shrink: 0;
}

.sidebar__link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 10px;
  border-radius: 0;
  color: var(--dp-text-2);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  background: transparent;
  border: none;
  width: 100%;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s ease, color 0.12s ease;
  white-space: nowrap;
}

.sidebar__link:hover {
  background: rgba(70, 153, 109, 0.08);
  color: var(--dp-text);
}

.sidebar__link--active {
  background: var(--dp-accent-soft);
  color: var(--dp-accent);
}

.sidebar__label {
  flex: 1;
}

.sidebar__link--button {
  color: var(--dp-text-2);
}

.sidebar__link--button:hover {
  color: #ec8a86;
  background: rgba(210, 85, 79, 0.10);
}

/* Activé : vert comme les liens actifs ; désactivé : gris, bouclier barré. */
.sidebar__superadmin {
  color: var(--dp-accent);
}

.sidebar__superadmin--off {
  color: var(--dp-text-dim);
}

/* En cours : grisé et sans effet de survol, jusqu'au rechargement. */
.sidebar__superadmin:disabled,
.sidebar__superadmin:disabled:hover {
  color: var(--dp-text-dim);
  background: transparent;
  opacity: 0.55;
  cursor: wait;
}

.sidebar__spin {
  animation: sidebar-spin 0.9s linear infinite;
}

@keyframes sidebar-spin {
  to { transform: rotate(360deg); }
}

.sidebar__switch {
  position: relative;
  flex-shrink: 0;
  width: 26px;
  height: 14px;
  border: 1px solid var(--dp-accent-line);
  border-radius: 999px;
  background: var(--dp-accent-soft);
  transition: background 0.15s ease, border-color 0.15s ease;
}

.sidebar__switch::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 14px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dp-accent);
  transition: left 0.15s ease, background 0.15s ease;
}

.sidebar__superadmin--off .sidebar__switch {
  border-color: var(--dp-line-strong);
  background: transparent;
}

.sidebar__superadmin--off .sidebar__switch::after {
  left: 2px;
  background: var(--dp-text-dim);
}
</style>
