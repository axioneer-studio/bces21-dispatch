<script setup lang="ts">
definePageMeta({ layout: false })
useHead({ title: 'Dispatch BCES21' })

type Agent = {
  id: number
  discord_id: string
  discord_username: string
  discord_avatar: string | null
  prenom_rp: string | null
  nom_rp: string | null
}

type SlotKind = 'centrale' | 'hopital' | 'intervention' | 'consultation'

interface DispatchSlot {
  id: string
  kind: SlotKind
  title: string
  agents: Agent[]
}

interface DragPayload {
  agent: Agent
  fromSlotId: string | null
}

function displayName(a: Agent): string {
  if (a.prenom_rp && a.nom_rp) return `${a.prenom_rp} ${a.nom_rp}`
  return a.discord_username
}

function seriesOf(a: Agent): string {
  return `SSS-${String(a.id).padStart(4, '0')}`
}

function avatarUrl(a: Agent): string | null {
  if (!a.discord_avatar) return null
  return `https://cdn.discordapp.com/avatars/${a.discord_id}/${a.discord_avatar}.png?size=80`
}

async function loadAgents(): Promise<Agent[]> {
  try {
    const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
    const data = await $fetch<{ agents: Agent[] }>('/api/users', {
      credentials: 'include',
      headers
    })
    return data.agents
  } catch {
    return []
  }
}

const { data: meData } = await useAsyncData('me-dispatch', async () => {
  try {
    const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
    return await $fetch('/api/me', {
      credentials: 'include',
      headers
    })
  } catch {
    return null
  }
})

if (!meData.value) {
  await navigateTo('/')
}

const { data: agentsData } = await useAsyncData<Agent[]>('dispatch-agents', loadAgents)
const agents = computed<Agent[]>(() => agentsData.value ?? [])

const slots = ref<DispatchSlot[]>([
  { id: 's-centrale', kind: 'centrale', title: 'Centrale', agents: [] },
  { id: 's-hopital', kind: 'hopital', title: 'Hôpital', agents: [] }
])

function unassignedAgents(): Agent[] {
  const assigned = new Set<number>()
  for (const s of slots.value) for (const a of s.agents) assigned.add(a.id)
  return agents.value.filter((a) => !assigned.has(a.id))
}

function makeIntervention(): DispatchSlot {
  const n = slots.value.filter((s) => s.kind === 'intervention').length + 1
  return {
    id: `s-int-${Date.now()}`,
    kind: 'intervention',
    title: `Intervention ${n}`,
    agents: []
  }
}

function makeConsultation(): DispatchSlot {
  const n = slots.value.filter((s) => s.kind === 'consultation').length + 1
  return {
    id: `s-cons-${Date.now()}`,
    kind: 'consultation',
    title: `Consultation ${n}`,
    agents: []
  }
}

function removeSlot(id: string) {
  const slot = slots.value.find((s) => s.id === id)
  if (!slot || slot.kind === 'centrale' || slot.kind === 'hopital') return
  slots.value = slots.value.filter((s) => s.id !== id)
}

function renameSlot(slot: DispatchSlot, value: string) {
  slot.title = value.trim() || slot.title
}

const dragOverSlot = ref<string | null>(null)

function onDragStart(event: DragEvent, payload: DragPayload) {
  if (!event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/json', JSON.stringify(payload))
}

function onDragOver(event: DragEvent, slotId: string) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dragOverSlot.value = slotId
}

function onDragLeave(slotId: string) {
  if (dragOverSlot.value === slotId) dragOverSlot.value = null
}

function onDrop(event: DragEvent, slot: DispatchSlot) {
  event.preventDefault()
  dragOverSlot.value = null
  const raw = event.dataTransfer?.getData('application/json')
  if (!raw) return
  let payload: DragPayload
  try {
    payload = JSON.parse(raw)
  } catch {
    return
  }
  const sourceSlot = payload.fromSlotId
    ? slots.value.find((s) => s.id === payload.fromSlotId)
    : null
  if (sourceSlot && sourceSlot.id === slot.id) return
  if (sourceSlot) {
    sourceSlot.agents = sourceSlot.agents.filter((a) => a.id !== payload.agent.id)
  }
  if (!slot.agents.some((a) => a.id === payload.agent.id)) {
    slot.agents = [...slot.agents, payload.agent]
  }
}

