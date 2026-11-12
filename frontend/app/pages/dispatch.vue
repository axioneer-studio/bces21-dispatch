<script setup lang="ts">
import { assignUser, createFleetEntry, createSlot, fetchSnapshot, saveDispatchNote, unassignUser } from '~/composables/useDispatchApi'
import type { Agent } from '~/utils/agent'
import { sortAgentsByGradeAndArrival } from '~/utils/agent'

definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Dispatch • BCES' })

interface DispatchUser {
  is_super_admin: boolean
  grade_permissions: string[]
}

const { data: meData } = await useAsyncData<DispatchUser | null>('me-dispatch', async () => {
  try {
    const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
    return await $fetch<DispatchUser>('/api/me', { credentials: 'include', headers })
  } catch {
    return null
  }
})

if (!meData.value) {
  await navigateTo('/')
}

const { data: agentsData } = await useAsyncData<Agent[]>('dispatch-employees', async () => {
  try {
    const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
    return await $fetch<Agent[]>('/api/employees', {
      credentials: 'include',
      headers
    })
  } catch {
    return []
  }
})

const agents = computed<Agent[]>(() => agentsData.value ?? [])
const toast = useAppToast()

async function refreshAgents() {
  try {
    agentsData.value = await $fetch<Agent[]>('/api/employees', {
      credentials: 'include'
    })
  } catch {
    toast.error('Mise à jour des employés impossible.')
  }
}

const {
  slots,
  interventions,
  centrale,
  hopital,
  snapshot,
  connected,
  applySnapshot,
  beginEmployeeMove,
  completeEmployeeMove,
  cancelEmployeeMove
} = useDispatchStore()
const { connect, disconnect } = useDispatchSocket(refreshAgents)
const movingEmployees = new Set<number>()
const noteDraft = ref('')
const noteDirty = ref(false)
const savingNote = ref(false)
const editingNote = ref(false)
const noteEditor = ref<HTMLTextAreaElement | null>(null)

const { data: initialSnapshot } = await useAsyncData('dispatch-snapshot-initial', async () => {
  try {
    return await fetchSnapshot()
  } catch {
    return null
  }
})

if (initialSnapshot.value) {
  applySnapshot(initialSnapshot.value)
  noteDraft.value = initialSnapshot.value.note ?? ''
}

onMounted(() => connect())
onBeforeUnmount(() => disconnect())

watch(
  () => snapshot.value.note,
  (note) => {
    if (!editingNote.value && !noteDirty.value) noteDraft.value = note ?? ''
  }
)

watch(connected, (v) => {
  if (v) toast.success('Synchronisation en direct.')
})

const byKind = (kind: string) => slots.value.find((s) => s.kind === kind) ?? null
const astreinte = computed(() => byKind('astreinte'))
const conges = computed(() => byKind('conges'))
const ipt = computed(() => byKind('ipt'))
const astreinteFin = computed(() => byKind('astreinte-fin'))
const pause = computed(() => byKind('pause'))

// Agents pas encore assignés → pool "Hors service BCES"
const pool = computed(() => {
  const taken = new Set<number>()
  for (const s of slots.value) for (const a of s.assignments) taken.add(a.employee_id)
  return sortAgentsByGradeAndArrival(
    agents.value.filter((agent) => agent.is_active && !taken.has(agent.id))
  )
})

async function onEmployeeDrop(employeeId: number, targetSlotId: number | null) {
  if (movingEmployees.has(employeeId)) return
  const sourceSlot = slots.value.find((slot) =>
    slot.assignments.some((assignment) => assignment.employee_id === employeeId)
  )
  if (sourceSlot?.id === targetSlotId || (targetSlotId === null && !sourceSlot)) return

  movingEmployees.add(employeeId)
  beginEmployeeMove(employeeId, targetSlotId)
  try {
    const updatedSlot =
      targetSlotId === null
        ? await unassignUser(sourceSlot!.id, employeeId)
        : await assignUser(targetSlotId, employeeId)
    completeEmployeeMove(employeeId, updatedSlot)
  } catch {
    toast.error(targetSlotId === null ? 'Désassignation impossible.' : 'Assignation impossible.')
    cancelEmployeeMove(employeeId)
    try {
      applySnapshot(await fetchSnapshot())
    } catch {
      toast.error('Synchronisation du Dispatch impossible.')
    }
  } finally {
    movingEmployees.delete(employeeId)
  }
}

