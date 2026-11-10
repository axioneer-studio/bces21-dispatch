<script setup lang="ts">
import type { FleetEntry, ParkingSpot, Vehicle } from '~/composables/useDispatchStore'
import { deleteFleetEntry, updateFleetEntry } from '~/composables/useDispatchApi'

const props = defineProps<{
  entries: FleetEntry[]
  vehicles: Vehicle[]
  parkingSpots: ParkingSpot[]
}>()

const toast = useAppToast()
const spotsListId = useId()

type TextField = 'location' | 'note'

/** Message d'erreur renvoyé par l'API (`detail`), sinon le message par défaut. */
function apiError(error: unknown, fallback: string): string {
  const detail = (error as { data?: { detail?: unknown } } | null)?.data?.detail
  return typeof detail === 'string' && detail ? detail : fallback
}

// --- Véhicule : uniquement dans la liste, un véhicule par ligne ---

const usedVehicleIds = computed(
  () => new Set(props.entries.flatMap((entry) => (entry.vehicle_id === null ? [] : [entry.vehicle_id])))
)

const vehicleName = (entry: FleetEntry) =>
  props.vehicles.find((vehicle) => vehicle.id === entry.vehicle_id)?.name ?? '—'

/** Véhicules proposés : ceux qui ne sont sur aucune autre ligne, plus celui de la ligne. */
function vehicleOptions(entry: FleetEntry): Vehicle[] {
  return props.vehicles.filter(
    (vehicle) => vehicle.id === entry.vehicle_id || !usedVehicleIds.value.has(vehicle.id)
  )
}

async function setVehicle(entry: FleetEntry, event: Event) {
  const select = event.target as HTMLSelectElement
  const vehicleId = select.value ? Number(select.value) : null
  if (vehicleId === entry.vehicle_id) return
  try {
    await updateFleetEntry(entry.id, { vehicle_id: vehicleId })
  } catch (error) {
    select.value = entry.vehicle_id === null ? '' : String(entry.vehicle_id)
    toast.error(apiError(error, 'Mise à jour du véhicule impossible.'))
  }
}

// --- Lieu et informations : texte enregistré à la sortie du champ ---

/** Saisie en cours, par champ (`<id>:<champ>`), pour ne pas être écrasée par le direct. */
const drafts = reactive<Record<string, string>>({})
/** Valeur envoyée au serveur, affichée en attendant sa confirmation. */
const pending = reactive<Record<string, string>>({})

const fieldKey = (entry: FleetEntry, field: TextField) => `${entry.id}:${field}`

function fieldValue(entry: FleetEntry, field: TextField): string {
  const key = fieldKey(entry, field)
  return drafts[key] ?? pending[key] ?? entry[field]
}

function startEdit(entry: FleetEntry, field: TextField) {
  drafts[fieldKey(entry, field)] = fieldValue(entry, field)
}

function onInput(entry: FleetEntry, field: TextField, event: Event) {
  drafts[fieldKey(entry, field)] = (event.target as HTMLInputElement).value
}

function cancelEdit(entry: FleetEntry, field: TextField, event: KeyboardEvent) {
  delete drafts[fieldKey(entry, field)]
  ;(event.target as HTMLInputElement).blur()
}

async function commit(entry: FleetEntry, field: TextField) {
  const key = fieldKey(entry, field)
  const draft = drafts[key]
  if (draft === undefined) return
  delete drafts[key]
  const value = draft.trim()
  if (value === entry[field]) return
  pending[key] = value
  try {
    await updateFleetEntry(entry.id, { [field]: value })
  } catch (error) {
    toast.error(apiError(error, 'Mise à jour de la ligne impossible.'))
  } finally {
    delete pending[key]
  }
}

function blurField(event: KeyboardEvent) {
  ;(event.target as HTMLInputElement).blur()
}

// --- Suppression ---

