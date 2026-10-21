<script setup lang="ts">
import { fetchSnapshot } from '~/composables/useDispatchApi'
import type { Agent } from '~/utils/agent'

definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Tableau de bord BCES' })

const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined

const { data: me } = await useAsyncData('me-dashboard', async () => {
  try {
    return await $fetch('/api/me', { credentials: 'include', headers: requestHeaders })
  } catch {
    return null
  }
})

if (!me.value) await navigateTo('/')

const [{ data: snapshot }, { data: agents }] = await Promise.all([
  useAsyncData('dashboard-snapshot', () => fetchSnapshot().catch(() => null)),
  useAsyncData('dashboard-agents', async () => {
    try {
      const response = await $fetch<{ agents: Agent[] }>('/api/users', {
        credentials: 'include',
        headers: requestHeaders
      })
      return response.agents
    } catch {
      return []
    }
  })
])

const activeSlots = computed(() =>
  (snapshot.value?.slots ?? []).filter((slot) =>
    ['centrale', 'hopital', 'intervention', 'consultation'].includes(slot.kind)
  )
)
const assignedCount = computed(() =>
  new Set((snapshot.value?.slots ?? []).flatMap((slot) => slot.assignments.map((item) => item.user_id))).size
)
const interventionsCount = computed(() =>
  (snapshot.value?.slots ?? []).filter((slot) => ['intervention', 'consultation'].includes(slot.kind)).length
)
const availableCount = computed(() => Math.max(0, (agents.value?.length ?? 0) - assignedCount.value))
const onlineRadios = computed(() => (snapshot.value?.radios ?? []).filter((radio) => radio.is_on).length)
</script>

<template>
  <main class="dashboard">
    <header class="dashboard__header">
      <div>
        <p class="dashboard__eyebrow">BCES</p>
        <h1>Tableau de bord</h1>
        <p>Vue d’ensemble des effectifs et de l’activité en cours.</p>
      </div>
      <NuxtLink class="dashboard__dispatch-link" to="/dispatch">
        Ouvrir le dispatch <Icon name="lucide:arrow-right" size="16" />
      </NuxtLink>
    </header>

    <section class="dashboard__stats" aria-label="Indicateurs">
      <article class="dashboard__stat"><Icon name="lucide:users" size="20" /><strong>{{ assignedCount }}</strong><span>agents assignés</span></article>
      <article class="dashboard__stat"><Icon name="lucide:user-round-check" size="20" /><strong>{{ availableCount }}</strong><span>agents disponibles</span></article>
      <article class="dashboard__stat"><Icon name="lucide:siren" size="20" /><strong>{{ interventionsCount }}</strong><span>interventions</span></article>
      <article class="dashboard__stat"><Icon name="lucide:radio" size="20" /><strong>{{ onlineRadios }}</strong><span>radios actives</span></article>
    </section>

    <section class="dashboard__panel">
      <div>
        <h2>Service en cours</h2>
        <p>{{ activeSlots.length }} postes opérationnels sont configurés.</p>
      </div>
      <NuxtLink to="/dispatch" class="dashboard__action">Gérer les postes</NuxtLink>
    </section>
  </main>
</template>

<style scoped>
.dashboard { flex: 1; overflow: auto; padding: clamp(20px, 4vw, 52px); background: var(--dp-bg); }
.dashboard__header { display: flex; align-items: end; justify-content: space-between; gap: 24px; max-width: 1080px; margin: 0 auto 30px; }
.dashboard__eyebrow { color: var(--dp-accent); font-size: 12px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
h1 { margin: 5px 0 8px; font-size: clamp(26px, 4vw, 38px); }
.dashboard__header p { color: var(--dp-text-2); }
.dashboard__dispatch-link, .dashboard__action { display: inline-flex; align-items: center; gap: 8px; padding: 10px 14px; background: var(--dp-accent); color: #08110b; font-size: 13px; font-weight: 700; text-decoration: none; white-space: nowrap; }
.dashboard__stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; max-width: 1080px; margin: 0 auto 18px; }
.dashboard__stat, .dashboard__panel { background: var(--dp-panel); border: 1px solid var(--dp-line); }
.dashboard__stat { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; padding: 20px; color: var(--dp-accent); }
.dashboard__stat strong { font-size: 28px; line-height: 1; color: var(--dp-text); }
.dashboard__stat span { grid-column: 2; color: var(--dp-text-2); font-size: 12px; }
.dashboard__panel { display: flex; align-items: center; justify-content: space-between; gap: 20px; max-width: 1080px; margin: 0 auto; padding: 22px; }
.dashboard__panel h2 { margin: 0 0 6px; font-size: 16px; }.dashboard__panel p { margin: 0; color: var(--dp-text-2); font-size: 13px; }
.dashboard__action { background: var(--dp-accent-soft); color: var(--dp-accent); border: 1px solid var(--dp-accent-line); }
@media (max-width: 760px) { .dashboard__header, .dashboard__panel { align-items: flex-start; flex-direction: column; }.dashboard__stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
