<script setup lang="ts">
import ConfirmDialog from '~/components/ConfirmDialog.vue'

definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Crise • BCES' })

interface CrisisEmployee {
  id: number
  name: string
}

interface CrisisBed {
  id: number
  label: string
  patient_name: string | null
}

interface CrisisVictim {
  id: number
  full_name: string
  affiliation: string
  coma: boolean
  severe: boolean
  unconscious: boolean
  injuries: string
  repatriating_doctor: string
  treating_doctor: string
  arrived_at: string | null
  care_done: boolean
  channel_added: boolean
  bed_id: number | null
  created_at: string
}

interface CrisisData {
  zip_code: string | null
  primo: CrisisEmployee | null
  helpers: CrisisEmployee[]
  victims: CrisisVictim[]
  employees: CrisisEmployee[]
  beds: CrisisBed[]
  groups: string[]
}

type VictimText = 'full_name' | 'affiliation' | 'injuries' | 'repatriating_doctor' | 'treating_doctor'
type VictimFlag = 'coma' | 'severe' | 'unconscious' | 'care_done' | 'channel_added'
type VictimPatch = Partial<Record<VictimText, string> & Record<VictimFlag, boolean>> & {
  arrived?: boolean
  bed_id?: number | null
}

const toast = useAppToast()

/** Code postal de la crise : celui de l'intervention « Primo » du Dispatch quand elle existe. */
const zipCode = ref<string | null>(null)
const zipDraft = ref('')
const zipInput = ref<HTMLInputElement | null>(null)
const primo = ref<CrisisEmployee | null>(null)
const helpers = ref<CrisisEmployee[]>([])
const victims = ref<CrisisVictim[]>([])
const employees = ref<CrisisEmployee[]>([])
const beds = ref<CrisisBed[]>([])
/** Groupes gérés dans Administration, proposés pour l'appartenance. */
const groups = ref<string[]>([])
const loaded = ref(false)
const loadError = ref('')
/** Requêtes en cours : le rafraîchissement attend qu'elles soient finies. */
const pending = ref(0)
const table = ref<HTMLElement | null>(null)

const resetVisible = ref(false)
const resetting = ref(false)
const victimToDelete = ref<CrisisVictim | null>(null)

function groupKey(victim: CrisisVictim) {
  return victim.affiliation.trim().toLocaleLowerCase('fr')
}

/**
 * Blessés regroupés par appartenance : les groupes dans l'ordre où ils sont
 * apparus, et dans chaque groupe les blessés dans l'ordre de saisie (le plus
 * récent en bas de son groupe). Les appartenances inconnues forment un groupe.
 */
const sortedByCreation = computed(() =>
  [...victims.value].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id - b.id)
)

const sortedVictims = computed(() => {
  const byCreation = sortedByCreation.value
  const groupRank = new Map<string, number>()
  for (const victim of byCreation) {
    if (!groupRank.has(groupKey(victim))) groupRank.set(groupKey(victim), groupRank.size)
  }
  return byCreation
    .map((victim, index) => ({ victim, index }))
    .sort((a, b) => groupRank.get(groupKey(a.victim))! - groupRank.get(groupKey(b.victim))! || a.index - b.index)
    .map(({ victim }) => victim)
})

/** Arrivé à l'hôpital depuis le plus longtemps sans médecin soignant : à prendre en charge en premier. */
const nextToTreatId = computed(() => {
  const waiting = victims.value.filter((victim) => victim.arrived_at && !victim.treating_doctor && !victim.care_done)
  waiting.sort((a, b) => Date.parse(a.arrived_at!) - Date.parse(b.arrived_at!) || a.id - b.id)
  return waiting[0]?.id ?? null
})

/** Heure de saisie de la première ligne de la crise. */
const firstEntryAt = computed(() => sortedByCreation.value[0]?.created_at ?? null)

const counts = computed(() => ({
  total: victims.value.length,
  severe: victims.value.filter((victim) => victim.severe).length,
  arrived: victims.value.filter((victim) => victim.arrived_at).length,
  cared: victims.value.filter((victim) => victim.care_done).length
}))

