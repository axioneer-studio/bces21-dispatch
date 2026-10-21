<script setup lang="ts">
type SidebarMode = 'collapsed' | 'expanded' | 'hover'

const STORAGE_KEY = 'bces:sidebar-mode'
const mode = ref<SidebarMode>('hover')
const hovering = ref(false)
const settingsOpen = ref(false)
const modeWrap = ref<HTMLElement | null>(null)
let hoverTimer: ReturnType<typeof setTimeout> | null = null

const modeOptions: ReadonlyArray<{ value: SidebarMode; label: string; icon: string }> = [
  { value: 'collapsed', label: 'Réduite', icon: 'lucide:panel-left-close' },
  { value: 'expanded', label: 'Étendue', icon: 'lucide:panel-left-open' },
  { value: 'hover', label: 'Au survol', icon: 'lucide:mouse-pointer-2' }
]

const expanded = computed(() => mode.value === 'expanded' || (mode.value === 'hover' && hovering.value))

interface NavItem {
  to: string
  label: string
  icon: string
}

const items: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: 'lucide:layout-dashboard' },
  { to: '/dispatch', label: 'Dispatch', icon: 'lucide:radio' }
]

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

const currentMode = computed(() => modeOptions.find((option) => option.value === mode.value) ?? modeOptions[2])

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
      <img src="/images/logo.png" alt="BCES" class="sidebar__logo" />
      <span v-if="expanded" class="sidebar__brand-name">BCES</span>
    </div>

    <nav class="sidebar__nav">
      <NuxtLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="sidebar__link"
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
</style>
