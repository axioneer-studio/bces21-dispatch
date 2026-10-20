<script setup lang="ts">
useHead({ title: 'BCES Connexion' })

const config = useRuntimeConfig()
const toast = useToast()

onMounted(() => {
  const query = new URLSearchParams(window.location.search)
  const code = query.get('error')
  if (code) {
    const message = useErrorMessage(code)
    toast.error(message ?? 'La connexion a échoué.')
    window.history.replaceState({}, '', window.location.pathname)
  }
  if (query.get('status') === 'pending') {
    toast.warning(useErrorMessage('account_pending') ?? 'Compte en attente de validation.')
    window.history.replaceState({}, '', window.location.pathname)
  }
})
</script>

<template>
  <main class="bces-card bces-card--wide">
    <div class="bces-card__brand">
      <img src="/images/logo.png" alt="BCES" />
      <span class="bces-card__brand-name">BCES Dispatch</span>
    </div>

    <h1 class="bces-card__title">BCES Connexion</h1>
    <p class="bces-card__subtitle">
      Connecte-toi avec Discord pour accéder à ton espace.
    </p>

    <DiscordButton :url="config.public.discordAuthUrl" />

    <p class="bces-card__hint">
      Première connexion ? Ton compte est créé automatiquement.
    </p>
  </main>
</template>