const adding = ref<boolean>(false)
async function addIntervention() {
  if (adding.value) return
  adding.value = true
  try {
    await createSlot('intervention')
  } catch {
    toast.error('Création impossible.')
  } finally {
    adding.value = false
  }
}

const addingFleetEntry = ref(false)
async function addFleetEntry() {
  if (addingFleetEntry.value) return
  addingFleetEntry.value = true
  try {
    await createFleetEntry()
  } catch {
    toast.error('Ajout de la ligne impossible.')
  } finally {
    addingFleetEntry.value = false
  }
}

async function saveNote() {
  if (savingNote.value || !noteDirty.value) return
  savingNote.value = true
  try {
    const updatedSnapshot = await saveDispatchNote(noteDraft.value)
    applySnapshot(updatedSnapshot)
    noteDirty.value = false
  } catch {
    toast.error('Mise à jour du bloc-notes impossible.')
  } finally {
    savingNote.value = false
  }
}

async function editNote() {
  if (editingNote.value || savingNote.value) return
  if (!noteDirty.value) noteDraft.value = snapshot.value.note ?? ''
  editingNote.value = true
  await nextTick()
  noteEditor.value?.focus()
  const end = noteEditor.value?.value.length ?? 0
  noteEditor.value?.setSelectionRange(end, end)
}

async function finishNoteEdit() {
  editingNote.value = false
  await saveNote()
}
</script>

