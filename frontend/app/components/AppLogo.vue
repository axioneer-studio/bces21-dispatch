<script setup lang="ts">
defineProps<{
  size?: number
}>()
</script>

<template>
  <NuxtLink to="/" class="bces-brand" aria-label="BCES Dispatch - Accueil">
    <img src="/images/logo.png" alt="BCES Dispatch" :height="size ?? 44" />
    <span class="bces-brand__name">BCES</span>
  </NuxtLink>
</template>

<style scoped>
.bces-brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--bces-accent);
}

.bces-brand:hover {
  color: var(--bces-accent-hover);
}

.bces-brand img {
  display: block;
  height: auto;
  filter: drop-shadow(0 2px 6px rgba(70, 153, 109, 0.35));
}

.bces-brand__name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
</style>