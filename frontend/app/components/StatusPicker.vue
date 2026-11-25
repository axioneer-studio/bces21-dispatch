<script setup lang="ts">
import { findStatus, STATUS_KINDS } from '~/utils/statuses'

const props = defineProps<{ modelValue: string | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: string | null]
  close: []
}>()

const { snapshot } = useDispatchStore()
const search = ref('')
const groups = computed(() =>
  STATUS_KINDS
    .map((kind) => ({
      ...kind,
      items: snapshot.value.statuses.filter((status) => {
        if (status.kind !== kind.value) return false
        const query = search.value.trim().toLocaleLowerCase('fr')
        return !query || `${status.emoji} ${status.label}`.toLocaleLowerCase('fr').includes(query)
      })
    }))
    .filter((group) => group.items.length)
)
const selected = computed(() => findStatus(snapshot.value.statuses, props.modelValue))

function choose(value: string | null) {
  emit('update:modelValue', value)
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div class="status-overlay" @click.self="emit('close')" @keydown.esc="emit('close')">
      <section class="status-panel" role="dialog" aria-modal="true" aria-labelledby="status-title">
        <header class="status-header">
          <div class="status-header__icon"><Icon name="lucide:tags" size="18" /></div>
          <div>
            <h2 id="status-title">Statut de l’intervention</h2>
            <p>Choisissez le statut à afficher sur la carte.</p>
          </div>
          <button type="button" class="status-close" aria-label="Fermer" @click="emit('close')">
            <Icon name="lucide:x" size="16" />
          </button>
        </header>

        <div class="status-body">
          <div class="status-current">
            <span>Statut actuel</span>
            <strong :style="selected ? { '--current-color': selected.color } : undefined">
              {{ selected ? `${selected.emoji} ${selected.label}` : 'Sans statut' }}
            </strong>
          </div>

          <div class="status-search">
            <Icon name="lucide:search" size="16" />
            <input v-model="search" type="search" placeholder="Rechercher un statut…" aria-label="Rechercher un statut" />
            <button v-if="search" type="button" aria-label="Effacer la recherche" @click="search = ''">
              <Icon name="lucide:x" size="14" />
            </button>
          </div>

          <button
            type="button"
            class="status-option"
            v-if="!search.trim() || 'sans statut'.includes(search.trim().toLocaleLowerCase('fr'))"
            :class="{ 'is-selected': !modelValue }"
            @click="choose(null)"
          >
            <span class="status-option__dot" />
            <span>Sans statut</span>
            <Icon v-if="!modelValue" name="lucide:check" size="15" />
          </button>

          <section v-for="group in groups" :key="group.value" class="status-group">
            <h3>{{ group.label }}</h3>
            <button
              v-for="status in group.items"
              :key="status.id"
              type="button"
              class="status-option"
              :class="{ 'is-selected': status.key === modelValue }"
              :style="{ '--option-color': status.color }"
              @click="choose(status.key)"
            >
              <span class="status-option__dot" />
              <span>{{ status.emoji }} {{ status.label }}</span>
              <Icon v-if="status.key === modelValue" name="lucide:check" size="15" />
            </button>
          </section>
          <p v-if="!groups.some((group) => group.items.length) && search.trim() && !'sans statut'.includes(search.trim().toLocaleLowerCase('fr'))" class="status-empty">
            Aucun statut ne correspond à « {{ search }} ».
          </p>
        </div>

        <footer class="status-footer">
          <button type="button" class="status-cancel" @click="emit('close')">Annuler</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.status-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(5, 8, 11, .72);
  backdrop-filter: blur(8px);
  animation: status-fade .18s ease-out;
}

.status-panel {
  width: min(520px, 94vw);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--dp-line-strong);
  border-radius: 16px;
  background: var(--dp-panel);
  box-shadow: 0 24px 80px rgba(0, 0, 0, .55);
  animation: status-rise .22s cubic-bezier(.16, 1, .3, 1);
}

.status-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}

.status-header__icon {
  width: 40px;
  height: 40px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--dp-accent-line);
  border-radius: 10px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}

.status-header h2 { margin: 0; color: var(--dp-text); font-size: 17px; }
.status-header p { margin: 3px 0 0; color: var(--dp-text-2); font-size: 12px; }

.status-close {
  width: 34px;
  height: 34px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  margin-left: auto;
  border: 1px solid var(--dp-line);
  border-radius: 8px;
  color: var(--dp-text-2);
  background: transparent;
  cursor: pointer;
}

.status-close:hover, .status-cancel:hover { color: var(--dp-text); background: var(--dp-panel-3); }

.status-body { padding: 18px 22px; overflow-y: auto; }

.status-search {
  min-height: 42px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 14px;
  padding: 0 12px;
  border: 1px solid var(--dp-line-strong);
  border-radius: 9px;
  color: var(--dp-text-dim);
  background: var(--dp-bg);
}

.status-search:focus-within { border-color: var(--dp-accent-line); box-shadow: 0 0 0 2px var(--dp-accent-soft); }
.status-search input { flex: 1; min-width: 0; border: 0; outline: 0; color: var(--dp-text); background: transparent; font: inherit; font-size: 13px; }
.status-search input::placeholder { color: var(--dp-text-dim); }
.status-search button { display: grid; place-items: center; padding: 4px; border: 0; color: var(--dp-text-dim); background: transparent; cursor: pointer; }
.status-empty { padding: 14px 4px; color: var(--dp-text-dim); font-size: 13px; text-align: center; }

.status-current {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
  margin-bottom: 14px;
  padding: 13px 15px;
  border: 1px solid var(--dp-line);
  border-radius: 10px;
  background: var(--dp-panel-2);
}

.status-current span { color: var(--dp-text-2); font-size: 11px; font-weight: 600; text-transform: uppercase; }
.status-current strong { color: var(--current-color, var(--dp-accent)); font-size: 15px; text-align: left; }

.status-group { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--dp-line); }
.status-group h3 { margin: 0 0 6px; color: var(--dp-text-dim); font-size: 10px; text-transform: uppercase; letter-spacing: .07em; }

.status-option {
  width: 100%;
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 7px;
  color: var(--dp-text-2);
  background: transparent;
  font: inherit;
  font-size: 13px;
  text-align: left;
  justify-content: flex-start;
  cursor: pointer;
}

.status-option:hover, .status-option.is-selected {
  border-color: color-mix(in srgb, var(--option-color, var(--dp-accent)) 45%, var(--dp-line));
  color: var(--dp-text);
  background: color-mix(in srgb, var(--option-color, var(--dp-accent)) 16%, var(--dp-panel-2));
}

.status-option > span:nth-child(2) { flex: 1; }
.status-option > span { text-align: left; }
.status-option > :last-child { margin-left: auto; color: var(--option-color, var(--dp-accent)); }
.status-option__dot { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: var(--option-color, var(--dp-text-dim)); }

.status-footer { display: flex; justify-content: flex-end; padding: 14px 22px; border-top: 1px solid var(--dp-line); background: var(--dp-panel-2); }
.status-cancel { min-height: 38px; padding: 0 16px; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text-2); background: transparent; font-size: 13px; cursor: pointer; }

@keyframes status-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes status-rise { from { opacity: 0; transform: translateY(10px) scale(.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
