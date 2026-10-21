<script setup lang="ts">
defineProps<{
  message: string
}>()
</script>

<template>
  <div class="empty-slot-state">{{ message }}</div>
</template>

<style scoped>
.empty-slot-state {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  color: var(--dp-text-dim);
  font-size: 10px;
  font-style: italic;
  text-align: center;
}
</style>
