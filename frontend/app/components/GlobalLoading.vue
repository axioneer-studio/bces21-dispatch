<script setup lang="ts">
import { useGlobalLoading } from "~/composables/useGlobalLoading";

const { isLoading } = useGlobalLoading();
</script>

<template>
  <div
    v-if="isLoading"
    class="bces-global-loading"
    role="status"
    aria-label="Chargement en cours"
  >
    <div class="bces-global-loading__backdrop" />
    <div class="bces-global-loading__spinner">
      <div class="bces-global-loading__spinner-ring" />
    </div>
  </div>
</template>

<style scoped>
.bces-global-loading {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bces-bg, #0a0f0d);
}

.bces-global-loading__backdrop {
  position: absolute;
  inset: 0;
}

.bces-global-loading__spinner {
  position: relative;
  width: 48px;
  height: 48px;
}

.bces-global-loading__spinner-ring {
  position: absolute;
  inset: 0;
  border: 3px solid rgba(70, 153, 109, 0.15);
  border-top-color: var(--bces-accent, #46996d);
  border-radius: 50%;
  animation: bces-spin 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

@keyframes bces-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
