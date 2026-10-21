// https://nuxt.com/docs/api/configuration/nuxt-config
import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: [
    '@nuxt/ui',
    '@nuxt/icon',
    '@pinia/nuxt',
    '@vueuse/nuxt'
  ],

  icon: {
    localApiEndpoint: '/_nuxt_icon'
  },

  css: ['~/assets/css/main.css', '~/assets/css/dispatch.css'],

  vite: {
    plugins: [tailwindcss()]
  },

  app: {
    head: {
      title: 'BCES Dispatch',
      htmlAttrs: { lang: 'fr', class: 'dark' },
      bodyAttrs: { class: 'dark-body' },
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'color-scheme', content: 'dark' },
        { name: 'theme-color', content: '#21252b' }
      ],
      link: [
        { rel: 'icon', type: 'image/png', href: '/images/logo.png' }
      ]
    }
  },

  ui: {
    colorMode: false
  },

  nitro: {
    routeRules: {
      '/api/**': {
        proxy: (process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000') + '/api/**'
      }
    }
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000',
      discordAuthUrl: process.env.NUXT_PUBLIC_DISCORD_AUTH_URL || '/api/auth/discord/start',
      timezone: process.env.NUXT_PUBLIC_TIMEZONE || 'Europe/Paris'
    }
  }
})