<template>
  <DispatchHeader
    :can-reset-assignments="Boolean(meData?.is_super_admin || meData?.grade_permissions.includes('dispatch.manage_assignments'))"
    :can-delete-interventions="Boolean(meData?.is_super_admin || meData?.grade_permissions.includes('dispatch.manage_slots'))"
  />

  <main class="dp">
    <div class="dp__board">
      <section v-if="centrale" class="z z--centrale">
        <header class="z__head">
          <Icon name="lucide:phone" size="12" />
          <span>Centrale</span>
        </header>
        <div class="z__rail z__rail--one">
          <InterventionCard
            :slot="centrale"
            :agents="agents"
            :fixed="true"
            compact
            label="Centrale"
            @employee-drop="onEmployeeDrop"
            @employee-remove="onEmployeeDrop"
          />
        </div>
      </section>

      <section class="z z--inter">
        <header class="z__head">
          <Icon name="lucide:siren" size="12" />
          <span>Intervention</span>
          <button
            type="button"
            class="z__plus"
            :disabled="adding"
            title="Créer une intervention"
            aria-label="Créer une intervention"
            @click="addIntervention"
          >
            <Icon name="lucide:plus" size="13" />
          </button>
        </header>
        <div class="z__rail">
          <InterventionCard
            v-for="(slot, i) in interventions"
            :key="slot.id"
            :slot="slot"
            :agents="agents"
            :hospital-slot-id="hopital?.id"
            :label="slot.kind === 'consultation' ? 'Consultation' : `Int. ${i + 1}`"
            @employee-drop="onEmployeeDrop"
            @employee-remove="onEmployeeDrop"
          />
          <button
            type="button"
            class="z__addcard"
            :disabled="adding"
            title="Créer une intervention"
            @click="addIntervention"
          >
            <Icon name="lucide:plus" size="16" />
            <span>Créer</span>
          </button>
        </div>
      </section>

      <section class="z z--hors">
        <header class="z__head z__head--hors">
          <Icon name="lucide:user-x" size="12" />
          <span>Hors service BCES</span>
          <span class="z__count">{{ pool.length }}</span>
        </header>
        <SlotPanel
          :pool="pool"
          :agents="agents"
          @employee-drop="onEmployeeDrop"
          @employee-remove="onEmployeeDrop"
        />
      </section>

      <aside class="z z--radio">
        <RadioPanel
          :radios="snapshot.radios"
          :agents="agents"
          :pool="pool"
        />
      </aside>

      <section v-if="hopital" class="z z--hopital">
        <header class="z__head z__head--alt">
          <Icon name="lucide:heart-pulse" size="12" />
          <span>Hôpital</span>
          <span class="z__hint">en service, hors intervention</span>
        </header>
        <SlotPanel
          :slot="hopital"
          :agents="agents"
          accent="#ec8a86"
          @employee-drop="onEmployeeDrop"
          @employee-remove="onEmployeeDrop"
        />
      </section>

      <div class="dp__lower">
        <section v-if="astreinte" class="z z--astreinte">
          <header class="z__head"><Icon name="lucide:shield-alert" size="12" /><span>Astreinte</span></header>
          <SlotPanel
            :slot="astreinte"
            :agents="agents"
            @employee-drop="onEmployeeDrop"
            @employee-remove="onEmployeeDrop"
          />
        </section>

        <section v-if="conges" class="z z--conges">
          <header class="z__head"><Icon name="lucide:umbrella" size="12" /><span>Congés</span></header>
          <SlotPanel
            :slot="conges"
            :agents="agents"
            @employee-drop="onEmployeeDrop"
            @employee-remove="onEmployeeDrop"
          />
        </section>

        <div class="dp__lower-bottom">
          <section v-if="ipt" class="z z--ipt">
            <header class="z__head"><Icon name="lucide:id-card" size="12" /><span>IPT</span></header>
            <SlotPanel
              :slot="ipt"
              :agents="agents"
              @employee-drop="onEmployeeDrop"
              @employee-remove="onEmployeeDrop"
            />
          </section>

          <section v-if="astreinteFin" class="z z--fin">
            <header class="z__head"><Icon name="lucide:moon-star" size="12" /><span>Astreinte fin de service</span></header>
            <SlotPanel
              :slot="astreinteFin"
              :agents="agents"
              @employee-drop="onEmployeeDrop"
              @employee-remove="onEmployeeDrop"
            />
          </section>

          <section v-if="pause" class="z z--pause">
            <header class="z__head"><Icon name="lucide:coffee" size="12" /><span>Pause</span></header>
            <SlotPanel
              :slot="pause"
              :agents="agents"
              @employee-drop="onEmployeeDrop"
              @employee-remove="onEmployeeDrop"
            />
          </section>
        </div>
      </div>

      <div class="dp__tools">
        <section class="z z--fleet">
          <header class="z__head">
            <Icon name="lucide:car-front" size="12" />
            <span>Flotte de véhicules</span>
            <button
              type="button"
              class="z__plus"
              :disabled="addingFleetEntry"
              title="Ajouter une ligne"
              aria-label="Ajouter une ligne à la flotte"
              @click="addFleetEntry"
            >
              <Icon name="lucide:plus" size="13" />
            </button>
          </header>
          <FleetPanel
            :entries="snapshot.fleet"
            :vehicles="snapshot.vehicles"
            :parking-spots="snapshot.parking_spots"
          />
        </section>

        <section class="z z--notes">
          <header class="z__head">
            <Icon name="lucide:notebook-pen" size="12" />
            <span>Prise de note centrale</span>
            <span v-if="savingNote" class="dp__note-status">Mise à jour…</span>
          </header>
          <textarea
            v-if="editingNote"
            ref="noteEditor"
            v-model="noteDraft"
            class="dp__note-input"
            maxlength="10000"
            placeholder="Notes partagées du Dispatch…"
            aria-label="Bloc-notes partagé du Dispatch"
            @input="noteDirty = true"
            @blur="finishNoteEdit"
          />
          <button
            v-else
            type="button"
            class="dp__note-display"
            :class="{ 'is-empty': !snapshot.note }"
            aria-label="Double-cliquer pour modifier la prise de note centrale"
            title="Double-cliquer pour modifier"
            @dblclick="editNote"
          >{{ snapshot.note || 'Double-cliquez pour ajouter une note…' }}</button>
        </section>
      </div>
    </div>
  </main>
