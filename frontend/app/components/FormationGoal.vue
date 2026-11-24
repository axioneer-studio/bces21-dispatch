<script setup lang="ts">
/**
 * Seuil du passage d'une barre de progression (en %) ou d'une note (sur 20),
 * commun à toutes les fiches de la page Formation. Ceux qui gèrent la formation
 * le modifient ici ; les autres le lisent. `save` renvoie false si
 * l'enregistrement échoue : le champ reprend alors l'ancien seuil.
 */
const props = withDefaults(
  defineProps<{
    value: number
    max: number
    unit: string
    label: string
    step?: number
    editable?: boolean
    disabled?: boolean
    save?: (value: number) => Promise<boolean>
  }>(),
  { step: 1, editable: false, disabled: false, save: undefined }
)

/** Un seuil à 0 n'exige rien : il ne s'affiche que pour ceux qui le modifient. */
const shown = computed(() => props.editable || props.value > 0)

async function commit(event: Event) {
  const field = event.target as HTMLInputElement
  const value = Number(field.value)
  if (field.value === '' || !Number.isFinite(value) || value < 0 || value > props.max) {
    field.value = String(props.value)
    return
  }
  if (value === props.value || !props.save) return
  if (!(await props.save(value))) field.value = String(props.value)
}
</script>

<template>
  <span class="formation-goal" :title="shown ? `Seuil requis pour le passage (${label}), commun à toutes les fiches` : undefined">
    <template v-if="editable">
      requis
      <input
        type="number"
        :value="value"
        min="0"
        :max="max"
        :step="step"
        :disabled="disabled"
        :aria-label="`Seuil requis pour le passage : ${label}`"
        @change="commit"
      >
      {{ unit }}
    </template>
    <template v-else-if="shown">requis {{ value }} {{ unit }}</template>
  </span>
</template>

<style scoped>
.formation-goal { display: inline-flex; width: var(--formation-goal-width, 116px); align-items: center; justify-content: flex-end; gap: 4px; color: var(--dp-text-dim); font-size: 10px; font-weight: 500; white-space: nowrap; }
.formation-goal input { width: 46px; min-height: 24px; box-sizing: border-box; padding: 0 4px; border: 1px solid var(--dp-line); border-radius: 6px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; font-variant-numeric: tabular-nums; text-align: right; }
.formation-goal input:focus { border-color: var(--dp-accent-line); outline: none; }
</style>
