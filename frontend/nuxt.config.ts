// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: ['@nuxt/icon'],

  css: ['~/assets/css/main.css'],

  app: {
    head: {
      title: 'BCES Dispatch',
      htmlAttrs: { lang: 'fr', class: 'dark' },
      bodyAttrs: { class: 'dark-body' },
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'color-scheme', content: 'dark' },
        { name: 'theme-color', content: '#0a0f0d' }
      ],
      link: [
        { rel: 'icon', type: 'image/png', href: '/images/logo.png' }
      ]
    }
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
