<script setup lang="ts">
useHead({ title: "Compte refusé ou désactivé • BCES" });
</script>

<template>
  <main class="bces-card bces-card--wide refused-card">
    <div class="bces-card__brand">
      <img
        src="https://s3.axioneer.com/bces21-dispatch/images/logo-72.webp"
        alt="BCES"
        width="72"
        height="72"
      />
      <span class="bces-card__brand-name">BCES Dispatch</span>
    </div>
    <div class="refused-icon" aria-hidden="true">
      <Icon name="lucide:user-round-x" size="24" />
    </div>
    <h1 class="bces-card__title">Compte refusé ou désactivé</h1>
    <p class="bces-card__subtitle">
      Ta demande de compte a été refusée ou ton compte a été désactivé. Si tu
      penses qu’il s’agit d’une erreur, contacte un membre de l’équipe.
    </p>
    <NuxtLink class="refused-link" to="/">Retour à la connexion</NuxtLink>
  </main>
</template>

<style scoped>
.refused-card {
  text-align: center;
}
.refused-icon {
  display: grid;
  width: 54px;
  height: 54px;
  place-items: center;
  margin: 8px auto 16px;
  border: 1px solid rgba(210, 85, 79, 0.35);
  border-radius: 17px;
  color: #ec8a86;
  background: rgba(210, 85, 79, 0.12);
}
.refused-card .bces-card__title {
  margin-bottom: 8px;
}
.refused-card .bces-card__subtitle {
  max-width: 430px;
  margin: 0 auto 18px;
  line-height: 1.6;
}
.refused-link {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
  border: 1px solid var(--bces-border-strong);
  border-radius: var(--bces-radius-sm);
  color: #04140c;
  background: var(--bces-accent);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition:
    background 0.15s ease,
    transform 0.05s ease;
}
.refused-link:hover {
  background: var(--bces-accent-hover);
}
.refused-link:active {
  background: var(--bces-accent-active);
  transform: translateY(1px);
}
.refused-link:focus-visible {
  outline: 2px solid var(--bces-accent);
  outline-offset: 3px;
}
</style>
