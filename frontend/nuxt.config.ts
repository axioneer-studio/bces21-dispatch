// https://nuxt.com/docs/api/configuration/nuxt-config
import tailwindcss from "@tailwindcss/vite";

declare const process: any;

const publicApiBase =
  process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000";
const apiProxyBase = (
  process.env.API_INTERNAL_BASE ||
  process.env.NUXT_PUBLIC_API_BASE ||
  "http://localhost:8000"
).replace(/\/$/, "");

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },

  modules: ["@nuxt/ui", "@nuxt/icon", "@pinia/nuxt", "@vueuse/nuxt"],

  icon: {
    localApiEndpoint: "/_nuxt_icon",
  },

  css: ["~/assets/css/main.css", "~/assets/css/dispatch.css"],

  vite: {
    plugins: [tailwindcss()],
  },

  app: {
    head: {
      title: "Dispatch • BCES",
      htmlAttrs: { lang: "fr", class: "dark" },
      bodyAttrs: { class: "dark-body" },
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { name: "color-scheme", content: "dark" },
        { name: "theme-color", content: "#46996D" },
        {
          name: "description",
          content:
            "Dispatch BCES - Plateforme web tout-en-un dédiée à la gestion opérationnelle des services de secours, centralisant les interventions, les équipes, les effectifs, les véhicules, les ressources et l'ensemble des opérations quotidiennes au sein d'une interface unique.",
        },
        // Open Graph
        { property: "og:title", content: "Dispatch • BCES" },
        {
          property: "og:description",
          content:
            "Dispatch BCES - Plateforme web tout-en-un dédiée à la gestion opérationnelle des services de secours, centralisant les interventions, les équipes, les effectifs, les véhicules, les ressources et l'ensemble des opérations quotidiennes au sein d'une interface unique.",
        },
        { property: "og:type", content: "website" },
        { property: "og:url", content: "https://bces.axioneer.com" },
        {
          property: "og:image",
          content:
            "https://s3.axioneer.com/bces21-dispatch/images/background.webp",
        },
        { property: "og:site_name", content: "Dispatch • BCES" },
        // Twitter
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:title", content: "Dispatch • BCES" },
        {
          name: "twitter:description",
          content:
            "Dispatch BCES - Plateforme web tout-en-un dédiée à la gestion opérationnelle des services de secours, centralisant les interventions, les équipes, les effectifs, les véhicules, les ressources et l'ensemble des opérations quotidiennes au sein d'une interface unique.",
        },
        {
          name: "twitter:image",
          content:
            "https://s3.axioneer.com/bces21-dispatch/images/background.webp",
        },
        // Facebook
        { property: "fb:app_id", content: "" },
      ],
      link: [
        {
          rel: "icon",
          type: "image/png",
          href: "https://s3.axioneer.com/bces21-dispatch/images/favicon.png",
        },
      ],
    },
  },

  ui: {
    colorMode: false,
  },
  devServer: {
    host: "localhost",
  },
  nitro: {
    compressPublicAssets: true,
    routeRules: {
      "/api/**": {
        proxy: apiProxyBase + "/api/**",
      },
      "/ws/**": {
        proxy: apiProxyBase + "/ws/**",
      },
    },
  },

  runtimeConfig: {
    public: {
      apiBase: publicApiBase,
      discordAuthUrl:
        process.env.NUXT_PUBLIC_DISCORD_AUTH_URL || "/api/auth/discord/url",
      timezone: process.env.NUXT_PUBLIC_TIMEZONE || "Europe/Paris",
    },
  },
});