function unassignAgent(slot: DispatchSlot, agentId: number) {
  slot.agents = slot.agents.filter((a) => a.id !== agentId)
}

const showCreateMenu = ref<boolean>(false)
function toggleCreateMenu() {
  showCreateMenu.value = !showCreateMenu.value
}
function createIntervention() {
  slots.value = [...slots.value, makeIntervention()]
  showCreateMenu.value = false
}
function createConsultation() {
  slots.value = [...slots.value, makeConsultation()]
  showCreateMenu.value = false
}
function closeCreateMenu() {
  showCreateMenu.value = false
}

const radioDirection = ref<Array<{ id: string; name: string; series: string; on: boolean }>>([
  { id: 'rd1', series: 'V6GXXXX', name: 'Mike', on: false },
  { id: 'rd2', series: '3FXXXXX', name: 'Lucy', on: false },
  { id: 'rd3', series: 'yeXXXXX', name: 'Noah D', on: false }
])

const radioNormal = ref<Array<{ id: string; name: string; series: string; on: boolean }>>([
  { id: 'r1', series: '0VXXXXX', name: 'Warren', on: true },
  { id: 'r2', series: '2XXXXXX', name: 'Lilyane', on: false },
  { id: 'r3', series: '3XXXXXX', name: 'Alicia', on: false },
  { id: 'r4', series: '4bXXXXX', name: 'Bill', on: false },
  { id: 'r5', series: '4XXXXXX', name: 'William', on: false },
  { id: 'r6', series: 'L8XXXXX', name: 'Léo', on: false },
  { id: 'r7', series: 'NTXXXXX', name: 'Matthew', on: false },
  { id: 'r8', series: '0PXXXXX', name: 'Noah R', on: false },
  { id: 'r9', series: 'q2XXXXX', name: 'Riley', on: false },
  { id: 'r10', series: 'YJXXXXX', name: 'Lewis', on: false },
  { id: 'r11', series: 'ZXXXXXX', name: 'François', on: false },
  { id: 'r12', series: '5VXXXXX', name: '—', on: false },
  { id: 'r13', series: '5UXXXXX', name: '—', on: false },
  { id: 'r14', series: '5NXXXXX', name: '—', on: false },
  { id: 'r15', series: '7zXXXXX', name: '—', on: false },
  { id: 'r16', series: '9XXXXXX', name: '—', on: false },
  { id: 'r17', series: 'c0XXXXX', name: '—', on: false },
  { id: 'r18', series: 'GSXXXXX', name: '—', on: false },
  { id: 'r19', series: 'Q1XXXXX', name: '—', on: false },
  { id: 'r20', series: 'V6XXXXX', name: '—', on: false },
  { id: 'r21', series: '3FXXXXX', name: '—', on: false },
  { id: 'r22', series: 'yeXXXXX', name: '—', on: false }
])

async function logout() {
  await $fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
  await navigateTo('/')
}
</script>