/** Agents qu'on peut encore ajouter à l'équipe. */
const availableHelpers = computed(() => {
  const taken = new Set([primo.value?.id, ...helpers.value.map((helper) => helper.id)])
  return employees.value.filter((employee) => !taken.has(employee.id))
})

const doctorOptions = computed(() => [
  ...employees.value.map((employee) => employee.name),
  ...victims.value.flatMap((victim) => [victim.repatriating_doctor, victim.treating_doctor])
])

/**
 * Lits proposés au blessé : les lits libres de l'onglet Chambres, plus le sien.
 * Un lit choisi ici y installe le blessé, il n'est donc plus libre pour les autres.
 */
function bedChoices(victim: CrisisVictim) {
  return beds.value.filter((bed) => !bed.patient_name || bed.id === victim.bed_id)
}

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === 'object' && cause !== null && 'data' in cause) {
    const data = cause.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
  }
  return fallback
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

async function load() {
  try {
    const data = await $fetch<CrisisData>('/api/crisis', { credentials: 'include' })
    zipCode.value = data.zip_code
    if (document.activeElement !== zipInput.value) zipDraft.value = data.zip_code ?? ''
    primo.value = data.primo
    helpers.value = data.helpers
    victims.value = data.victims
    employees.value = data.employees
    beds.value = data.beds
    groups.value = data.groups
    loadError.value = ''
  } catch (cause) {
    loadError.value = messageFromError(cause, 'Impossible de charger la crise.')
  } finally {
    loaded.value = true
  }
}

/** Rafraîchissement en arrière-plan, sauf pendant une saisie dans le tableau. */
function refresh() {
  if (pending.value > 0 || resetVisible.value || victimToDelete.value) return
  if (table.value?.contains(document.activeElement)) return
  void load()
}

let refreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  refreshTimer = setInterval(refresh, 5_000)
  window.addEventListener('focus', refresh)
  void load()
})
onBeforeUnmount(() => {
  clearInterval(refreshTimer)
  window.removeEventListener('focus', refresh)
})

async function request<T>(action: () => Promise<T>, failure: string): Promise<T | undefined> {
  pending.value += 1
  try {
    return await action()
  } catch (cause) {
    toast.error(messageFromError(cause, failure))
    await load()
    return undefined
  } finally {
    pending.value -= 1
  }
}

// --- Équipe ---

async function saveTeam(nextPrimo: CrisisEmployee | null, nextHelpers: CrisisEmployee[]) {
  const previous = { primo: primo.value, helpers: helpers.value }
  primo.value = nextPrimo
  helpers.value = nextHelpers.filter((helper) => helper.id !== nextPrimo?.id)
  const done = await request(
    () => $fetch('/api/crisis/team', {
      method: 'PUT',
      credentials: 'include',
      body: { primo_id: nextPrimo?.id ?? null, helper_ids: helpers.value.map((helper) => helper.id) }
    }),
    'Impossible de mettre à jour l’équipe.'
  )
  if (done === undefined) {
    primo.value = previous.primo
    helpers.value = previous.helpers
  }
}

async function saveZip() {
  const value = zipDraft.value.trim() || null
  zipDraft.value = value ?? ''
  if (value === zipCode.value) return
  const previous = zipCode.value
  zipCode.value = value
  const done = await request(
    () => $fetch('/api/crisis/zip', { method: 'PUT', credentials: 'include', body: { zip_code: value } }),
    'Impossible d’enregistrer le code postal.'
  )
  if (done === undefined) {
    zipCode.value = previous
    zipDraft.value = previous ?? ''
  }
}

function onPrimoChange(event: Event) {
  const id = Number((event.target as HTMLSelectElement).value)
  void saveTeam(employees.value.find((employee) => employee.id === id) ?? null, helpers.value)
}

function onHelperAdd(event: Event) {
  const select = event.target as HTMLSelectElement
  const employee = employees.value.find((item) => item.id === Number(select.value))
  select.value = ''
  if (employee) void saveTeam(primo.value, [...helpers.value, employee])
}

