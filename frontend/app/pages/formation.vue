<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Formation • BCES' })
</script>

<template>
  <main class="formation-page">
    <section class="formation-section">
      <div class="formation-section__heading">
        <h2>Formation</h2>
        <p>Une fiche par employé en formation : modules, questionnaire, simulations et passages de grade. Les pôles et spécialités sont dans Pôles &amp; Spé.</p>
      </div>
      <FormationPanel />
    </section>
  </main>
</template>

<style scoped>
.formation-page { flex: 1; min-height: 0; overflow: auto; padding: 16px; background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }
.formation-section { padding: clamp(16px, 2vw, 22px); border: 1px solid var(--dp-line); border-radius: 18px; background: linear-gradient(145deg, rgba(255,255,255,.025), transparent 55%), var(--dp-panel); box-shadow: 0 16px 40px rgba(0, 0, 0, .14); }
.formation-section__heading { margin-bottom: 16px; }
.formation-section h2 { margin: 0; font-size: 20px; letter-spacing: -.02em; }
.formation-section__heading p { margin: 6px 0 0; color: var(--dp-text-2); font-size: 13px; line-height: 1.6; }
</style>
