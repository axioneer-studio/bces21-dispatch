<script setup lang="ts">
const config = useRuntimeConfig()

onMounted(() => {
  document.body.dataset.layout = 'dispatch'
})
onBeforeUnmount(() => {
  delete document.body.dataset.layout
})
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
  min-height: 100vh;
  background: var(--dp-bg);
  color: var(--dp-text);
}

.dispatch-layout__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>