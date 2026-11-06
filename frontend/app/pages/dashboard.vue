<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Accueil · BCES' })

interface DashboardUser {
  is_super_admin: boolean
  page_access: string[]
}

const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
const { data: me } = await useAsyncData('me-dashboard', async () => {
  try {
    return await $fetch<DashboardUser>('/api/me', {
      credentials: 'include',
      headers: requestHeaders
    })
  } catch {
    return null
  }
})

if (!me.value) await navigateTo('/')

const shortcuts = computed(() => {
  const pages = [
    { page: 'dispatch', to: '/dispatch', label: 'Ouvrir le dispatch', detail: 'Gérer les postes et les affectations', icon: 'lucide:radio' },
    { page: 'human-resources', to: '/ressources-humaines', label: 'Gérer les équipes', detail: 'Consulter les agents et leurs compétences', icon: 'lucide:users-round' },
    { page: 'direction', to: '/direction', label: 'Organiser les grades', detail: 'Configurer la hiérarchie du service', icon: 'lucide:shield' },
    { page: 'administration', to: '/administration', label: 'Administrer les accès', detail: 'Gérer les comptes et les rôles', icon: 'lucide:settings-2' }
  ]
  return pages.filter(({ page }) => me.value?.is_super_admin || me.value?.page_access.includes(page))
})
</script>

<template>
  <main class="dashboard">
    <div class="dashboard__content">
      <header class="dashboard__hero">
        <div class="dashboard__intro">
          <p class="dashboard__eyebrow"><span></span> BCES · VOTRE ESPACE</p>
          <h1>Vos outils, au même endroit.</h1>
          <p>Accédez rapidement aux espaces de travail disponibles pour votre compte.</p>
        </div>
        <div class="dashboard__hero-mark" aria-hidden="true">
          <Icon name="lucide:layout-dashboard" size="34" />
        </div>
      </header>

      <section class="dashboard__section" aria-labelledby="tools-title">
        <div class="dashboard__section-heading">
          <div>
            <p class="dashboard__section-kicker">PRÊTS À L’EMPLOI</p>
            <h2 id="tools-title">Accès rapides</h2>
          </div>
          <span v-if="shortcuts.length" class="dashboard__section-count">
            {{ shortcuts.length }} raccourci{{ shortcuts.length > 1 ? 's' : '' }}
          </span>
        </div>
        <div v-if="shortcuts.length" class="dashboard__shortcuts">
          <NuxtLink
            v-for="shortcut in shortcuts"
            :key="shortcut.page"
            class="dashboard__shortcut"
            :class="{ 'dashboard__shortcut--featured': shortcut.page === 'dispatch' }"
            :to="shortcut.to"
          >
            <span class="dashboard__shortcut-icon"><Icon :name="shortcut.icon" size="19" /></span>
            <span class="dashboard__shortcut-copy">
              <strong>{{ shortcut.label }}</strong>
              <small>{{ shortcut.detail }}</small>
            </span>
            <Icon class="dashboard__shortcut-arrow" name="lucide:arrow-up-right" size="17" />
          </NuxtLink>
        </div>
        <div v-else class="dashboard__empty">
          <span class="dashboard__empty-icon"><Icon name="lucide:layout-grid" size="20" /></span>
          <p>Aucun raccourci n’est associé à votre compte pour le moment.</p>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.dashboard {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: clamp(22px, 5vw, 64px);
  background:
    radial-gradient(ellipse at 78% 0, rgba(70, 153, 109, .14), transparent 42%),
    var(--dp-bg);
}
.dashboard__content { display: grid; width: min(1120px, 100%); gap: 38px; margin: 0 auto; }
.dashboard__hero {
  position: relative;
  display: flex;
  min-height: 230px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  overflow: hidden;
  padding: clamp(26px, 5vw, 52px);
  border: 1px solid var(--dp-line);
  border-radius: 24px;
  background: linear-gradient(115deg, rgba(70, 153, 109, .15), rgba(70, 153, 109, .025) 72%), var(--dp-panel);
  box-shadow: 0 18px 48px rgba(0, 0, 0, .18);
}
.dashboard__hero::after {
  position: absolute;
  top: -120px;
  right: 12%;
  width: 330px;
  height: 330px;
  border: 1px solid rgba(70, 153, 109, .11);
  border-radius: 50%;
  box-shadow: 0 0 0 36px rgba(70, 153, 109, .025), 0 0 0 72px rgba(70, 153, 109, .02);
  content: '';
  pointer-events: none;
}
.dashboard__intro { position: relative; z-index: 1; max-width: 680px; }
.dashboard__eyebrow, .dashboard__section-kicker {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0 0 12px;
  color: var(--dp-accent);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .15em;
}
.dashboard__eyebrow span { width: 7px; height: 7px; border-radius: 50%; background: var(--dp-accent); box-shadow: 0 0 12px var(--dp-accent); }
.dashboard__hero h1 { margin: 0; font-size: clamp(30px, 4vw, 46px); line-height: 1.08; letter-spacing: -.045em; }
.dashboard__hero p:last-child { max-width: 540px; margin: 14px 0 0; color: var(--dp-text-2); font-size: 14px; line-height: 1.7; }
.dashboard__hero-mark {
  position: relative;
  z-index: 1;
  display: grid;
  width: 76px;
  height: 76px;
  flex: 0 0 76px;
  place-items: center;
  border: 1px solid var(--dp-accent-line);
  border-radius: 22px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
  box-shadow: 0 10px 32px rgba(0, 0, 0, .18);
}
.dashboard__section { display: grid; gap: 18px; }
.dashboard__section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
.dashboard__section-kicker { margin-bottom: 5px; font-size: 9px; }
.dashboard__section h2 { margin: 0; font-size: 22px; letter-spacing: -.025em; }
.dashboard__section-count { color: var(--dp-text-dim); font-size: 11px; }
.dashboard__shortcuts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.dashboard__shortcut {
  display: grid;
  min-height: 116px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  min-width: 0;
  padding: 22px;
  border: 1px solid var(--dp-line);
  border-radius: 17px;
  color: inherit;
  background: linear-gradient(145deg, rgba(255, 255, 255, .025), transparent 65%), var(--dp-panel);
  text-decoration: none;
  transition: transform .18s ease, border-color .18s ease, background .18s ease, box-shadow .18s ease;
}
.dashboard__shortcut:hover { transform: translateY(-3px); border-color: var(--dp-accent-line); background: var(--dp-panel-2); box-shadow: 0 12px 32px rgba(0, 0, 0, .2); }
.dashboard__shortcut--featured { border-color: rgba(70, 153, 109, .34); background: linear-gradient(115deg, rgba(70, 153, 109, .09), transparent 75%), var(--dp-panel); }
.dashboard__shortcut-icon {
  display: grid;
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  place-items: center;
  border: 1px solid var(--dp-accent-line);
  border-radius: 14px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}
