<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Accès refusé · BCES' })
</script>

<template>
  <main class="denied">
    <span><Icon name="lucide:shield-x" size="24" /></span>
    <h1>Accès non autorisé</h1>
    <p>Aucun rôle ne vous donne accès aux pages de l’application. Contactez un super-admin.</p>
    <NuxtLink to="/">Retour à l’accueil</NuxtLink>
  </main>
</template>

<style scoped>
.denied { display: grid; flex: 1; align-content: center; justify-items: center; gap: 12px; padding: 24px; color: var(--dp-text); text-align: center; background: var(--dp-bg); }
.denied > span { display: grid; width: 52px; height: 52px; place-items: center; border: 1px solid var(--dp-danger-line); border-radius: 16px; color: var(--dp-danger); background: var(--dp-danger-soft); }
.denied h1 { margin: 0; font-size: 21px; }
.denied p { max-width: 430px; margin: 0; color: var(--dp-text-2); font-size: 12px; line-height: 1.6; }
.denied a { margin-top: 6px; color: var(--dp-accent); font-size: 12px; }
</style>
