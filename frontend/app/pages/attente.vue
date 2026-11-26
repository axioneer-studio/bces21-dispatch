<script setup lang="ts">
useHead({ title: 'Validation du compte • BCES' })

let statusTimer: ReturnType<typeof setInterval> | null = null
let checking = false

async function checkAccountStatus() {
  if (checking) return
  checking = true
  try {
    const result = await $fetch<{ status: string }>('/api/auth/account-status', { credentials: 'include' })
    if (result.status === 'active') {
      await navigateTo('/dispatch', { replace: true })
    } else if (result.status === 'rejected') {
      await navigateTo('/compte-refuse', { replace: true })
    } else if (result.status === 'disabled') {
      await navigateTo('/acces-refuse', { replace: true })
    }
  } catch (cause) {
    const fetchError = cause as { statusCode?: number; status?: number }
    if (fetchError.statusCode === 401 || fetchError.status === 401) {
      await navigateTo('/', { replace: true })
    }
  } finally {
    checking = false
  }
}

onMounted(() => {
  void checkAccountStatus()
  statusTimer = setInterval(() => void checkAccountStatus(), 3000)
})

onBeforeUnmount(() => {
  if (statusTimer !== null) clearInterval(statusTimer)
})
</script>

<template>
  <main class="bces-card bces-card--wide waiting-card">
    <div class="bces-card__brand">
      <img src="https://s3.axioneer.com/bces21-dispatch/images/logo-72.webp" alt="BCES" width="72" height="72" />
      <span class="bces-card__brand-name">BCES Dispatch</span>
    </div>
    <div class="waiting-icon" aria-hidden="true"><Icon name="lucide:clock-3" size="24" /></div>
    <h1 class="bces-card__title">Demande en cours de validation</h1>
    <p class="bces-card__subtitle">Un membre actif doit valider ton compte. Cette page se mettra à jour automatiquement dès qu’une décision sera prise.</p>
    <p class="waiting-status" role="status"><span class="waiting-dot" /> En attente d’une réponse…</p>
  </main>
</template>

<style scoped>
.waiting-card { text-align: center; }
.waiting-icon { display: grid; width: 54px; height: 54px; place-items: center; margin: 8px auto 16px; border: 1px solid var(--bces-accent-soft); border-radius: 17px; color: var(--bces-accent); background: var(--bces-accent-soft); }
.waiting-card .bces-card__title { margin-bottom: 8px; }
.waiting-card .bces-card__subtitle { max-width: 430px; margin: 0 auto; line-height: 1.6; }
.waiting-status { display: inline-flex; align-items: center; gap: 8px; margin: 22px 0 0; color: var(--bces-text-muted); font-size: 12px; }
.waiting-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--bces-accent); box-shadow: 0 0 0 4px var(--bces-accent-soft); animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .45; } }
</style>
