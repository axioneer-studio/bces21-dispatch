<script setup lang="ts">
const { isLoading } = useGlobalLoading()
</script>

<template>
  <div>
    <GlobalLoading />
    <NuxtRouteAnnouncer />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <ToastStack />
  </div>
</template>