<template>
  <div class="dispatch" @click="closeCreateMenu">
    <header class="dispatch__topbar">
      <div class="dispatch__brand">
        <img src="/images/logo.png" alt="BCES" />
        <span class="dispatch__brand-name">Dispatch BCES21</span>
      </div>
      <div class="dispatch__topbar-actions">
        <span class="dispatch__pill">
          <Icon name="lucide:users-round" size="14" />
          {{ agents.length }} agents
        </span>
        <button type="button" class="dispatch__icon-btn" aria-label="Déconnexion" @click.stop="logout">
          <Icon name="lucide:log-out" size="16" />
        </button>
      </div>
    </header>

    <div class="dispatch__grid">
      <section class="slot" data-kind="centrale">
        <header class="slot__head">
          <Icon name="lucide:phone" size="14" />
          <input
            class="slot__title-input"
            :value="slots[0].title"
            @input="(e) => slots[0] && renameSlot(slots[0], (e.target as HTMLInputElement).value)"
            @dragover.prevent
          />
        </header>
        <div
          class="slot__body"
          :data-drop-over="dragOverSlot === 's-centrale'"
          @dragover="(e) => onDragOver(e, 's-centrale')"
          @dragleave="onDragLeave('s-centrale')"
          @drop="(e) => slots[0] && onDrop(e, slots[0])"
        >
          <AgentTile
            v-for="a in slots[0].agents"
            :key="`c-${a.id}`"
            :agent="a"
            :display-name="displayName(a)"
            :series="seriesOf(a)"
            :avatar-url="avatarUrl(a)"
            :from-slot-id="slots[0].id"
            @drag-start="onDragStart"
            @unassign="unassignAgent(slots[0]!, a.id)"
          />
          <div v-if="slots[0].agents.length === 0" class="slot__empty">
            <Icon name="lucide:mouse-pointer-click" size="14" />
            Glisse un agent ici
          </div>
        </div>
      </section>

      <div class="slot__intervention-wrap">
        <div class="slot__intervention-head">
          <h2 class="slot__intervention-title">
            <Icon name="lucide:list-plus" size="14" />
            Interventions
          </h2>
          <div class="dispatch__create" @click.stop>
            <button
              type="button"
              class="dispatch__create-btn"
              :class="{ 'is-open': showCreateMenu }"
              @click="toggleCreateMenu"
            >
              <Icon name="lucide:plus" size="14" />
              Créer
              <Icon name="lucide:chevron-down" size="14" />
            </button>
            <div v-if="showCreateMenu" class="dispatch__create-menu">
              <button type="button" class="dispatch__create-item" @click="createIntervention">
                <Icon name="lucide:siren" size="14" />
                Nouvelle intervention
              </button>
              <button type="button" class="dispatch__create-item" @click="createConsultation">
                <Icon name="lucide:stethoscope" size="14" />
                Nouvelle consultation
              </button>
            </div>
          </div>
        </div>
        <div class="slot__intervention-grid">
          <article
            v-for="slot in slots.filter((s) => s.kind === 'intervention' || s.kind === 'consultation')"
            :key="slot.id"
            class="slot slot--small"
            :data-kind="slot.kind"
          >
            <header class="slot__head">
              <Icon
                :name="slot.kind === 'intervention' ? 'lucide:siren' : 'lucide:stethoscope'"
                size="14"
              />
              <input
                class="slot__title-input"
                :value="slot.title"
                @input="(e) => renameSlot(slot, (e.target as HTMLInputElement).value)"
                @dragover.prevent
              />
              <button
                type="button"
                class="slot__remove"
                aria-label="Supprimer"
                @click="removeSlot(slot.id)"
              >
                <Icon name="lucide:x" size="12" />
              </button>
            </header>
            <div
              class="slot__body slot__body--mini"
              :data-drop-over="dragOverSlot === slot.id"
              @dragover="(e) => onDragOver(e, slot.id)"
              @dragleave="onDragLeave(slot.id)"
              @drop="(e) => onDrop(e, slot)"
            >
              <AgentTile
                v-for="a in slot.agents"
                :key="`${slot.id}-${a.id}`"
                :agent="a"
                :display-name="displayName(a)"
                :series="seriesOf(a)"
                :avatar-url="avatarUrl(a)"
                :from-slot-id="slot.id"
                @drag-start="onDragStart"
                @unassign="unassignAgent(slot, a.id)"
              />
              <div v-if="slot.agents.length === 0" class="slot__empty slot__empty--small">
                <Icon name="lucide:mouse-pointer-click" size="12" />
                Vide
              </div>
            </div>
          </article>
        </div>
      </div>

      <section class="slot slot--hors" data-kind="hors">
        <header class="slot__head slot__head--hors">
          <Icon name="lucide:user-x" size="14" />
          <span>Hors service BCES</span>
          <span class="slot__count">{{ unassignedAgents().length }}</span>
        </header>
        <div class="slot__body slot__body--hors">
          <AgentTile
            v-for="a in unassignedAgents()"
            :key="`ghost-${a.id}`"
            :agent="a"
            :display-name="displayName(a)"
            :series="seriesOf(a)"
            :avatar-url="avatarUrl(a)"
            :from-slot-id="null"
            @drag-start="onDragStart"
          />
          <div v-if="unassignedAgents().length === 0" class="slot__empty">
            <Icon name="lucide:check-circle-2" size="14" />
            Tous les agents sont assignés
          </div>
        </div>
      </section>

      <section class="slot slot--hopital" data-kind="hopital">
        <header class="slot__head">
          <Icon name="lucide:heart-pulse" size="14" />
          <input
            class="slot__title-input"
            :value="slots[1].title"
            @input="(e) => slots[1] && renameSlot(slots[1], (e.target as HTMLInputElement).value)"
            @dragover.prevent
          />
        </header>
        <div
          class="slot__body slot__body--mini"
          :data-drop-over="dragOverSlot === 's-hopital'"
          @dragover="(e) => onDragOver(e, 's-hopital')"
          @dragleave="onDragLeave('s-hopital')"
          @drop="(e) => slots[1] && onDrop(e, slots[1])"
        >
          <AgentTile
            v-for="a in slots[1].agents"
            :key="`h-${a.id}`"
            :agent="a"
            :display-name="displayName(a)"
            :series="seriesOf(a)"
            :avatar-url="avatarUrl(a)"
            :from-slot-id="slots[1].id"
            @drag-start="onDragStart"
            @unassign="unassignAgent(slots[1]!, a.id)"
          />
          <div v-if="slots[1].agents.length === 0" class="slot__empty slot__empty--small">
            <Icon name="lucide:bed" size="12" />
            Vide
          </div>
        </div>
      </section>

      <section class="panel panel--simple" data-area="astreinte">
        <header class="panel__head">
          <Icon name="lucide:shield-alert" size="14" />
          <span>Astreinte</span>
        </header>
        <div class="panel__body">
          <div class="panel__placeholder">Aucun agent d'astreinte</div>
        </div>
      </section>

      <section class="panel panel--simple" data-area="conges">
        <header class="panel__head">
          <Icon name="lucide:beach" size="14" />
          <span>Congés</span>
        </header>
        <div class="panel__body">
          <div class="panel__placeholder">Personne en congé</div>
        </div>
      </section>

      <section class="panel panel--simple" data-area="ipt">
        <header class="panel__head">
          <Icon name="lucide:id-card" size="14" />
          <span>IPT</span>
        </header>
        <div class="panel__body">
          <div class="panel__placeholder">—</div>
        </div>
      </section>

      <section class="panel panel--simple" data-area="astreinte-fin">
        <header class="panel__head">
          <Icon name="lucide:moon-star" size="14" />
          <span>Astreinte fin de service</span>
        </header>
        <div class="panel__body">
          <div class="panel__placeholder">—</div>
        </div>
      </section>

      <section class="panel panel--simple" data-area="pause">
        <header class="panel__head">
          <Icon name="lucide:coffee" size="14" />
          <span>Pause</span>
        </header>
        <div class="panel__body">
          <div class="panel__placeholder">Personne en pause</div>
        </div>
      </section>

      <aside class="dispatch__radio">
        <section class="panel panel--radio">
          <header class="panel__head">
            <Icon name="lucide:radio-tower" size="14" />
            <span>Radio Direction</span>
            <span class="panel__head-count">{{ radioDirection.length }}</span>
          </header>
          <div class="panel__body panel__body--radio">
            <div class="radio-grid">
              <div class="radio-cell radio-cell--head">N° Série</div>
              <div class="radio-cell radio-cell--head">Nom</div>
              <div class="radio-cell radio-cell--head">On/Off</div>
              <template v-for="r in radioDirection" :key="r.id">
                <div class="radio-cell radio-cell--series">{{ r.series }}</div>
                <div class="radio-cell radio-cell--name">{{ r.name }}</div>
                <div class="radio-cell radio-cell--toggle">
                  <button
                    type="button"
                    class="radio-toggle"
                    :data-on="r.on"
                    @click="r.on = !r.on"
                  >
                    {{ r.on ? 'On' : 'Off' }}
                    <Icon :name="r.on ? 'lucide:check' : 'lucide:x'" size="12" />
                  </button>
                </div>
              </template>
            </div>
          </div>
        </section>

        <section class="panel panel--radio">
          <header class="panel__head">
            <Icon name="lucide:radio" size="14" />
            <span>Radio</span>
            <span class="panel__head-count">{{ radioNormal.length }}</span>
          </header>
          <div class="panel__body panel__body--radio">
            <div class="radio-grid">
              <div class="radio-cell radio-cell--head">N° Série</div>
              <div class="radio-cell radio-cell--head">Nom</div>
              <div class="radio-cell radio-cell--head">On/Off</div>
              <template v-for="r in radioNormal" :key="r.id">
                <div class="radio-cell radio-cell--series">{{ r.series }}</div>
                <div class="radio-cell radio-cell--name">{{ r.name }}</div>
                <div class="radio-cell radio-cell--toggle">
                  <button
                    type="button"
                    class="radio-toggle"
                    :data-on="r.on"
                    @click="r.on = !r.on"
                  >
                    {{ r.on ? 'On' : 'Off' }}
                    <Icon :name="r.on ? 'lucide:check' : 'lucide:x'" size="12" />
                  </button>
                </div>
              </template>
            </div>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.dispatch {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #21252b;
  color: var(--bces-text);
}

