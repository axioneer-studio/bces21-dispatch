<script setup lang="ts">
definePageMeta({ layout: 'dispatch' })
useHead({ title: 'Direction · BCES' })

interface GradePermission {
  key: string
  label: string
}

interface Grade {
  id: number
  name: string
  level: number
  color: string
  permissions: string[]
  employees_count: number
}

const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
const [{ data: initialGrades }, { data: permissionOptions }] = await Promise.all([
  useAsyncData('direction-grades', () =>
    $fetch<Grade[]>('/api/direction/grades', { credentials: 'include', headers: requestHeaders })
  ),
  useAsyncData('direction-grade-permissions', () =>
    $fetch<GradePermission[]>('/api/direction/permissions', {
      credentials: 'include',
      headers: requestHeaders
    })
  )
])

const grades = ref<Grade[]>(initialGrades.value ?? [])
const editingId = ref<number | null>(null)
const saving = ref(false)
const error = ref('')
const form = reactive({ name: '', level: 1, color: '#46996d', permissions: [] as string[] })

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === 'object' && cause !== null && 'data' in cause) {
    const data = cause.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
  }
  return fallback
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.level = 1
  form.color = '#46996d'
  form.permissions = []
}

function editGrade(grade: Grade) {
  editingId.value = grade.id
  form.name = grade.name
  form.level = grade.level
  form.color = grade.color
  form.permissions = [...grade.permissions]
  error.value = ''
  document.querySelector('.direction-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

async function saveGrade() {
  if (saving.value || !form.name.trim() || form.level < 1) return
  saving.value = true
  error.value = ''
  try {
    const payload = {
      name: form.name.trim(),
      level: Math.floor(form.level),
      color: form.color,
      permissions: [...new Set(form.permissions)]
    }
    const saved = editingId.value
      ? await $fetch<Grade>(`/api/direction/grades/${editingId.value}`, {
          method: 'PATCH',
          body: payload,
          credentials: 'include'
        })
      : await $fetch<Grade>('/api/direction/grades', {
          method: 'POST',
          body: payload,
          credentials: 'include'
        })
    const existingIndex = grades.value.findIndex((grade) => grade.id === saved.id)
    if (existingIndex < 0) grades.value.push(saved)
    else grades.value.splice(existingIndex, 1, saved)
    grades.value.sort((a, b) => a.level - b.level || a.name.localeCompare(b.name, 'fr'))
    resetForm()
  } catch (cause) {
    error.value = messageFromError(cause, 'Enregistrement du grade impossible.')
  } finally {
    saving.value = false
  }
}

async function deleteGrade(grade: Grade) {
  if (!window.confirm(`Supprimer le grade « ${grade.name} » ?`)) return
  error.value = ''
  try {
    await $fetch(`/api/direction/grades/${grade.id}`, { method: 'DELETE', credentials: 'include' })
    grades.value = grades.value.filter((item) => item.id !== grade.id)
    if (editingId.value === grade.id) resetForm()
  } catch (cause) {
    error.value = messageFromError(cause, 'Suppression du grade impossible.')
  }
}
</script>

<template>
  <main class="direction-page">
    <header class="direction-header">
      <div>
        <p class="direction-eyebrow">BCES · ORGANISATION DU SERVICE</p>
        <h1>Direction</h1>
        <p>Définissez la hiérarchie des grades et les capacités opérationnelles associées.</p>
      </div>
      <div class="direction-count"><Icon name="lucide:shield" size="18" /><strong>{{ grades.length }}</strong><span>grades</span></div>
    </header>

    <div v-if="error" class="direction-error" role="alert">
      <Icon name="lucide:circle-alert" size="17" /><span>{{ error }}</span>
      <button type="button" aria-label="Fermer" @click="error = ''"><Icon name="lucide:x" size="15" /></button>
    </div>

    <section class="direction-section">
      <div class="direction-section__heading">
        <div>
          <h2>{{ editingId ? 'Modifier un grade' : 'Créer un grade' }}</h2>
          <p>Le niveau numérique détermine l’ordre hiérarchique, du niveau 1 vers les niveaux supérieurs.</p>
        </div>
        <button v-if="editingId" type="button" class="direction-button" @click="resetForm">Annuler</button>
      </div>
      <form class="direction-form" @submit.prevent="saveGrade">
        <label>
          <span>Nom du grade</span>
          <input v-model="form.name" required maxlength="64" placeholder="Ex. Médecin-chef">
        </label>
        <label>
          <span>Niveau hiérarchique</span>
          <input v-model.number="form.level" type="number" min="1" step="1" required>
        </label>
        <label class="direction-color-field">
          <span>Couleur du grade</span>
          <span class="direction-color-control">
            <input v-model="form.color" type="color" aria-label="Couleur du grade">
            <code>{{ form.color.toUpperCase() }}</code>
          </span>
        </label>
        <fieldset>
          <legend>Permissions opérationnelles</legend>
          <label v-for="permission in permissionOptions" :key="permission.key">
            <input v-model="form.permissions" type="checkbox" :value="permission.key">
            <span>{{ permission.label }}</span>
          </label>
          <p v-if="!permissionOptions?.length" class="direction-muted">Aucune permission disponible.</p>
        </fieldset>
        <button class="direction-button direction-button--primary" type="submit" :disabled="saving || !form.name.trim() || form.level < 1">
          <Icon :name="saving ? 'lucide:loader-circle' : 'lucide:save'" size="15" :class="{ 'direction-spin': saving }" />
          {{ saving ? 'Enregistrement…' : editingId ? 'Enregistrer le grade' : 'Créer le grade' }}
        </button>
      </form>
    </section>

    <section class="direction-section">
      <div class="direction-section__heading">
        <div><h2>Hiérarchie des grades</h2><p>Les grades attribués à des employés ne peuvent être supprimés qu’après réattribution.</p></div>
      </div>
      <article v-for="grade in grades" :key="grade.id" class="direction-grade">
        <div class="direction-grade__level" :style="{ '--grade-color': grade.color }"><span>Niveau</span><strong>{{ grade.level }}</strong></div>
        <div class="direction-grade__main">
          <div class="direction-grade__title"><span class="direction-grade__swatch" :style="{ backgroundColor: grade.color }"></span><h3>{{ grade.name }}</h3><code>{{ grade.color.toUpperCase() }}</code><span>{{ grade.employees_count }} employé{{ grade.employees_count > 1 ? 's' : '' }}</span></div>
          <div class="direction-permissions">
            <span v-for="key in grade.permissions" :key="key">
              {{ permissionOptions?.find((permission) => permission.key === key)?.label ?? key }}
            </span>
            <small v-if="!grade.permissions.length">Aucune permission opérationnelle</small>
          </div>
        </div>
        <div class="direction-actions">
          <button type="button" class="direction-button" @click="editGrade(grade)"><Icon name="lucide:pencil" size="14" /> Modifier</button>
          <button type="button" class="direction-button direction-button--danger" @click="deleteGrade(grade)"><Icon name="lucide:trash-2" size="14" /> Supprimer</button>
        </div>
      </article>
      <div v-if="!grades.length" class="direction-empty">Aucun grade n’est configuré.</div>
    </section>
  </main>
</template>

<style scoped>
.direction-page { flex: 1; min-height: 0; overflow: auto; padding: clamp(18px, 3vw, 36px); background: var(--dp-bg); }
.direction-header, .direction-section, .direction-error { width: min(1120px, 100%); margin-right: auto; margin-left: auto; }
.direction-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.direction-eyebrow { margin-bottom: 6px; color: var(--dp-accent); font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.direction-header h1 { margin: 0; font-size: clamp(24px, 3vw, 34px); }.direction-header p, .direction-section__heading p { margin: 7px 0 0; color: var(--dp-text-2); font-size: 12px; }
.direction-count { display: grid; grid-template-columns: auto auto; align-items: center; gap: 2px 9px; padding: 12px 15px; border: 1px solid var(--dp-line); background: var(--dp-panel); color: var(--dp-accent); }
.direction-count strong { color: var(--dp-text); font-size: 18px; }.direction-count span { grid-column: 2; color: var(--dp-text-2); font-size: 10px; }
.direction-section { margin-bottom: 16px; padding: 19px; border: 1px solid var(--dp-line); background: var(--dp-panel); }.direction-section__heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 15px; }.direction-section h2 { margin: 0; font-size: 16px; }
.direction-form { display: grid; grid-template-columns: minmax(200px, 1fr) 150px; align-items: end; gap: 12px; }.direction-form > label { display: grid; gap: 6px; color: var(--dp-text-2); font-size: 10px; font-weight: 650; }
.direction-form input:not([type='checkbox']) { width: 100%; min-height: 36px; border: 1px solid var(--dp-line); border-radius: 4px; padding: 0 10px; color: var(--dp-text); background: #101419; font: inherit; font-size: 12px; }
.direction-color-field { min-width: 0; }.direction-color-control { display: flex; min-height: 36px; align-items: center; gap: 8px; }.direction-color-control input[type='color'] { width: 48px; min-height: 32px; padding: 3px; cursor: pointer; }.direction-color-control code, .direction-grade__title code { color: var(--dp-text-dim); font-size: 10px; }
.direction-form fieldset { display: grid; grid-column: 1 / -1; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 9px 16px; margin: 0; padding: 12px; border: 1px solid var(--dp-line); }.direction-form legend { padding: 0 5px; color: var(--dp-text-dim); font-size: 10px; }.direction-form fieldset label { display: flex; align-items: flex-start; gap: 7px; color: var(--dp-text-2); font-size: 11px; }
.direction-button { display: inline-flex; min-height: 34px; align-items: center; justify-content: center; gap: 6px; padding: 0 10px; border: 1px solid var(--dp-line); border-radius: 4px; color: var(--dp-text-2); background: transparent; font-size: 10px; font-weight: 650; cursor: pointer; }.direction-button--primary { justify-self: start; color: #0c1710; border-color: transparent; background: var(--dp-accent); }.direction-button--danger { color: var(--dp-danger); background: var(--dp-danger-soft); }.direction-button:disabled { opacity: .5; cursor: not-allowed; }
.direction-grade { display: flex; align-items: center; gap: 13px; padding: 11px; border: 1px solid var(--dp-line); background: #151a1f; }.direction-grade + .direction-grade { margin-top: 7px; }.direction-grade__level { display: grid; width: 48px; height: 48px; flex: 0 0 48px; place-content: center; justify-items: center; border: 1px solid color-mix(in srgb, var(--grade-color) 60%, transparent); color: var(--grade-color); background: color-mix(in srgb, var(--grade-color) 16%, transparent); }.direction-grade__level span { font-size: 8px; }.direction-grade__level strong { font-size: 17px; }.direction-grade__main { flex: 1; min-width: 0; }.direction-grade__title { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }.direction-grade__title h3 { margin: 0; font-size: 13px; }.direction-grade__title > span:last-child { color: var(--dp-text-dim); font-size: 9px; }.direction-grade__swatch { width: 10px; height: 10px; border: 1px solid rgba(255,255,255,.25); border-radius: 50%; }.direction-permissions { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }.direction-permissions > span { padding: 3px 6px; border: 1px solid var(--dp-line); color: var(--dp-text-2); font-size: 9px; }.direction-permissions small, .direction-muted { color: var(--dp-text-dim); font-size: 10px; }.direction-actions { display: flex; flex-wrap: wrap; gap: 5px; }.direction-empty { padding: 18px; color: var(--dp-text-dim); text-align: center; font-size: 11px; }
.direction-error { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; padding: 10px 12px; border: 1px solid var(--dp-danger-line); color: #f0a29d; background: var(--dp-danger-soft); font-size: 11px; }.direction-error span { flex: 1; }.direction-error button { color: inherit; }.direction-spin { animation: direction-spin 1s linear infinite; }@keyframes direction-spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) { .direction-grade { align-items: flex-start; flex-wrap: wrap; }.direction-actions { width: 100%; padding-left: 61px; }.direction-form { grid-template-columns: 1fr; }.direction-form fieldset { grid-column: auto; } }
</style>
