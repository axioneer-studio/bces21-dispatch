<script setup lang="ts">
const expanded = ref<boolean>(false)

interface NavItem {
  to: string
  label: string
  icon: string
}

const items: NavItem[] = [
  { to: '/dispatch', label: 'Dispatch', icon: 'lucide:radio' },
  { to: '/dashboard', label: 'Dashboard', icon: 'lucide:layout-dashboard' },
  { to: '/personnel', label: 'Personnel', icon: 'lucide:users' }
]

async function logout() {
  await $fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
  await navigateTo('/')
}
</script>

<template>
  <aside
    class="sidebar"
    :class="{ 'sidebar--expanded': expanded }"
    @mouseenter="expanded = true"
    @mouseleave="expanded = false"
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