.dispatch__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  background: #1c2026;
  gap: 12px;
  flex-wrap: wrap;
}

.dispatch__brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dispatch__brand img {
  height: 24px;
  width: auto;
  filter: drop-shadow(0 2px 6px rgba(70, 153, 109, 0.35));
}

.dispatch__brand-name {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--bces-accent);
}

.dispatch__topbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dispatch__pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 0;
  background: var(--bces-accent-soft);
  border: 1px solid var(--bces-border-strong);
  color: var(--bces-accent);
  font-size: 10px;
  font-weight: 600;
}

.dispatch__icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 0;
  color: var(--bces-text-muted);
  transition: color 0.15s ease, background 0.15s ease;
}

.dispatch__icon-btn:hover {
  color: #ec8a86;
  background: rgba(210, 85, 79, 0.10);
}

.dispatch__grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 240px;
  grid-template-rows: minmax(100px, auto) minmax(180px, auto) 140px 140px;
  grid-template-areas:
    'centrale intervention hors radio'
    'hopital   hopital      hors radio'
    'astreinte astreinte    conges radio'
    'ipt       astreinte-fin pause radio';
  gap: 0;
  padding: 0;
  min-height: 0;
  width: 100%;
}

.dispatch__grid > .panel {
  height: 100%;
  min-height: 0;
}