function removeHelper(helper: CrisisEmployee) {
  void saveTeam(primo.value, helpers.value.filter((item) => item.id !== helper.id))
}

// --- Blessés ---

async function patchVictim(victim: CrisisVictim, patch: VictimPatch) {
  const updated = await request(
    () => $fetch<CrisisVictim>(`/api/crisis/victims/${victim.id}`, { method: 'PATCH', credentials: 'include', body: patch }),
    'Impossible d’enregistrer le blessé.'
  )
  if (updated) Object.assign(victim, updated)
  // Lit choisi, ou libéré une fois soigné : la liste des lits libres change.
  if (updated && ('bed_id' in patch || patch.care_done)) await load()
}

function onText(victim: CrisisVictim, field: VictimText, event: Event) {
  const value = (event.target as HTMLInputElement | HTMLTextAreaElement).value.trim()
  if (value === victim[field]) return
  victim[field] = value
  void patchVictim(victim, { [field]: value })
}

function setText(victim: CrisisVictim, field: VictimText, value: string) {
  victim[field] = value
  void patchVictim(victim, { [field]: value })
}

function toggleFlag(victim: CrisisVictim, field: VictimFlag) {
  victim[field] = !victim[field]
  // « Canal » suit « Soigné » : le serveur le décoche aussi quand on décoche « Soigné ».
  if (field === 'care_done' && !victim.care_done) victim.channel_added = false
  // Soigné : le blessé quitte son lit de l'onglet Chambres.
  if (field === 'care_done' && victim.care_done) victim.bed_id = null
  void patchVictim(victim, { [field]: victim[field] })
}

/** Soigné et ajouté au canal : la ligne est terminée et grisée. Soigné seul : à ajouter au canal. */
function rowState(victim: CrisisVictim) {
  if (victim.care_done && victim.channel_added) return 'is-done'
  if (victim.care_done) return 'is-cared'
  return ''
}

function toggleArrived(victim: CrisisVictim) {
  void patchVictim(victim, { arrived: !victim.arrived_at })
}

function onBed(victim: CrisisVictim, event: Event) {
  const raw = (event.target as HTMLSelectElement).value
  const bedId = raw ? Number(raw) : null
  victim.bed_id = bedId
  void patchVictim(victim, { bed_id: bedId })
}

async function addVictim() {
  const created = await request(
    () => $fetch<CrisisVictim>('/api/crisis/victims', { method: 'POST', credentials: 'include', body: {} }),
    'Impossible d’ajouter un blessé.'
  )
  if (!created) return
  victims.value.push(created)
  await nextTick()
  table.value?.querySelector<HTMLInputElement>(`#crisis-name-${created.id}`)?.focus()
}

async function deleteVictim() {
  const victim = victimToDelete.value
  victimToDelete.value = null
  if (!victim) return
  const done = await request(
    () => $fetch(`/api/crisis/victims/${victim.id}`, { method: 'DELETE', credentials: 'include' }),
    'Impossible de retirer le blessé.'
  )
  if (done !== undefined) {
    victims.value = victims.value.filter((item) => item.id !== victim.id)
    if (victim.bed_id !== null) await load()
  }
}

async function resetCrisis() {
  if (resetting.value) return
  resetting.value = true
  const done = await request(
    () => $fetch('/api/crisis/reset', { method: 'POST', credentials: 'include' }),
    'Réinitialisation de la crise impossible.'
  )
  resetting.value = false
  if (done === undefined) return
  await load()
  toast.success('Crise réinitialisée : liste des blessés et équipe vidées, lits libérés.')
}
</script>