.dashboard__shortcut-copy { display: grid; min-width: 0; gap: 6px; }
.dashboard__shortcut-copy strong { color: var(--dp-text); font-size: 14px; font-weight: 700; }
.dashboard__shortcut-copy small { color: var(--dp-text-2); font-size: 12px; line-height: 1.5; }
.dashboard__shortcut-arrow { color: var(--dp-text-dim); transition: color .18s ease, transform .18s ease; }
.dashboard__shortcut:hover .dashboard__shortcut-arrow { transform: translate(2px, -2px); color: var(--dp-accent); }
.dashboard__shortcut:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: 3px; }
.dashboard__empty {
  display: grid;
  min-height: 180px;
  justify-items: center;
  align-content: center;
  gap: 12px;
  padding: 24px;
  border: 1px dashed var(--dp-line-strong);
  border-radius: 17px;
  color: var(--dp-text-2);
  text-align: center;
}
.dashboard__empty p { max-width: 360px; font-size: 13px; }
.dashboard__empty-icon { display: grid; width: 44px; height: 44px; place-items: center; border-radius: 13px; color: var(--dp-text-dim); background: var(--dp-panel-2); }
@media (max-width: 700px) {
  .dashboard { padding: 22px 18px 32px; }
  .dashboard__content { gap: 28px; }
  .dashboard__hero { min-height: 200px; padding: 28px; }
  .dashboard__shortcuts { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .dashboard__hero { min-height: 0; padding: 24px 20px; }
  .dashboard__hero-mark { display: none; }
  .dashboard__hero h1 { font-size: 32px; }
  .dashboard__shortcut { min-height: 100px; gap: 13px; padding: 17px; }
  .dashboard__shortcut-icon { width: 42px; height: 42px; flex-basis: 42px; }
}
@media (prefers-reduced-motion: reduce) {
  .dashboard *, .dashboard *::before, .dashboard *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
</style>