</template>

<style scoped>
.dp {
  flex: 1;
  min-height: 0;
  padding: 5px;
  overflow: hidden;
}

.dp__board {
  display: grid;
  grid-template-columns:
    minmax(190px, 220px)
    minmax(0, 1.15fr)
    minmax(0, 1fr)
    minmax(220px, 260px);
  grid-template-rows: minmax(160px, max-content) minmax(170px, 1fr) 112px 112px 150px;
  grid-template-areas:
    'centrale hopital hors radio'
    'inter hopital hors radio'
    'inter lower lower radio'
    'inter lower lower radio'
    'inter tools tools radio';
  gap: 4px;
  height: 100%;
  min-height: 0;
}

.dp__lower {
  grid-area: lower;
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  grid-template-areas:
    'astreinte conges'
    'bottom bottom';
  gap: 4px;
  min-width: 0;
  min-height: 0;
}

.dp__lower-bottom {
  grid-area: bottom;
  display: grid;
  grid-template-columns: minmax(0, 0.65fr) minmax(0, 1.35fr) minmax(0, 1fr);
  grid-template-areas: 'ipt fin pause';
  gap: 4px;
  min-width: 0;
  min-height: 0;
}

.dp__tools {
  grid-area: tools;
  display: grid;
  grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
  gap: 4px;
  min-width: 0;
  min-height: 0;
}

.dp__note-status {
  color: var(--dp-text-dim);
  font-size: 9px;
}

.z--notes .z__head {
  justify-content: center;
}

.dp__note-input {
  flex: 1;
  width: 100%;
  min-height: 0;
  resize: none;
  border: 0;
  outline: 0;
  padding: 8px;
  color: var(--dp-text);
  background: var(--dp-panel-2);
  font: inherit;
  font-size: 11px;
  line-height: 1.4;
  text-align: center;
}

.dp__note-display {
  display: flex;
  flex: 1;
  width: 100%;
  align-items: center;
  justify-content: center;
  min-height: 0;
  overflow: auto;
  border: 0;
  padding: 8px;
  color: var(--dp-text);
  background: var(--dp-panel-2);
  font: inherit;
  font-size: 11px;
  line-height: 1.4;
  text-align: center;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  cursor: text;
}

.dp__note-display.is-empty {
  color: var(--dp-text-dim);
  font-style: italic;
}

.dp__note-input:focus,
.dp__note-display:focus-visible {
  box-shadow: inset 0 0 0 1px var(--dp-accent-line);
}

.dp__spin {
  animation: dp-spin 1s linear infinite;
}

@keyframes dp-spin {
  to { transform: rotate(360deg); }
}
.z {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: var(--dp-panel);
  border: 1px solid var(--dp-line);
  overflow: hidden;
}

.z--centrale { grid-area: centrale; }
.z--inter    { grid-area: inter; }
.z--hors     { grid-area: hors; }
.z--radio    { grid-area: radio; }
.z--hopital  { grid-area: hopital; }
.z--astreinte{ grid-area: astreinte; }
.z--conges   { grid-area: conges; }
.z--ipt      { grid-area: ipt; }
.z--fin      { grid-area: fin; }
.z--pause    { grid-area: pause; }
.z--fleet,
.z--notes { min-height: 0; }

.z--centrale .z__rail :deep(.iv) {
  width: 100%;
  min-width: 0;
  flex: 0 0 auto;
  align-self: flex-start;
  min-height: 0;
  height: auto;
}

.z--centrale .z__rail {
  flex: 0 0 auto;
  overflow-y: auto;
}