.dispatch__radio {
  grid-row: 1 / 5;
}

.slot,
.panel {
  background: #2a2f37;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.slot[data-kind='centrale'] { grid-area: centrale; }
.slot--hors { grid-area: hors; }
.slot--hopital { grid-area: hopital; }
.slot__intervention-wrap { grid-area: intervention; display: flex; flex-direction: column; gap: 4px; min-height: 0; }

.panel--simple[data-area='astreinte'] { grid-area: astreinte; }
.panel--simple[data-area='conges'] { grid-area: conges; }
.panel--simple[data-area='ipt'] { grid-area: ipt; }
.panel--simple[data-area='astreinte-fin'] { grid-area: astreinte-fin; }
.panel--simple[data-area='pause'] { grid-area: pause; }

.dispatch__grid > .panel--simple {
  min-height: 0;
  max-height: 140px;
  overflow: hidden;
}

.dispatch__radio {
  grid-area: radio;
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}

.dispatch__radio > .panel {
  flex: 1;
}

.slot__head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(70, 153, 109, 0.10);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: var(--bces-accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.slot__head--hors {
  background: rgba(210, 85, 79, 0.14);
  border-bottom-color: rgba(255, 255, 255, 0.04);
  color: #ec8a86;
}

.slot__head[data-drop-over='true'] {
  background: var(--bces-accent);
  color: #04140c;
}

.slot__title-input {
  flex: 1;
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  text-transform: inherit;
  letter-spacing: inherit;
  font-weight: inherit;
  outline: none;
  min-width: 0;
}

.slot__title-input:focus {
  background: rgba(0, 0, 0, 0.30);
  padding: 2px 10px;
  color: var(--bces-text);
}

.slot__count {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  color: var(--bces-text-muted);
}

.slot__remove {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0;
  color: inherit;
  background: rgba(0, 0, 0, 0.20);
  opacity: 0.6;
  transition: opacity 0.15s ease, background 0.15s ease;
}

.slot__remove:hover {
  opacity: 1;
  background: rgba(210, 85, 79, 0.30);
}

.slot__intervention-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 4px;
}

.slot__intervention-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 10px;
  font-weight: 700;
  color: var(--bces-accent);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding-left: 4px;
}

