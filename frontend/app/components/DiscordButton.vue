<script setup lang="ts">
import { fetchDiscordAuthorizeUrl } from '@/composables/useDispatchApi'

const props = defineProps<{
  url: string
  label?: string
}>()

async function handleClick() {
  if (typeof window === 'undefined') {
    return
  }
  try {
    // Une URL absolue est ouverte directement ; une URL relative est l'endpoint
    // API qui renvoie l'URL d'autorisation Discord (le navigateur reste sur le frontend).
    const authorizeUrl =
      props.url.startsWith('http') ? props.url : await fetchDiscordAuthorizeUrl()
    window.location.href = authorizeUrl
  } catch (error) {
    console.error('Impossible d\'initialiser la connexion Discord.', error)
  }
}
</script>

<template>
  <button
    class="bces-btn bces-btn--discord"
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
  </button>
</template>

<style scoped>
.bces-btn__discord-icon {
  display: block;
  flex-shrink: 0;
}
</style>