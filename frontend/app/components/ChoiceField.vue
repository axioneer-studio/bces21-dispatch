<script setup lang="ts">
/**
 * Liste de choix non exhaustive : une valeur de la liste, ou « Autre… » pour en
 * saisir une à la main. La valeur est émise quand on choisit dans la liste, ou à
 * la validation de la saisie (Entrée ou sortie du champ).
 */
const props = withDefaults(
  defineProps<{
    modelValue: string;
    options: string[];
    placeholder?: string;
    label: string;
    disabled?: boolean;
    maxlength?: number;
    /** Couleur « #rrggbb » qui teinte le menu (ex. celle du groupe choisi). */
    color?: string | null;
  }>(),
  {
    placeholder: "—",
    disabled: false,
    maxlength: 120,
    color: null,
  },
);

const emit = defineEmits<{ (e: "update:modelValue", value: string): void }>();

/** Teinte en style direct : elle passe devant les styles de menu de la page. */
const colorStyle = computed(() =>
  props.color
    ? { background: `color-mix(in srgb, ${props.color} 30%, var(--dp-bg))` }
    : undefined,
);

const OTHER = "__other__";
const typing = ref(false);
const draft = ref("");
const input = ref<HTMLInputElement | null>(null);

/** Les choix de la liste, plus la valeur actuelle si elle a été saisie à la main. */
const choices = computed(() => {
  const list = [...new Set(props.options.filter(Boolean))];
  if (props.modelValue && !list.includes(props.modelValue))
    list.unshift(props.modelValue);
  return list;
});

function onSelect(event: Event) {
  const value = (event.target as HTMLSelectElement).value;
  if (value === OTHER) {
    draft.value = "";
    typing.value = true;
    nextTick(() => input.value?.focus());
    (event.target as HTMLSelectElement).value = props.modelValue;
    return;
  }
  if (value !== props.modelValue) emit("update:modelValue", value);
}

function commit() {
  if (!typing.value) return;
  typing.value = false;
  const value = draft.value.trim();
  if (value && value !== props.modelValue) emit("update:modelValue", value);
}

function cancel() {
  typing.value = false;
}
</script>

<template>
  <input
    v-if="typing"
    ref="input"
    v-model="draft"
    class="choice-field"
    type="text"
    :maxlength="maxlength"
    :aria-label="label"
    placeholder="Saisir…"
    @blur="commit"
    @keydown.enter.prevent="commit"
    @keydown.esc.prevent="cancel"
  />
  <select
    v-else
    class="choice-field"
    :style="colorStyle"
    :value="modelValue"
    :aria-label="label"
    :disabled="disabled"
    @change="onSelect"
  >
    <option value="">{{ placeholder }}</option>
    <option v-for="choice in choices" :key="choice" :value="choice">
      {{ choice }}
    </option>
    <option :value="OTHER">Autre…</option>
  </select>
</template>

<style scoped>
.choice-field {
  width: 100%;
  min-width: 0;
  min-height: 32px;
  padding: 0 8px;
  border: 1px solid var(--dp-line);
  border-radius: 7px;
  color: var(--dp-text);
  background: var(--dp-bg);
  font: inherit;
  font-size: 11px;
}
.choice-field:focus-visible {
  border-color: var(--dp-accent-line);
  outline: 2px solid rgba(70, 153, 109, 0.24);
  outline-offset: 1px;
}
</style>
