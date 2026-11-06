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
const deletingGradeId = ref<number | null>(null)
const error = ref('')
const gradeDialog = ref<HTMLDialogElement | null>(null)
const gradeSearch = ref('')
const form = reactive({ name: '', level: 1, color: '#46996d', permissions: [] as string[] })
const visibleGrades = computed(() => {
  const query = gradeSearch.value.trim().toLocaleLowerCase('fr')
  if (!query) return grades.value
  return grades.value.filter((grade) => {
    const permissions = grade.permissions.map((key) =>
      permissionOptions.value?.find((permission) => permission.key === key)?.label ?? key
    )
    return [grade.name, String(grade.level), ...permissions].join(' ').toLocaleLowerCase('fr').includes(query)
  })
})
const assignedEmployeeCount = computed(() => grades.value.reduce((total, grade) => total + grade.employees_count, 0))

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

async function openGradeDialog(grade?: Grade) {
  resetForm()
  error.value = ''
  if (grade) {
    editingId.value = grade.id
    form.name = grade.name
    form.level = grade.level
    form.color = grade.color
    form.permissions = [...grade.permissions]
  }
  await nextTick()
  if (!gradeDialog.value?.open) gradeDialog.value?.showModal()
  gradeDialog.value?.querySelector<HTMLInputElement>('[autocomplete="off"]')?.focus()
}

function closeGradeDialog() {
  if (saving.value) return
  gradeDialog.value?.close()
}

function onGradeDialogClose() {
  resetForm()
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
    gradeDialog.value?.close()
  } catch (cause) {
    error.value = messageFromError(cause, 'Enregistrement du grade impossible.')
  } finally {
    saving.value = false
  }
}