<template>
  <main class="crisis-page">
    <section class="crisis-bar">
      <div class="crisis-bar__title">
        <span class="crisis-bar__icon"><Icon name="lucide:siren" size="18" /></span>
        <div>
          <h1>Crise</h1>
          <p>
            {{ counts.total }} blessé{{ counts.total > 1 ? 's' : '' }} ·
            {{ counts.severe }} grave{{ counts.severe > 1 ? 's' : '' }} ·
            {{ counts.arrived }} arrivé{{ counts.arrived > 1 ? 's' : '' }} ·
            {{ counts.cared }} soigné{{ counts.cared > 1 ? 's' : '' }}
          </p>
          <p class="crisis-bar__start">
            <Icon name="lucide:clock" size="12" />
            {{ firstEntryAt ? `Première ligne à ${formatTime(firstEntryAt)}` : 'Aucune ligne' }}
          </p>
        </div>
      </div>

      <div class="crisis-team">
        <label class="crisis-team__zip">
          <span>ZIP</span>
          <input
            ref="zipInput"
            v-model="zipDraft"
            type="text"
            maxlength="16"
            placeholder="—"
            @change="saveZip"
            @keydown.enter="zipInput?.blur()"
          >
        </label>
        <label class="crisis-team__primo">
          <span>Primo Intervenant</span>
          <select :value="primo?.id ?? ''" @change="onPrimoChange">
            <option value="">Aucun</option>
            <option v-for="employee in employees" :key="employee.id" :value="employee.id">{{ employee.name }}</option>
          </select>
        </label>
        <div class="crisis-team__helpers">
          <span>Agents en assistance</span>
          <div class="crisis-team__chips">
            <span v-for="helper in helpers" :key="helper.id" class="crisis-chip">
              {{ helper.name }}
              <button type="button" :aria-label="`Retirer ${helper.name} de l’équipe`" @click="removeHelper(helper)">
                <Icon name="lucide:x" size="12" />
              </button>
            </span>
            <select v-if="availableHelpers.length" class="crisis-team__add" aria-label="Ajouter un agent en assistance" value="" @change="onHelperAdd">
              <option value="">+ Ajouter un agent</option>
              <option v-for="employee in availableHelpers" :key="employee.id" :value="employee.id">{{ employee.name }}</option>
            </select>
          </div>
        </div>
      </div>

      <button type="button" class="crisis-reset" :disabled="resetting" @click="resetVisible = true">
        <Icon name="lucide:tornado" size="14" />
        {{ resetting ? 'Réinitialisation…' : 'Tempête' }}
      </button>
    </section>

    <section class="crisis-list">
      <p v-if="loadError" class="crisis-error"><Icon name="lucide:circle-alert" size="15" /> {{ loadError }}</p>
      <div v-else-if="!loaded" class="crisis-empty"><Icon name="lucide:loader-circle" size="20" class="crisis-spin" /></div>
      <template v-else>
        <div ref="table" class="crisis-table-wrap">
          <table class="crisis-table">
            <thead>
              <tr>
                <th class="is-check">Canal</th>
                <th class="is-bed">Chambre</th>
                <th class="is-name">Nom Prénom</th>
                <th class="is-choice">Appartenance</th>
                <th class="is-check"><span class="crisis-check-head">Coma</span></th>
                <th class="is-check"><span class="crisis-check-head">Grave</span></th>
                <th class="is-check"><span class="crisis-check-head">Inconscient</span></th>
                <th class="is-injuries">Analyse des blessures</th>
                <th class="is-choice">Médecin rapatrie</th>
                <th class="is-choice">Médecin soignant</th>
                <th class="is-check">Arrivé</th>
                <th class="is-time">Heure</th>
                <th class="is-check">Soigné</th>
                <th class="is-action"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="victim in sortedVictims"
                :key="victim.id"
                :class="[rowState(victim), { 'is-severe': victim.severe, 'is-next': victim.id === nextToTreatId }]"
                :title="victim.id === nextToTreatId ? 'Arrivé depuis le plus longtemps sans médecin soignant' : undefined"
              >
                <td class="is-check">
                  <input
                    type="checkbox"
                    :checked="victim.channel_added"
                    :disabled="!victim.care_done"
                    aria-label="Ajouté au canal"
                    :title="victim.care_done ? 'Ajouté au canal' : 'Cochez « Soigné » avant « Canal »'"
                    @change="toggleFlag(victim, 'channel_added')"
                  >
                </td>
                <td class="is-bed">
                  <select
                    :value="victim.bed_id ?? ''"
                    aria-label="Chambre"
                    :disabled="victim.care_done"
                    :title="victim.care_done ? 'Blessé soigné : il a quitté son lit' : 'Lit où installer le blessé (onglet Chambres)'"
                    @change="onBed(victim, $event)"
                  >
                    <option value="">—</option>
                    <option v-for="bed in bedChoices(victim)" :key="bed.id" :value="bed.id">{{ bed.label }}</option>
                  </select>
                </td>
                <td class="is-name">
                  <input
                    :id="`crisis-name-${victim.id}`"
                    type="text"
                    maxlength="120"
                    :value="victim.full_name"
                    placeholder="Inconnu"
                    aria-label="Nom et prénom"
                    @change="onText(victim, 'full_name', $event)"
                    @keydown.enter="($event.target as HTMLInputElement).blur()"
                  >
                </td>
                <td class="is-choice">
                  <ChoiceField
                    :model-value="victim.affiliation"
                    :options="groups"
                    :maxlength="64"
                    placeholder="Inconnue"
                    label="Appartenance"
                    @update:model-value="setText(victim, 'affiliation', $event)"
                  />
                </td>
                <td class="is-check">
                  <input type="checkbox" :checked="victim.coma" aria-label="Coma" @change="toggleFlag(victim, 'coma')">
                </td>
                <td class="is-check">
                  <input type="checkbox" :checked="victim.severe" aria-label="Blessure grave" @change="toggleFlag(victim, 'severe')">
                </td>
                <td class="is-check">
                  <input type="checkbox" :checked="victim.unconscious" aria-label="Inconscient" @change="toggleFlag(victim, 'unconscious')">
                </td>
                <td class="is-injuries">
                  <input
                    type="text"
                    maxlength="500"
                    :value="victim.injuries"
                    placeholder="Type de balle, localisation, allergies…"
                    aria-label="Analyse des blessures"
                    @change="onText(victim, 'injuries', $event)"
                    @keydown.enter="($event.target as HTMLInputElement).blur()"
                  >
                </td>
                <td class="is-choice">
                  <ChoiceField
                    :model-value="victim.repatriating_doctor"
                    :options="doctorOptions"
                    label="Médecin qui rapatrie"
                    @update:model-value="setText(victim, 'repatriating_doctor', $event)"
                  />
                </td>
                <td class="is-choice">
                  <ChoiceField
                    :model-value="victim.treating_doctor"
                    :options="doctorOptions"
                    label="Médecin soignant"
                    @update:model-value="setText(victim, 'treating_doctor', $event)"
                  />
                </td>
                <td class="is-check">
                  <input type="checkbox" :checked="Boolean(victim.arrived_at)" aria-label="Arrivé à l’hôpital" @change="toggleArrived(victim)">
                </td>
                <td class="is-time">{{ victim.arrived_at ? formatTime(victim.arrived_at) : '' }}</td>
                <td class="is-check">
                  <input type="checkbox" :checked="victim.care_done" aria-label="Soins terminés" @change="toggleFlag(victim, 'care_done')">
                </td>
                <td class="is-action">
                  <button type="button" class="crisis-delete" :aria-label="`Retirer ${victim.full_name || 'ce blessé'} de la liste`" @click="victimToDelete = victim">
                    <Icon name="lucide:trash-2" size="14" />
                  </button>
                </td>
              </tr>
              <tr v-if="!victims.length" class="crisis-table__empty">
                <td colspan="14">Aucun blessé pour l’instant.</td>
              </tr>
            </tbody>
          </table>
        </div>
        <button type="button" class="crisis-add" :disabled="pending > 0" @click="addVictim">
          <Icon name="lucide:user-plus" size="14" /> Ajouter un blessé
        </button>
      </template>
    </section>

    <Teleport to="body">
      <ConfirmDialog
        v-model:visible="resetVisible"
        title="Réinitialiser la crise ?"
        message="La liste des blessés sera vidée, le Primo et les agents retirés de l’équipe, et les lits occupés par la crise libérés."
        confirm-label="Tempête"
        danger
        @confirm="resetCrisis"
        @cancel="resetVisible = false"
      />
      <ConfirmDialog
        :visible="Boolean(victimToDelete)"
        title="Retirer ce blessé ?"
        :message="`${victimToDelete?.full_name || 'Ce blessé'} sera retiré de la liste.`"
        confirm-label="Retirer"
        danger
        @confirm="deleteVictim"
        @cancel="victimToDelete = null"
      />
    </Teleport>
  </main>