async function removeEntry(entry: FleetEntry) {
  const filled = entry.vehicle_id !== null || entry.location !== '' || entry.note !== ''
  if (filled && !window.confirm('Supprimer cette ligne de la flotte ?')) return
  try {
    await deleteFleetEntry(entry.id)
  } catch (error) {
    toast.error(apiError(error, 'Suppression de la ligne impossible.'))
  }
}
</script>

<template>
  <div class="fl">
    <div class="fl__table">
      <div class="fl__cols" aria-hidden="true">
        <span>Véhicule</span>
        <span>Lieu</span>
        <span>Informations</span>
        <span />
      </div>

      <div v-for="entry in entries" :key="entry.id" class="fl__row">
        <div class="fl__vehicle">
          <!-- Donne à la colonne la largeur du nom affiché (un <select> prendrait celle de sa plus longue option). -->
          <span class="fl__sizer" aria-hidden="true">{{ vehicleName(entry) }}</span>
          <select
            class="fl__field fl__select"
            :value="entry.vehicle_id ?? ''"
            aria-label="Véhicule"
            @change="setVehicle(entry, $event)"
          >
            <option value="">—</option>
            <option v-for="vehicle in vehicleOptions(entry)" :key="vehicle.id" :value="vehicle.id">
              {{ vehicle.name }}
            </option>
          </select>
          <Icon name="lucide:chevron-down" size="10" class="fl__chevron" aria-hidden="true" />
        </div>

        <div class="fl__location">
          <!-- Élargit la colonne au lieu le plus long, pour qu'il ne soit jamais coupé. -->
          <span class="fl__sizer" aria-hidden="true">{{ fieldValue(entry, 'location') || 'Lieu' }}</span>
          <input
            class="fl__field"
            type="text"
            :list="spotsListId"
            :value="fieldValue(entry, 'location')"
            maxlength="64"
            placeholder="Lieu"
            aria-label="Lieu"
            @focus="startEdit(entry, 'location')"
            @input="onInput(entry, 'location', $event)"
            @blur="commit(entry, 'location')"
            @keydown.enter="blurField"
            @keydown.esc="cancelEdit(entry, 'location', $event)"
          >
        </div>

        <input
          class="fl__field"
          type="text"
          :value="fieldValue(entry, 'note')"
          maxlength="500"
          placeholder="Informations"
          aria-label="Informations"
          @focus="startEdit(entry, 'note')"
          @input="onInput(entry, 'note', $event)"
          @blur="commit(entry, 'note')"
          @keydown.enter="blurField"
          @keydown.esc="cancelEdit(entry, 'note', $event)"
        >

        <button
          type="button"
          class="fl__delete"
          title="Supprimer la ligne"
          aria-label="Supprimer la ligne"
          @click="removeEntry(entry)"
        >
          <Icon name="lucide:trash-2" size="10" />
        </button>
      </div>

      <p v-if="!entries.length" class="fl__empty">
        Aucun véhicule. Ajoutez une ligne avec +.
      </p>
    </div>

    <!-- Emplacements proposés ; le champ Lieu accepte aussi du texte libre. -->
    <datalist :id="spotsListId">
      <option v-for="spot in parkingSpots" :key="spot.id" :value="spot.name" />
    </datalist>
  </div>
</template>

<style scoped>
.fl {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  /* Même fond que les cases voisines (bloc-notes, créneaux). */
  background: var(--dp-panel-2);
}

/*
 * Colonnes partagées par toutes les lignes (sous-grilles), dans l'ordre :
 * - Véhicule : 30 % au minimum, s'élargit jusqu'au nom affiché le plus long ;
 * - Lieu : tout l'espace restant, au minimum 10 % ou le lieu le plus long
 *   (le minimum « auto » de la piste 1fr suit le contenu ; les 10 % sont
 *   portés par le libellé de la colonne) ;
 * - Informations : 40 % par défaut, réduites si le véhicule ou le lieu prend de la place ;
 * - suppression.
 */