async function deleteGrade(grade: Grade) {
  if (!window.confirm(`Supprimer le grade « ${grade.name} » ?`)) return
  if (deletingGradeId.value !== null) return
  deletingGradeId.value = grade.id
  error.value = ''
  try {
    await $fetch(`/api/direction/grades/${grade.id}`, { method: 'DELETE', credentials: 'include' })
    grades.value = grades.value.filter((item) => item.id !== grade.id)
    if (editingId.value === grade.id) closeGradeDialog()
  } catch (cause) {
    error.value = messageFromError(cause, 'Suppression du grade impossible.')
  } finally {
    deletingGradeId.value = null
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
      <div class="direction-header__actions">
        <div class="direction-overview" aria-label="Résumé de la hiérarchie">
          <div class="direction-count"><Icon name="lucide:shield" size="18" /><strong>{{ grades.length }}</strong><span>grades</span></div>
          <div class="direction-count direction-count--muted"><Icon name="lucide:users-round" size="18" /><strong>{{ assignedEmployeeCount }}</strong><span>agents classés</span></div>
        </div>
        <button type="button" class="direction-button direction-button--primary direction-add" @click="openGradeDialog()">
          <Icon name="lucide:plus" size="17" /> Ajouter un grade
        </button>
      </div>
    </header>

    <div v-if="error && !gradeDialog?.open" class="direction-error" role="alert">
      <Icon name="lucide:circle-alert" size="17" /><span>{{ error }}</span>
      <button type="button" aria-label="Fermer" @click="error = ''"><Icon name="lucide:x" size="15" /></button>
    </div>

    <dialog
      ref="gradeDialog"
      class="direction-dialog"
      aria-labelledby="direction-dialog-title"
      @click.self="closeGradeDialog"
      @keydown.esc.prevent="closeGradeDialog"
      @cancel.prevent="closeGradeDialog"
      @close="onGradeDialogClose"
    >
      <form class="direction-dialog__content" @submit.prevent="saveGrade">
        <header class="direction-dialog__header">
          <div class="direction-dialog__icon"><Icon :name="editingId ? 'lucide:shield-ellipsis' : 'lucide:shield-plus'" size="19" /></div>
          <div>
            <p class="direction-eyebrow">BCES · ORGANISATION DU SERVICE</p>
            <h2 id="direction-dialog-title">{{ editingId ? 'Modifier un grade' : 'Ajouter un grade' }}</h2>
            <p>Définissez son niveau hiérarchique et ses permissions opérationnelles.</p>
          </div>
          <button type="button" class="direction-dialog__close" aria-label="Fermer la fenêtre" :disabled="saving" @click="closeGradeDialog">
            <Icon name="lucide:x" size="18" />
          </button>
        </header>
        <div v-if="error" class="direction-error direction-dialog__error" role="alert">
          <Icon name="lucide:circle-alert" size="17" /><span>{{ error }}</span>
        </div>
        <div class="direction-form">
        <label>
          <span>Nom du grade</span>
          <input v-model="form.name" required maxlength="64" autocomplete="off" placeholder="Ex. Médecin-chef">
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
        </div>
        <footer class="direction-dialog__footer">
          <button type="button" class="direction-button" :disabled="saving" @click="closeGradeDialog">Annuler</button>
          <button class="direction-button direction-button--primary" type="submit" :disabled="saving || !form.name.trim() || !Number.isInteger(form.level) || form.level < 1">
            <Icon :name="saving ? 'lucide:loader-circle' : 'lucide:save'" size="15" :class="{ 'direction-spin': saving }" />
            {{ saving ? 'Enregistrement…' : editingId ? 'Enregistrer le grade' : 'Créer le grade' }}
          </button>
        </footer>
      </form>
    </dialog>

    <section class="direction-section">
      <div class="direction-section__heading">
        <div><h2>Hiérarchie des grades</h2><p>Les grades attribués à des employés ne peuvent être supprimés qu’après réattribution.</p></div>
        <label class="direction-search">
          <Icon name="lucide:search" size="15" />
          <input v-model="gradeSearch" type="search" aria-label="Rechercher un grade" placeholder="Rechercher un grade">
        </label>
      </div>
      <article v-for="grade in visibleGrades" :key="grade.id" class="direction-grade">
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
          <button type="button" class="direction-button" @click="openGradeDialog(grade)"><Icon name="lucide:pencil" size="14" /> Modifier</button>
          <button type="button" class="direction-button direction-button--danger" :disabled="deletingGradeId !== null" @click="deleteGrade(grade)"><Icon name="lucide:trash-2" size="14" /> {{ deletingGradeId === grade.id ? 'Suppression…' : 'Supprimer' }}</button>
        </div>
      </article>
      <div v-if="!visibleGrades.length" class="direction-empty">
        <Icon :name="gradeSearch ? 'lucide:search-x' : 'lucide:shield'" size="21" />
        <p>{{ gradeSearch ? 'Aucun grade ne correspond à cette recherche.' : 'Aucun grade n’est configuré.' }}</p>
        <button v-if="gradeSearch" type="button" class="direction-button" @click="gradeSearch = ''">Effacer la recherche</button>
        <button v-else type="button" class="direction-button direction-button--primary" @click="openGradeDialog()">Ajouter le premier grade</button>
      </div>
    </section>
  </main>
</template>

<style scoped>
.direction-page { flex: 1; min-height: 0; overflow: auto; padding: clamp(22px, 4vw, 48px); background: var(--dp-bg); }
.direction-header, .direction-section, .direction-error { width: min(1180px, 100%); margin-right: auto; margin-left: auto; }
.direction-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.direction-eyebrow { margin-bottom: 9px; color: var(--dp-accent); font-size: 10px; font-weight: 800; letter-spacing: .15em; }
.direction-header h1 { margin: 0; font-size: clamp(28px, 3.2vw, 38px); letter-spacing: -.04em; }.direction-header p, .direction-section__heading p { margin: 9px 0 0; color: var(--dp-text-2); font-size: 13px; line-height: 1.6; }
.direction-count { display: grid; min-width: 126px; grid-template-columns: auto auto; align-items: center; gap: 3px 10px; padding: 14px 16px; border: 1px solid var(--dp-line); border-radius: 14px; background: linear-gradient(145deg, rgba(255,255,255,.025), transparent 70%), var(--dp-panel); color: var(--dp-accent); }
.direction-count strong { color: var(--dp-text); font-size: 21px; font-variant-numeric: tabular-nums; }.direction-count span { grid-column: 2; color: var(--dp-text-2); font-size: 11px; }
.direction-overview { display: flex; gap: 8px; }.direction-count--muted { color: var(--dp-text-dim); }
.direction-section { margin-bottom: 18px; padding: clamp(18px, 2.5vw, 28px); border: 1px solid var(--dp-line); border-radius: 18px; background: var(--dp-panel); box-shadow: 0 16px 40px rgba(0, 0, 0, .14); }.direction-section__heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 20px; }.direction-section h2 { margin: 0; font-size: 20px; letter-spacing: -.02em; }
.direction-form { display: grid; grid-template-columns: minmax(200px, 1fr) 150px; align-items: end; gap: 12px; }.direction-form > label { display: grid; gap: 6px; color: var(--dp-text-2); font-size: 10px; font-weight: 650; }
.direction-form input:not([type='checkbox']) { width: 100%; min-height: 40px; border: 1px solid var(--dp-line); border-radius: 9px; padding: 0 11px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.direction-color-field { min-width: 0; }.direction-color-control { display: flex; min-height: 36px; align-items: center; gap: 8px; }.direction-color-control input[type='color'] { width: 48px; min-height: 32px; padding: 3px; cursor: pointer; }.direction-color-control code, .direction-grade__title code { color: var(--dp-text-dim); font-size: 10px; }
.direction-form fieldset { display: grid; grid-column: 1 / -1; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 11px 16px; margin: 0; padding: 14px; border: 1px solid var(--dp-line); border-radius: 12px; }.direction-form legend { padding: 0 6px; color: var(--dp-text-dim); font-size: 10px; }.direction-form fieldset label { display: flex; align-items: flex-start; gap: 8px; color: var(--dp-text-2); font-size: 11px; line-height: 1.5; }
.direction-button { display: inline-flex; min-height: 38px; align-items: center; justify-content: center; gap: 7px; padding: 0 12px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text-2); background: transparent; font-size: 10px; font-weight: 650; cursor: pointer; transition: background .16s ease, border-color .16s ease, transform .16s ease; }.direction-button--primary { justify-self: start; color: #0c1710; border-color: transparent; background: var(--dp-accent); }.direction-button--danger { color: var(--dp-danger); background: var(--dp-danger-soft); }.direction-button:disabled { opacity: .5; cursor: not-allowed; }
.direction-grade { display: grid; grid-template-columns: 58px minmax(0, 1fr) auto; align-items: center; gap: 16px; padding: 16px; border: 1px solid var(--dp-line); border-radius: 14px; background: var(--dp-panel-2); }.direction-grade + .direction-grade { margin-top: 10px; }.direction-grade__level { display: grid; width: 58px; height: 58px; place-content: center; justify-items: center; border: 1px solid color-mix(in srgb, var(--grade-color) 60%, transparent); border-radius: 14px; color: var(--grade-color); background: color-mix(in srgb, var(--grade-color) 16%, transparent); }.direction-grade__level span { font-size: 9px; }.direction-grade__level strong { font-size: 21px; }.direction-grade__main { min-width: 0; }.direction-grade__title { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }.direction-grade__title h3 { margin: 0; font-size: 15px; }.direction-grade__title > span:last-child { padding: 4px 8px; border: 1px solid var(--dp-line); border-radius: 999px; color: var(--dp-text-2); background: rgba(255,255,255,.025); font-size: 10px; }.direction-grade__swatch { width: 11px; height: 11px; border: 1px solid rgba(255,255,255,.25); border-radius: 50%; }.direction-permissions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }.direction-permissions > span { padding: 4px 9px; border: 1px solid var(--dp-line); border-radius: 999px; color: var(--dp-text-2); background: rgba(255,255,255,.025); font-size: 10px; }.direction-permissions small, .direction-muted { color: var(--dp-text-dim); font-size: 11px; }.direction-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }.direction-empty { display: grid; min-height: 170px; justify-items: center; align-content: center; gap: 10px; padding: 24px; border: 1px dashed var(--dp-line-strong); border-radius: 14px; color: var(--dp-text-dim); text-align: center; font-size: 12px; }
.direction-search { display: flex; min-width: min(280px, 100%); min-height: 42px; align-items: center; gap: 9px; padding: 0 12px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-dim); background: var(--dp-bg); }
.direction-search:focus-within { border-color: var(--dp-accent-line); }
.direction-search input { width: 100%; min-width: 0; min-height: 38px; border: 0; outline: 0; color: var(--dp-text); background: transparent; font: inherit; font-size: 12px; }
.direction-empty { display: grid; justify-items: center; gap: 9px; }.direction-empty p { margin: 0; }
.direction-button--primary { text-decoration: none; }
.direction-page { background: radial-gradient(ellipse at 86% 0, rgba(70, 153, 109, .11), transparent 40%), var(--dp-bg); }
.direction-header { padding: clamp(22px, 3vw, 34px); border: 1px solid var(--dp-line); border-radius: 22px; background: linear-gradient(110deg, rgba(70, 153, 109, .12), transparent 72%), var(--dp-panel); box-shadow: 0 18px 48px rgba(0, 0, 0, .16); }
.direction-header h1 { letter-spacing: -.03em; }
.direction-header__actions { display: flex; align-items: center; gap: 10px; }
.direction-add { min-height: 42px; padding: 0 16px; font-size: 11px; white-space: nowrap; }
.direction-section { background: linear-gradient(145deg, rgba(255,255,255,.025), transparent 55%), var(--dp-panel); }
.direction-grade { transition: border-color .16s ease, background .16s ease, transform .16s ease; }.direction-grade:hover { transform: translateY(-1px); border-color: var(--dp-line-strong); background: #1b2228; }
.direction-form input:focus-visible, .direction-search:focus-within { outline: 2px solid rgba(70, 153, 109, .24); outline-offset: 1px; }
.direction-button:focus-visible { outline: 2px solid var(--dp-accent); outline-offset: 2px; }
.direction-button:hover:not(:disabled) { border-color: var(--dp-line-strong); color: var(--dp-text); background-color: var(--dp-panel-3); }
.direction-button--primary:hover:not(:disabled) { filter: brightness(1.08); color: #0c1710; background: var(--dp-accent); }
.direction-dialog { position: fixed; inset: 50% auto auto 50%; width: min(760px, calc(100vw - 28px)); max-width: 760px; max-height: min(90dvh, 820px); margin: 0; padding: 0; overflow: auto; transform: translate(-50%, -50%); border: 1px solid var(--dp-line-strong); border-radius: 18px; color: var(--dp-text); background: var(--dp-panel); box-shadow: 0 24px 80px rgba(0, 0, 0, .55); }
.direction-dialog::backdrop { background: rgba(5, 8, 11, .76); backdrop-filter: blur(5px); }
.direction-dialog__content { display: grid; gap: 18px; margin: 0; padding: clamp(18px, 4vw, 28px); }
.direction-dialog__header { display: grid; grid-template-columns: 42px minmax(0, 1fr) 34px; align-items: start; gap: 13px; padding-bottom: 17px; border-bottom: 1px solid var(--dp-line); }
.direction-dialog__icon { display: grid; width: 42px; height: 42px; place-items: center; border: 1px solid var(--dp-accent-line); border-radius: 12px; color: var(--dp-accent); background: var(--dp-accent-soft); }
.direction-dialog__header .direction-eyebrow { margin: 1px 0 5px; }
.direction-dialog__header h2 { margin: 0; color: var(--dp-text); font-size: 19px; letter-spacing: -.02em; }
.direction-dialog__header p:last-child { margin: 5px 0 0; color: var(--dp-text-2); font-size: 11px; line-height: 1.5; }
.direction-dialog__close { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid var(--dp-line); color: var(--dp-text-2); background: transparent; cursor: pointer; }
.direction-dialog__close:hover:not(:disabled) { color: var(--dp-text); background: var(--dp-panel-3); }
.direction-dialog__close:disabled { opacity: .5; cursor: wait; }
.direction-dialog .direction-form { gap: 14px; }
.direction-dialog .direction-form > label { font-size: 11px; }
.direction-dialog .direction-form input:not([type='checkbox']) { min-height: 40px; font-size: 12px; }
.direction-dialog .direction-form fieldset { gap: 12px 16px; }
.direction-dialog .direction-form fieldset label { line-height: 1.5; }
.direction-dialog__error { width: 100%; margin: 0; }
.direction-dialog__footer { display: flex; justify-content: flex-end; gap: 9px; padding-top: 15px; border-top: 1px solid var(--dp-line); }
.direction-dialog__footer .direction-button { min-height: 40px; padding: 0 14px; font-size: 11px; }
.direction-dialog[open] { animation: direction-dialog-in .16s ease-out; }
@keyframes direction-dialog-in { from { opacity: 0; transform: translate(-50%, calc(-50% + 8px)) scale(.99); } to { opacity: 1; transform: translate(-50%, -50%) scale(1); } }
.direction-error { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; padding: 12px 14px; border: 1px solid var(--dp-danger-line); border-radius: 12px; color: #f0a29d; background: var(--dp-danger-soft); font-size: 12px; }.direction-error span { flex: 1; }.direction-error button { color: inherit; }.direction-spin { animation: direction-spin 1s linear infinite; }@keyframes direction-spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) { .direction-page { padding: 22px 18px; }.direction-header { align-items: flex-start; flex-direction: column; }.direction-header__actions { width: 100%; flex-wrap: wrap; }.direction-overview { flex: 1; }.direction-count { flex: 1; }.direction-add { width: 100%; }.direction-section__heading { align-items: flex-start; flex-direction: column; }.direction-search { width: 100%; }.direction-grade { grid-template-columns: 48px minmax(0, 1fr); align-items: start; gap: 12px; padding: 13px; }.direction-grade__level { width: 48px; height: 48px; }.direction-actions { grid-column: 2; width: auto; justify-content: flex-start; padding-left: 0; }.direction-form { grid-template-columns: 1fr; }.direction-form fieldset { grid-column: auto; }.direction-dialog { width: calc(100vw - 20px); max-height: 92dvh; }.direction-dialog__header { grid-template-columns: 36px minmax(0, 1fr) 32px; gap: 9px; }.direction-dialog__icon { width: 36px; height: 36px; }.direction-dialog__footer { flex-direction: column-reverse; }.direction-dialog__footer > button { width: 100%; } }
</style>