.dispatch__create {
  position: relative;
}

.dispatch__create-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 0;
  background: var(--bces-accent);
  color: #04140c;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  transition: background 0.15s ease;
}

.dispatch__create-btn:hover {
  background: var(--bces-accent-hover);
}

.dispatch__create-btn.is-open {
  background: var(--bces-accent-active);
}

.dispatch__create-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px;
  background: var(--bces-bg-elevated);
  border: 1px solid var(--bces-border-strong);
  box-shadow: var(--bces-shadow);
}

.dispatch__create-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: transparent;
  color: var(--bces-text);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  transition: background 0.15s ease;
}

.dispatch__create-item:hover {
  background: var(--bces-accent-soft);
  color: var(--bces-accent);
}

.slot__intervention-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 4px;
  align-content: start;
  overflow-y: auto;
  min-height: 0;
}

.slot--small {
  min-height: 80px;
}

.slot__body {
  flex: 1;
  padding: 3px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow-y: auto;
  min-height: 30px;
  transition: background 0.15s ease;
}

.slot__body--mini {
  padding: 2px;
}

.slot__body--hors {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 3px;
  align-content: start;
  padding: 3px;
}

.slot__body[data-drop-over='true'] {
  background: rgba(70, 153, 109, 0.18);
  outline: 2px dashed var(--bces-accent);
  outline-offset: -4px;
}

.slot__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  border: 1px dashed var(--bces-border);
  color: var(--bces-text-dim);
  font-size: 11px;
  font-style: italic;
}

.slot__empty--small {
  padding: 4px;
  font-size: 10px;
}

.panel__head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(70, 153, 109, 0.10);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: var(--bces-accent);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.panel__head-count {
  margin-left: auto;
  font-size: 10px;
  font-weight: 700;
  color: var(--bces-text-muted);
}

.panel__body {
  flex: 1;
  padding: 4px 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--bces-text-dim);
  font-size: 10px;
  font-style: italic;
}

.panel__body--radio {
  padding: 3px;
  align-items: stretch;
  justify-content: flex-start;
}

.panel__placeholder {
  text-align: center;
}

.radio-grid {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 1px;
  font-size: 9px;
}

.radio-cell {
  padding: 2px 3px;
}

.radio-cell--head {
  font-weight: 700;
  text-transform: uppercase;
  color: var(--bces-accent);
  border-bottom: 1px solid var(--bces-border);
  padding-bottom: 3px;
  font-size: 8px;
  text-align: center;
}

.radio-cell--series {
  color: var(--bces-text-muted);
  font-family: ui-monospace, monospace;
  font-size: 9px;
}

.radio-cell--name {
  font-size: 10px;
  color: var(--bces-text);
}

.radio-toggle {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 5px;
  border-radius: 0;
  background: rgba(210, 85, 79, 0.18);
  border: 1px solid rgba(210, 85, 79, 0.45);
  color: #ec8a86;
  font-size: 9px;
  font-weight: 600;
  cursor: pointer;
}

.radio-toggle[data-on='true'] {
  background: rgba(70, 153, 109, 0.22);
  border-color: rgba(70, 153, 109, 0.55);
  color: var(--bces-accent);
}

@media (max-width: 1100px) {
  .dispatch__grid {
    grid-template-columns: 1fr 1fr 240px;
    grid-template-areas:
      'centrale intervention hors'
      'hopital hopital hors'
      'astreinte astreinte radio'
      'conges ipt radio'
      'astreinte-fin pause radio';
  }
}

@media (max-width: 720px) {
  .dispatch__grid {
    grid-template-columns: 1fr;
    grid-template-areas:
      'centrale'
      'intervention'
      'hopital'
      'hors'
      'astreinte'
      'conges'
      'ipt'
      'astreinte-fin'
      'pause'
      'radio';
  }
}
</style>