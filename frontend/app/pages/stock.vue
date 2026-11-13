<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Stock • BCES' })
</script>

<template>
  <main class="stock-page">
    <section class="stock-section">
      <div class="stock-section__heading">
        <h1>Stock</h1>
        <p>Gestion des stocks du BCES</p>
      </div>
      <div class="stock-empty">
        <Icon name="lucide:package" size="21" />
        <p>À venir.</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.stock-page { flex: 1; min-height: 0; overflow: auto; padding: 16px; background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }

.stock-section { padding: clamp(16px, 2vw, 22px); border: 1px solid var(--dp-line); border-radius: 18px; background: linear-gradient(145deg, rgba(255,255,255,.025), transparent 55%), var(--dp-panel); box-shadow: 0 16px 40px rgba(0, 0, 0, .14); }
.stock-section__heading { margin-bottom: 18px; }
.stock-section h1 { margin: 0; font-size: 20px; letter-spacing: -.02em; }
.stock-section__heading p { margin: 6px 0 0; color: var(--dp-text-2); font-size: 13px; line-height: 1.6; }
.stock-empty { display: grid; min-height: 170px; justify-items: center; align-content: center; gap: 9px; padding: 24px; border: 1px dashed var(--dp-line-strong); border-radius: 14px; color: var(--dp-text-dim); text-align: center; font-size: 12px; }
.stock-empty p { margin: 0; }
</style>