.z--inter .z__rail {
  flex-direction: column;
  align-items: stretch;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.z--inter .z__rail :deep(.iv) {
  width: 100%;
  min-width: 0;
  flex: 0 0 auto;
  min-height: 126px;
  height: auto;
}

.z--inter .z__rail :deep(.z__addcard) {
  width: 100%;
  flex: 0 0 56px;
}

.z__head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  background: var(--dp-panel-3);
  border-bottom: 1px solid var(--dp-line);
  color: var(--dp-text-2);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.z__head--alt {
  color: var(--dp-danger);
  box-shadow: inset 3px 0 0 var(--dp-danger-line);
}

.z__head--hors {
  color: var(--dp-warn);
  box-shadow: inset 3px 0 0 var(--dp-warn-line);
}

.z__head span:first-of-type {
  color: var(--dp-text);
}

.z__hint {
  margin-left: auto;
  font-size: 9px;
  font-weight: 500;
  font-style: italic;
  text-transform: none;
  letter-spacing: 0;
  color: var(--dp-text-dim);
}

.z__count {
  margin-left: auto;
  color: var(--dp-text-dim);
  font-variant-numeric: tabular-nums;
}

.z__plus {
  margin-left: auto;
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--dp-accent);
  color: #0b1510;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  flex-shrink: 0;
}

.z__plus:hover { background: #55ad7e; }
.z__plus:disabled { opacity: 0.45; cursor: not-allowed; }

.z__body {
  flex: 1;
  min-height: 0;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.z__body--scroll {
  overflow-y: auto;
}

/* Rail horizontal : une carte = une tuile, on défile latéralement. */
.z__rail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 4px;
  padding: 4px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--dp-line-strong) transparent;
}

.z__rail--one {
  overflow-x: hidden;
}

.z__rail::-webkit-scrollbar {
  height: 8px;
}

.z__rail::-webkit-scrollbar-track {
  background: var(--dp-panel-2);
}

.z__rail::-webkit-scrollbar-thumb {
  background: var(--dp-line-strong);
  border-radius: 4px;
}

.z__addcard {
  flex: 0 0 106px;
  width: 106px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: transparent;
  border: 1px dashed var(--dp-line-strong);
  border-radius: 3px;
  color: var(--dp-text-dim);
  font-size: 9.5px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.12s ease, color 0.12s ease, background 0.12s ease;
}

.z__addcard:hover:not(:disabled) {
  border-color: var(--dp-accent-line);
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}

.z__addcard:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.z--hors > :deep(.sp) {
  overflow-y: auto;
}

.z__addline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 6px;
  background: transparent;
  border: 1px dashed var(--dp-line-strong);
  border-radius: 3px;
  color: var(--dp-text-dim);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
}

.pool {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 5px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed rgba(70, 153, 109, 0.40);
  cursor: grab;
  transition: background 0.12s ease;
}

.pool:hover { background: rgba(70, 153, 109, 0.14); }
.pool:active { cursor: grabbing; }

.pool__avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--bces-bg-elevated);
}

.pool__avatar--ph {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
  font-weight: 700;
  font-size: 12px;
}

.pool__meta {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  min-width: 0;
}

.pool__name {
  font-size: 11px;
  font-weight: 600;
  color: var(--bces-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pool__skills {
  font-size: 9px;
  color: var(--bces-text-muted);
}

@media (max-width: 1280px) {
  .dp__board {
    grid-template-columns:
      minmax(170px, 200px)
      minmax(0, 1.15fr)
      minmax(0, 1fr)
      minmax(200px, 230px);
  }
}

@media (max-width: 900px) {
  .dp { overflow: hidden; }
  .dp__board {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-areas:
      'centrale centrale'
      'inter inter'
      'hopital hopital'
      'hors hors'
      'lower lower'
      'tools tools'
      'radio radio';
    grid-template-rows: minmax(120px, max-content) 280px minmax(220px, auto) 220px 230px 180px 400px;
    height: auto;
    min-height: 100%;
    overflow-y: auto;
  }
}
</style>