</template>

<style scoped>
.crisis-page { display: flex; flex: 1; min-height: 0; flex-direction: column; gap: 12px; overflow: auto; padding: 16px; background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }

.crisis-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 14px 22px; padding: 14px 16px; border: 1px solid var(--dp-line); border-radius: 16px; background: var(--dp-panel); }
.crisis-bar__title { display: flex; align-items: center; gap: 11px; }
.crisis-bar__icon { display: grid; width: 38px; height: 38px; place-items: center; border: 1px solid var(--dp-danger-line); border-radius: 11px; color: var(--dp-danger); background: var(--dp-danger-soft); }
.crisis-bar h1 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
.crisis-bar__title p { margin: 3px 0 0; color: var(--dp-text-dim); font-size: 11px; }
.crisis-bar__title .crisis-bar__start { display: flex; align-items: center; gap: 5px; color: var(--dp-text-2); font-variant-numeric: tabular-nums; }
.crisis-team__zip { display: grid; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.crisis-team__zip input { width: 90px; min-height: 34px; padding: 0 9px; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; font-variant-numeric: tabular-nums; }
.crisis-team__zip input:focus-visible { border-color: var(--dp-accent-line); outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }

.crisis-team { display: flex; flex: 1; flex-wrap: wrap; align-items: flex-start; gap: 12px 18px; min-width: 0; }
.crisis-team__primo, .crisis-team__helpers { display: grid; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.crisis-team__primo select, .crisis-team__add { min-height: 34px; padding: 0 9px; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; }
.crisis-team__primo select { min-width: 190px; }
.crisis-team__chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.crisis-chip { display: inline-flex; align-items: center; gap: 4px; min-height: 28px; padding: 0 4px 0 10px; border: 1px solid var(--dp-accent-line); border-radius: 14px; color: var(--dp-text); background: var(--dp-accent-soft); font-size: 11px; }
.crisis-chip button { display: grid; width: 20px; height: 20px; place-items: center; border: 0; border-radius: 50%; color: var(--dp-text-2); background: transparent; cursor: pointer; }
.crisis-chip button:hover { color: var(--dp-danger); background: var(--dp-danger-soft); }

.crisis-reset { display: inline-flex; min-height: 36px; align-items: center; gap: 7px; margin-left: auto; padding: 0 14px; border: 1px solid var(--dp-danger-line); border-radius: 9px; color: var(--dp-danger); background: var(--dp-danger-soft); font-size: 11px; font-weight: 700; cursor: pointer; }
.crisis-reset:disabled { opacity: .5; cursor: not-allowed; }

.crisis-list { display: grid; gap: 10px; min-width: 0; padding: 12px; border: 1px solid var(--dp-line); border-radius: 16px; background: var(--dp-panel); }
.crisis-table-wrap { overflow-x: auto; border: 1px solid var(--dp-line); border-radius: 11px; }
.crisis-table { width: 100%; min-width: 1380px; border-collapse: collapse; font-size: 11px; }
.crisis-table th { position: sticky; top: 0; padding: 9px 6px; border-bottom: 1px solid var(--dp-line-strong); color: var(--dp-text-2); background: var(--dp-panel-2); font-size: 10px; font-weight: 700; text-align: center; white-space: nowrap; }
.crisis-table td { padding: 5px 6px; border-bottom: 1px solid var(--dp-line); vertical-align: middle; }
.crisis-table tbody tr:last-child td { border-bottom: 0; }
.crisis-table tbody tr.is-severe td:first-child { box-shadow: inset 3px 0 0 var(--dp-danger); }
.crisis-table tbody tr.is-cared td { background: var(--dp-accent-soft); }
.crisis-table tbody tr.is-cared td:last-child { box-shadow: inset -3px 0 0 var(--dp-accent); }
.crisis-table tbody tr.is-done td { opacity: .5; }
/* Prochain blessé à prendre en charge : surligné et encadré en orange, qui pulse doucement. */
.crisis-table tbody tr.is-next td { background: var(--dp-warn-soft); box-shadow: inset 0 1px 0 var(--dp-warn), inset 0 -1px 0 var(--dp-warn); animation: crisis-next 1.6s ease-in-out infinite; }
.crisis-table tbody tr.is-next td:first-child { box-shadow: inset 3px 0 0 var(--dp-warn), inset 0 1px 0 var(--dp-warn), inset 0 -1px 0 var(--dp-warn); }
.crisis-table tbody tr.is-next.is-severe td:first-child { box-shadow: inset 3px 0 0 var(--dp-danger), inset 0 1px 0 var(--dp-warn), inset 0 -1px 0 var(--dp-warn); }
@keyframes crisis-next { 50% { background: transparent; } }
@media (prefers-reduced-motion: reduce) { .crisis-table tbody tr.is-next td { animation: none; } }
.crisis-table input[type='checkbox']:disabled { opacity: .35; cursor: not-allowed; }
.crisis-table .is-check, .crisis-table .is-time, .crisis-table .is-action { width: 1%; text-align: center; white-space: nowrap; }
/* Coma, Grave et Inconscient : titres de même largeur, pour un espacement régulier. */
.crisis-check-head { display: inline-block; min-width: 58px; }
.crisis-table .is-bed { width: 1%; white-space: nowrap; }
.crisis-table .is-bed select { width: auto; min-width: 150px; }
.crisis-table .is-name { width: 170px; }
.crisis-table .is-choice { width: 150px; }
.crisis-table .is-time { min-width: 52px; color: var(--dp-text-2); font-variant-numeric: tabular-nums; }
.crisis-table input[type='text'], .crisis-table select { width: 100%; min-width: 0; min-height: 32px; padding: 0 8px; border: 1px solid var(--dp-line); border-radius: 7px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; }
.crisis-table input[type='text']:focus-visible, .crisis-table select:focus-visible { border-color: var(--dp-accent-line); outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }
.crisis-table input[type='checkbox'] { width: 16px; height: 16px; accent-color: var(--dp-accent); cursor: pointer; }
.crisis-table__empty td { padding: 26px; color: var(--dp-text-dim); text-align: center; }

.crisis-delete { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid transparent; border-radius: 7px; color: var(--dp-text-dim); background: transparent; cursor: pointer; }
.crisis-delete:hover { border-color: var(--dp-danger-line); color: var(--dp-danger); background: var(--dp-danger-soft); }
.crisis-add { display: inline-flex; min-height: 36px; align-items: center; justify-self: start; gap: 7px; padding: 0 14px; border: 1px solid var(--dp-accent-line); border-radius: 9px; color: var(--dp-accent); background: var(--dp-accent-soft); font-size: 11px; font-weight: 700; cursor: pointer; }
.crisis-add:disabled { opacity: .5; cursor: not-allowed; }

.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.crisis-error { display: flex; align-items: center; gap: 8px; margin: 0; padding: 12px; border: 1px solid var(--dp-danger-line); border-radius: 10px; color: var(--dp-danger); background: var(--dp-danger-soft); font-size: 12px; }
.crisis-empty { display: grid; min-height: 140px; place-items: center; color: var(--dp-text-dim); }
.crisis-spin { animation: crisis-spin 1s linear infinite; }
@keyframes crisis-spin { to { transform: rotate(360deg); } }

@media (max-width: 720px) {
  .crisis-page { padding: 10px; }
  .crisis-reset { margin-left: 0; }
  .crisis-team__primo select { min-width: 0; width: 100%; }
}
</style>