.fl__table {
  display: grid;
  flex: 1;
  container-type: inline-size;
  grid-template-columns: minmax(30%, max-content) 1fr minmax(0, 40%) 14px;
  align-content: start;
  column-gap: 3px;
  row-gap: 2px;
  min-height: 0;
  padding: 0 2px 2px;
  overflow-x: hidden;
  overflow-y: auto;
}

.fl__cols,
.fl__row {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: subgrid;
  column-gap: 5px;
  align-items: center;
  padding: 2px 4px;
  border: 1px solid transparent;
  border-radius: 3px;
}

.fl__cols {
  position: sticky;
  top: 0;
  z-index: 1;
  padding-top: 3px;
  padding-bottom: 3px;
  border-bottom-color: var(--dp-line);
  border-radius: 0;
  background: var(--dp-panel-2);
  color: var(--dp-text-dim);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.fl__row {
  background: transparent;
  border-color: var(--dp-line);
}

/* Libellés alignés sur le texte des champs (marge intérieure + bordure). */
.fl__cols > span {
  padding: 0 5px;
}

/* 10 % de la largeur du tableau : minimum de la colonne Lieu. */
.fl__cols > span:nth-child(2) {
  min-width: 10cqw;
}

/* Trait vertical dans l'espace entre Véhicule | Lieu | Informations. */
.fl__cols > span:nth-child(2),
.fl__cols > span:nth-child(3),
.fl__row > .fl__location,
.fl__row > .fl__field {
  box-shadow: -3px 0 0 -2px var(--dp-line-strong);
}

.fl__vehicle {
  position: relative;
  min-width: 0;
}

/* Pas de min-width: 0 ici : la colonne doit garder la largeur du texte. */
.fl__location {
  position: relative;
}

.fl__location .fl__sizer {
  padding-right: 5px;
  overflow: visible;
}

.fl__location .fl__field {
  position: absolute;
  inset: 0;
}

/*
 * Même police et mêmes marges que le champ (marge intérieure + bordure).
 * Pour le véhicule : 18 px de flèche + 2 px de marge, pour éviter les « … ».
 */
.fl__sizer {
  display: block;
  height: 20px;
  padding: 0 21px 0 5px;
  overflow: hidden;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
  visibility: hidden;
}

.fl__vehicle .fl__select {
  position: absolute;
  inset: 0;
}

.fl__row:hover {
  border-color: var(--dp-line-strong);
}

.fl__field {
  width: 100%;
  min-width: 0;
  height: 20px;
  padding: 0 4px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: var(--dp-text-2);
  font: inherit;
  font-size: 10px;
  font-weight: 600;
  text-overflow: ellipsis;
}

.fl__field::placeholder {
  color: var(--dp-text-dim);
  font-weight: 400;
  opacity: 0.6;
}

.fl__field:hover {
  background: var(--dp-panel-3);
  border-color: var(--dp-line-strong);
}

.fl__field:focus {
  outline: none;
  background: var(--dp-panel-3);
  border-color: var(--dp-accent-line);
  color: var(--dp-text);
}

/* Flèche dessinée par l'icône, de largeur fixe (la flèche native varie selon le navigateur). */
.fl__select {
  appearance: none;
  padding-right: 18px;
  cursor: pointer;
}

.fl__chevron {
  position: absolute;
  top: 50%;
  right: 5px;
  color: var(--dp-text-dim);
  pointer-events: none;
  transform: translateY(-50%);
}

.fl__vehicle:hover .fl__chevron,
.fl__select:focus + .fl__chevron {
  color: var(--dp-text);
}

.fl__select option {
  background: var(--dp-panel-3);
  color: var(--dp-text);
}

.fl__delete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 18px;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--dp-text-dim);
  cursor: pointer;
  opacity: 0;
}

.fl__row:hover .fl__delete,
.fl__delete:focus-visible {
  opacity: 1;
}

.fl__delete:hover {
  color: var(--dp-danger);
}

.fl__empty {
  grid-column: 1 / -1;
  margin: 0;
  padding: 12px;
  color: var(--dp-text-dim);
  font-size: 10px;
  font-style: italic;
  text-align: center;
}
</style>
