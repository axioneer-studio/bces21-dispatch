<script setup lang="ts">
const props = defineProps<{
  url: string
  label?: string
}>()

const config = useRuntimeConfig()

const href = computed(() => {
  const base = props.url.startsWith('http')
    ? props.url
    : `${config.public.apiBase}${props.url}`
  return base
})

function handleClick(event: MouseEvent) {
  event.preventDefault()
  if (typeof window !== 'undefined') {
    window.location.href = href.value
  }
}
</script>

<template>
  <a
    :href="href"
    class="bces-btn bces-btn--discord"
    rel="noopener"
    @click="handleClick"
  >
    <img
      src="https://cdn.jsdelivr.net/gh/selfhst/icons/svg/discord-light.svg"
      alt=""
      width="22"
      height="22"
      class="bces-btn__discord-icon"
    />
    <span>{{ props.label ?? 'Continuer avec Discord' }}</span>
  </a>
</template>

<style scoped>
.bces-btn__discord-icon {
  display: block;
  flex-shrink: 0;
}
</style>