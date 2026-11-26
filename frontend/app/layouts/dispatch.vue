<script setup lang="ts">
const config = useRuntimeConfig();

let previousHtmlOverflow: string | null = null;
let previousBodyOverflow: string | null = null;

onMounted(() => {
  document.body.dataset.layout = "dispatch";
  // Empêche le double scroll : seul le conteneur de page (.admin-page) doit défiler.
  previousHtmlOverflow = document.documentElement.style.overflow || null;
  previousBodyOverflow = document.body.style.overflow || null;
  document.documentElement.style.overflow = "hidden";
  document.body.style.overflow = "hidden";
});
onBeforeUnmount(() => {
  delete document.body.dataset.layout;
  if (previousHtmlOverflow !== null)
    document.documentElement.style.overflow = previousHtmlOverflow;
  else document.documentElement.style.removeProperty("overflow");
  if (previousBodyOverflow !== null)
    document.body.style.overflow = previousBodyOverflow;
  else document.body.style.removeProperty("overflow");
});
</script>

<template>
  <div class="dispatch-layout">
    <Sidebar />
    <div class="dispatch-layout__main">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.dispatch-layout {
  display: flex;
  height: 100dvh;
  overflow: hidden;
  background: var(--dp-bg);
  color: var(--dp-text);
}

.dispatch-layout__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}
</style>
