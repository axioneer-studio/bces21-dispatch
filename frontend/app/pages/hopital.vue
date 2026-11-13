<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Hôpital • BCES' })

const hospitalSections = [
  { key: 'rooms', label: 'Chambres', icon: 'lucide:bed-double', title: 'Chambres', description: 'Occupation des chambres de l’hôpital.' },
  { key: 'morgue', label: 'Morgue', icon: 'lucide:snowflake', title: 'Morgue', description: 'Corps en cellule réfrigérée et urnes des défunts incinérés.' }
] as const

type HospitalSection = (typeof hospitalSections)[number]['key']

const activeSection = ref<HospitalSection>('rooms')

function moveSectionTab(step: -1 | 1) {
  const index = hospitalSections.findIndex((section) => section.key === activeSection.value)
  const next = hospitalSections[(index + step + hospitalSections.length) % hospitalSections.length]
  if (!next) return
  activeSection.value = next.key
  nextTick(() => document.querySelector<HTMLElement>(`#hospital-tab-${next.key}`)?.focus())
}
</script>

<template>
  <main class="hospital-page">
    <nav class="hospital-nav" role="tablist" aria-label="Sections de l’hôpital" @keydown.left.prevent="moveSectionTab(-1)" @keydown.right.prevent="moveSectionTab(1)">
      <button
        v-for="section in hospitalSections"
        :id="`hospital-tab-${section.key}`"
        :key="section.key"
        type="button"
        role="tab"
        :aria-selected="activeSection === section.key"
        :aria-controls="`hospital-${section.key}`"
        :tabindex="activeSection === section.key ? 0 : -1"
        :class="{ 'is-active': activeSection === section.key }"
        @click="activeSection = section.key"
      >
        <Icon :name="section.icon" size="16" /> {{ section.label }}
      </button>
    </nav>

    <section
      v-for="section in hospitalSections"
      v-show="activeSection === section.key"
      :id="`hospital-${section.key}`"
      :key="section.key"
      class="hospital-section"
      role="tabpanel"
      :aria-labelledby="`hospital-tab-${section.key}`"
    >
      <div class="hospital-section__heading">
        <h2>{{ section.title }}</h2>
        <p>{{ section.description }}</p>
      </div>
      <RoomsPanel v-if="section.key === 'rooms'" :active="activeSection === 'rooms'" />
      <MorguePanel v-else :active="activeSection === 'morgue'" />
    </section>
  </main>
</template>

<style scoped>
.hospital-page { flex: 1; min-height: 0; overflow: auto; padding: 16px; background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }

.hospital-nav { display: flex; gap: 6px; margin-bottom: 14px; padding: 7px; overflow-x: auto; border: 1px solid var(--dp-line); border-radius: 14px; background: var(--dp-panel); }
.hospital-nav button { display: inline-flex; min-height: 42px; align-items: center; gap: 8px; padding: 0 14px; border: 1px solid transparent; border-radius: 9px; color: var(--dp-text-2); background: transparent; font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; white-space: nowrap; transition: background .15s ease, color .15s ease; }
.hospital-nav button:hover { color: var(--dp-text); background: var(--dp-panel-2); }
.hospital-nav button.is-active { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.hospital-nav button:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: -2px; }

.hospital-section { padding: clamp(16px, 2vw, 22px); border: 1px solid var(--dp-line); border-radius: 18px; background: linear-gradient(145deg, rgba(255,255,255,.025), transparent 55%), var(--dp-panel); box-shadow: 0 16px 40px rgba(0, 0, 0, .14); }
.hospital-section__heading { margin-bottom: 18px; }
.hospital-section h2 { margin: 0; font-size: 20px; letter-spacing: -.02em; }
.hospital-section__heading p { margin: 6px 0 0; color: var(--dp-text-2); font-size: 13px; line-height: 1.6; }
.hospital-empty { display: grid; min-height: 170px; justify-items: center; align-content: center; gap: 9px; padding: 24px; border: 1px dashed var(--dp-line-strong); border-radius: 14px; color: var(--dp-text-dim); text-align: center; font-size: 12px; }
.hospital-empty p { margin: 0; }
</style>
