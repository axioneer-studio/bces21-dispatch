<script setup lang="ts">
import ConfirmDialog from '~/components/ConfirmDialog.vue'

/**
 * Page Formation : une fiche par employé en formation, comme la feuille de
 * suivi du BCES. Deux onglets, nommés d'après les grades cochés dans Direction :
 * « Période d'essai » (ex. Interne) et « En formation » (ex. Résident). Les
 * formateurs remplissent les fiches ; les modules, le questionnaire et les
 * seuils de passage se gèrent par la Direction, « Gérer l'hôpital » et le
 * Responsable du pôle Formation (`can_manage`).
 */
type Stage = 'trial' | 'training'
type Category = 'basics' | 'tools' | 'interventions' | 'injuries' | 'mandatory' | 'optional'
type Tone = 'done' | 'ready' | 'normal' | 'warning' | 'urgent'
type Bar = Category | 'overall'
/** Seuils du passage : barres en %, notes sur 20 (moyenne, simulation de la période de formation). */
type ThresholdKey = Bar | 'average' | 'resident_simulation'

interface FormationModule {
  id: number
  category: Category
  name: string
  emoji: string | null
  /** À valider au plus haut pour le passage, même forcé. */
  is_required: boolean
}

interface Question {
  id: number
  question: string
  answer: string
}

interface Person {
  id: number
  name: string
}

interface Grade {
  id: number
  name: string
  level: number
}

interface Criterion {
  key: string
  label: string
}

interface Fiche {
  employee_id: number
  name: string
  stage: Stage
  grade_name: string | null
  grade_color: string | null
  arrival_date: string | null
  days: number | null
  mentors: Person[]
  /** Niveau par module ; absent : Non observé. */
  levels: Record<string, number>
  answers: number[]
  /** Note de 1 à 5 par critère. */
  simulation: Record<string, number>
  resident_simulation: Record<string, number>
  notes: string
  progress: Record<Category | 'overall', number>
  questionnaire_score: number | null
  simulation_score: number | null
  average: number | null
  resident_simulation_score: number | null
  status: { label: string; tone: Tone } | null
  /** Ce qui manque pour le passage sans forcer (vide : possible). */
  blockers: string[]
  /** Modules obligatoires pas encore validés : exigés même pour forcer. */
  missing_required: string[]
  can_pass_resident: boolean
  resident_at: string | null
  can_complete: boolean
  next_grade_name: string | null
  completed_at: string | null
}

function sortFichesByArrival(fiches: Fiche[]) {
  return [...fiches].sort((a, b) => {
    if (!a.arrival_date) return b.arrival_date ? 1 : 0
    if (!b.arrival_date) return -1
    return a.arrival_date.localeCompare(b.arrival_date)
  })
}

interface FormationPage {
  modules: FormationModule[]
  questions: Question[]
  criteria: Criterion[]
  resident_criteria: Criterion[]
  interns: Fiche[]
  residents: Fiche[]
  completed: Fiche[]
  trainers: Person[]
  trial_grades: Grade[]
  training_grades: Grade[]
  thresholds: Record<ThresholdKey, number>
  can_manage: boolean
  /** Forcer un passage : Direction et Responsable du pôle Formation. */
  can_force: boolean
}

const API = '/api/formation'

const CATEGORIES: Record<Stage, { key: Category; label: string }[]> = {
  trial: [
    { key: 'basics', label: 'Validations basiques' },
    { key: 'tools', label: 'Gestion des outils' },
    { key: 'interventions', label: 'Type d’intervention' },
    { key: 'injuries', label: 'Blessures' }
  ],
  training: [
    { key: 'mandatory', label: 'Formations obligatoires' },
    { key: 'optional', label: 'Formations facultatives' }
  ]
}

/** Barres de progression de chaque étape, avec leur seuil de passage. */
const BARS: Record<Stage, { key: Bar; label: string; total?: boolean }[]> = {
  trial: [...CATEGORIES.trial, { key: 'overall', label: 'Progression totale', total: true }],
  training: CATEGORIES.training
}

/** Types dont la case « Obligatoire » est cochée par défaut à la création d'un module. */
const REQUIRED_BY_DEFAULT: Category[] = ['basics', 'mandatory']

/** Niveaux et leur couleur : 0 rouge, puis jusqu'au vert au plus haut. */
/**
 * Libellé complet (légende, info-bulle) et court (liste du niveau, pour laisser
 * la place au nom du module).
 */
const LEVELS: Record<Stage, { value: number; icon: string; label: string; short: string; tone: string }[]> = {
  trial: [
    { value: 0, icon: '❌', label: 'Non observé', short: 'Non observé', tone: 'none' },
    { value: 1, icon: '👁️', label: 'Observé', short: 'Observé', tone: 'seen' },
    { value: 2, icon: '🧾', label: 'Pratiqué avec aide', short: 'Avec aide', tone: 'practiced' },
    { value: 3, icon: '✅', label: 'Pratiqué en autonomie', short: 'Autonomie', tone: 'done' }
  ],
  training: [
    { value: 0, icon: '❌', label: 'Non observé', short: 'Non observé', tone: 'none' },
    { value: 1, icon: '🧾', label: 'Pratiqué', short: 'Pratiqué', tone: 'practiced' },
    { value: 2, icon: '✅', label: 'Validé', short: 'Validé', tone: 'done' }
  ]
}

function levelLabel(level: number) {
  return LEVELS[viewStage.value].find((item) => item.value === level)?.label ?? ''
}

const toast = useAppToast()

const page = ref<FormationPage | null>(null)
const loaded = ref(false)
const loadError = ref('')
const busy = ref(false)
const { active: stage, select: selectStage } = useHashTab(['trial', 'training'] as const, 'trial', 0, 'stage')
const selected = reactive<Record<Stage, number | null>>({ trial: null, training: null })
const notesDraft = ref('')
const completedOpen = ref(false)
/**
 * Onglets de la fiche. Période d'essai : la fiche et le questionnaire. En
 * formation : la fiche, puis les archives de la période d'essai (sa fiche et
 * son questionnaire, en lecture seule).
 */
type FicheTab = 'fiche' | 'trial-archive' | 'questionnaire'
const { active: ficheTab, select: selectFicheTab } = useHashTab(
  ['fiche', 'trial-archive', 'questionnaire'] as const,
  'fiche',
  1,
  'fiche'
)
const ficheView = computed<FicheTab>(() =>
  stage.value === 'trial' && ficheTab.value === 'trial-archive' ? 'fiche' : ficheTab.value
)
/** Étape des modules et de la simulation affichés : celle de la fiche, ou la période d'essai en archive. */
const viewStage = computed<Stage>(() => (ficheView.value === 'trial-archive' ? 'trial' : stage.value))
/** Une étape passée ne se modifie plus : ses modules, sa simulation et son questionnaire sont en lecture seule. */
const archived = computed(() => current.value !== null && current.value.stage !== (ficheView.value === 'questionnaire' ? 'trial' : viewStage.value))

function gradeNames(grades: Grade[] | undefined, fallback: string) {
  return grades?.length ? grades.map((grade) => grade.name).join(' / ') : fallback
}

/** Noms des grades cochés dans Direction, à la place de « Interne » et « Résident ». */
const trialLabel = computed(() => gradeNames(page.value?.trial_grades, 'Période d’essai'))
const trainingLabel = computed(() => gradeNames(page.value?.training_grades, 'En formation'))

const tabs = computed(() => [
  { key: 'trial' as const, label: trialLabel.value, icon: 'lucide:clipboard-check', count: page.value?.interns.length ?? 0 },
  { key: 'training' as const, label: trainingLabel.value, icon: 'lucide:graduation-cap', count: page.value?.residents.length ?? 0 }
])

const fiches = computed(() => {
  const source = (stage.value === 'trial' ? page.value?.interns : page.value?.residents) ?? []
  return sortFichesByArrival(source)
})
const current = computed(() => fiches.value.find((fiche) => fiche.employee_id === selected[stage.value]) ?? null)

watch(stage, () => {
  notesDraft.value = current.value?.notes ?? ''
})

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === 'object' && cause !== null && 'data' in cause) {
    const data = cause.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
  }
  return fallback
}

/** Pourcentage entier, arrondi vers le bas comme les seuils : 99,6 % n'affiche pas 100 %. */
function percentValue(value: number) {
  return Math.floor(value * 100 + 1e-9)
}

/** Pourcentage affiché, à la française (« 25 % »). */
function percent(value: number) {
  return `${percentValue(value)} %`
}

/** Seuil de l'étape atteint (un seuil à 0 n'exige rien : rien n'est mis en avant). */
function reached(key: ThresholdKey, value: number | null) {
  const goal = page.value?.thresholds[key] ?? 0
  if (value === null || goal <= 0) return false
  if (key === 'average' || key === 'resident_simulation') return value >= goal
  return percentValue(value) >= goal
}

/** Étapes des barres et notes des informations générales : la période d'essai, puis celle de formation. */
const infoStages = computed<Stage[]>(() => (current.value?.stage === 'training' ? ['trial', 'training'] : ['trial']))

/** Seuil affiché sur la barre : ceux de l'étape de la fiche, pas ceux d'une étape passée. */
function goalOn(key: Bar, barStage: Stage) {
  return current.value?.stage === barStage && (page.value?.thresholds[key] ?? 0) > 0
}

/** Largeur d'une barre de progression : sans espace, sinon le CSS l'ignore. */
function barWidth(value: number) {
  return `${Math.min(Math.max(value, 0), 1) * 100}%`
}

function score(value: number | null) {
  return value === null ? '—' : `${Number.isInteger(value) ? value : value.toFixed(1)} / 20`
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString('fr-FR') : '—'
}

function modulesOf(category: Category) {
  return page.value?.modules.filter((module) => module.category === category) ?? []
}

function levelOf(fiche: Fiche, module: FormationModule) {
  return fiche.levels[String(module.id)] ?? 0
}

function toneOf(level: number) {
  return LEVELS[viewStage.value].find((item) => item.value === level)?.tone ?? 'none'
}

const mentorOptions = computed(() => {
  const fiche = current.value
  if (!fiche || !page.value) return []
  const taken = new Set(fiche.mentors.map((mentor) => mentor.id))
  return page.value.trainers.filter((trainer) => trainer.id !== fiche.employee_id && !taken.has(trainer.id))
})

/**
 * Ce qui manque pour le passage, dans l'info-bulle du bouton : modules
 * obligatoires, seuils des barres et de la note, grade au-dessus (calculé par
 * le serveur, qui vérifie les mêmes conditions au passage).
 */
const blockers = computed(() => current.value?.blockers ?? [])

/** Passage possible sans forcer. */
const canPass = computed(() => {
  const fiche = current.value
  return Boolean(fiche && (fiche.stage === 'trial' ? fiche.can_pass_resident : fiche.can_complete))
})

/**
 * Forcer le passage : la Direction et le Responsable du pôle Formation passent
 * outre les seuils, mais les modules obligatoires restent exigés.
 */
const force = ref(false)
const canForce = computed(() => Boolean(current.value?.next_grade_name && !current.value.missing_required.length))
const forceHint = computed(() => {
  const fiche = current.value
  if (!fiche) return ''
  if (fiche.missing_required.length) return `Pour forcer, il faut valider les modules obligatoires : ${fiche.missing_required.join(', ')}`
  if (!fiche.next_grade_name) return 'Aucun grade au-dessus dans Direction'
  return 'Passe outre les seuils ; les modules obligatoires sont validés'
})
const passEnabled = computed(() => canPass.value || (force.value && canForce.value))

watch(() => [current.value?.employee_id, stage.value], () => {
  force.value = false
})

async function load() {
  try {
    const data = await $fetch<FormationPage>(API, { credentials: 'include' })
    page.value = data
    for (const [key, list] of [['trial', data.interns], ['training', data.residents]] as const) {
      if (!list.some((fiche) => fiche.employee_id === selected[key])) {
        selected[key] = sortFichesByArrival(list)[0]?.employee_id ?? null
      }
    }
    notesDraft.value = current.value?.notes ?? ''
    loadError.value = ''
  } catch (cause) {
    loadError.value = messageFromError(cause, 'Impossible de charger les fiches de formation.')
  } finally {
    loaded.value = true
  }
}

const TAB_KEY = 'bces.formation.tab'

function setStage(key: Stage) {
  selectStage(key)
  notesDraft.value = current.value?.notes ?? ''
  try {
    localStorage.setItem(TAB_KEY, key)
  } catch {
    // Stockage indisponible (navigation privée…) : l'onglet reste pour cette visite.
  }
}

function select(fiche: Fiche) {
  selected[stage.value] = fiche.employee_id
  notesDraft.value = fiche.notes
}

function replaceFiche(fiche: Fiche) {
  if (!page.value) return
  const key = fiche.stage === 'trial' ? 'interns' : 'residents'
  page.value[key] = page.value[key].map((item) => (item.employee_id === fiche.employee_id ? fiche : item))
}

/** Envoie une modification de la fiche ; la fiche renvoyée remplace l'ancienne. */
async function send(path: string, method: 'PATCH' | 'PUT', body: Record<string, unknown>, fallback: string) {
  const fiche = current.value
  if (!fiche || busy.value) return
  busy.value = true
  try {
    replaceFiche(await $fetch<Fiche>(`${API}/${fiche.employee_id}${path}`, { method, body, credentials: 'include' }))
  } catch (cause) {
    toast.error(messageFromError(cause, fallback))
  } finally {
    busy.value = false
  }
}

function setArrival(event: Event) {
  const value = (event.target as HTMLInputElement).value
  void send('', 'PATCH', { arrival_date: value || null }, 'Date d’arrivée impossible à enregistrer.')
}

function setMentors(ids: number[]) {
  void send('', 'PATCH', { mentor_ids: ids }, 'Mentors impossibles à enregistrer.')
}

function addMentor(event: Event) {
  const field = event.target as HTMLSelectElement
  const id = Number(field.value)
  field.value = ''
  if (id && current.value) setMentors([...current.value.mentors.map((mentor) => mentor.id), id])
}

function removeMentor(id: number) {
  if (current.value) setMentors(current.value.mentors.filter((mentor) => mentor.id !== id).map((mentor) => mentor.id))
}

function setLevel(module: FormationModule, event: Event) {
  const level = Number((event.target as HTMLSelectElement).value)
  void send(`/modules/${module.id}`, 'PUT', { level }, 'Niveau impossible à enregistrer.')
}

/** Simulation de l'étape de la fiche. */
const simulationField = computed(() => (viewStage.value === 'trial' ? 'simulation' : 'resident_simulation'))
const simulationCriteria = computed(() => (viewStage.value === 'trial' ? page.value?.criteria : page.value?.resident_criteria) ?? [])
const simulationScore = computed(() =>
  current.value ? (viewStage.value === 'trial' ? current.value.simulation_score : current.value.resident_simulation_score) : null
)

const ficheTabs = computed(() => {
  const questionnaire = { key: 'questionnaire' as const, label: 'Questionnaire', icon: 'lucide:list-checks', badge: score(current.value?.questionnaire_score ?? null) }
  return stage.value === 'trial'
    ? [{ key: 'fiche' as const, label: 'Fiche de formation', icon: 'lucide:clipboard-list', badge: '' }, questionnaire]
    : [
        { key: 'fiche' as const, label: 'Fiche de formation', icon: 'lucide:clipboard-list', badge: '' },
        { key: 'trial-archive' as const, label: `Archive ${trialLabel.value}`, icon: 'lucide:archive', badge: percent(current.value?.progress.overall ?? 0) },
        { ...questionnaire, label: 'Archive questionnaire', icon: 'lucide:archive' }
      ]
})

function setSimulation(key: string, event: Event) {
  const fiche = current.value
  if (!fiche) return
  const value = Number((event.target as HTMLSelectElement).value)
  const scores = { ...fiche[simulationField.value] }
  if (value) scores[key] = value
  else delete scores[key]
  void send('', 'PATCH', { [simulationField.value]: scores }, 'Simulation impossible à enregistrer.')
}

function setAnswer(question: Question, event: Event) {
  const correct = (event.target as HTMLInputElement).checked
  void send(`/questions/${question.id}`, 'PUT', { correct }, 'Réponse impossible à enregistrer.')
}

function saveNotes() {
  const fiche = current.value
  if (!fiche || notesDraft.value.trim() === fiche.notes) return
  void send('', 'PATCH', { notes: notesDraft.value }, 'Notes impossibles à enregistrer.')
}

/** Seuil de passage, commun à toutes les fiches : la page se recharge pour recalculer les passages. */
async function saveThreshold(key: ThresholdKey, value: number) {
  if (busy.value) return false
  busy.value = true
  try {
    await $fetch(`${API}/thresholds`, { method: 'PUT', body: { [key]: value }, credentials: 'include' })
    await load()
    return true
  } catch (cause) {
    toast.error(messageFromError(cause, 'Seuil impossible à enregistrer.'))
    return false
  } finally {
    busy.value = false
  }
}

// --- Passages de grade et annulations ---

type Transition = { fiche: Fiche; method: 'POST' | 'DELETE'; path: 'resident' | 'complete'; title: string; message: string; label: string; danger: boolean; done: string; force: boolean }

const transition = ref<Transition | null>(null)
const transitionVisible = ref(false)

function askPass(fiche: Fiche) {
  const grade = fiche.next_grade_name ?? trainingLabel.value
  const forced = !canPass.value && force.value
  const forcedNote = forced ? ` Passage forcé : ${blockers.value.join(', ')}.` : ''
  transition.value = fiche.stage === 'trial'
    ? {
        fiche, method: 'POST', path: 'resident', danger: forced, force: forced,
        title: `${forced ? 'Forcer le passage' : 'Passer'} ${fiche.name} ${grade} ?`,
        message: `Il prend le grade « ${grade} ». Les emojis des modules de ${trialLabel.value} quittent ses compétences. Le passage s’annule depuis sa fiche.${forcedNote}`,
        label: forced ? 'Forcer le passage' : 'Valider le passage', done: `${fiche.name} passe ${grade}.`
      }
    : {
        fiche, method: 'POST', path: 'complete', danger: forced, force: forced,
        title: `${forced ? 'Forcer' : 'Valider'} la fin de formation de ${fiche.name} ?`,
        message: `Il prend le grade « ${grade} ». Les emojis des formations de ${trainingLabel.value} quittent ses compétences. La fin de formation s’annule depuis « Formation terminée ».${forcedNote}`,
        label: forced ? 'Forcer la fin de formation' : 'Valider la fin de formation', done: `${fiche.name} passe ${grade}.`
      }
  transitionVisible.value = true
}

function askCancelPass(fiche: Fiche) {
  transition.value = {
    fiche, method: 'DELETE', path: 'resident', danger: true, force: false,
    title: `Annuler le passage ${trainingLabel.value} de ${fiche.name} ?`,
    message: `Il reprend son grade ${trialLabel.value} ; les emojis de ses modules en autonomie reviennent et ceux de ${trainingLabel.value} partent.`,
    label: 'Annuler le passage', done: `${fiche.name} reprend son grade ${trialLabel.value}.`
  }
  transitionVisible.value = true
}

function askCancelCompletion(fiche: Fiche) {
  transition.value = {
    fiche, method: 'DELETE', path: 'complete', danger: true, force: false,
    title: `Annuler la fin de formation de ${fiche.name} ?`,
    message: `Il reprend son grade ${trainingLabel.value} ; les emojis de ses formations validées reviennent.`,
    label: 'Annuler la fin de formation', done: `${fiche.name} reprend son grade ${trainingLabel.value}.`
  }
  transitionVisible.value = true
}

async function runTransition() {
  const target = transition.value
  if (!target) return
  try {
    const fiche = await $fetch<Fiche>(`${API}/${target.fiche.employee_id}/${target.path}`, {
      method: target.method,
      body: target.method === 'POST' ? { force: target.force } : undefined,
      credentials: 'include'
    })
    force.value = false
    toast.success(target.done)
    await load()
    if (fiche.stage === 'trial' || fiche.stage === 'training') {
      if (page.value?.[fiche.stage === 'trial' ? 'interns' : 'residents'].some((item) => item.employee_id === fiche.employee_id)) {
        selected[fiche.stage] = fiche.employee_id
        setStage(fiche.stage)
      }
    }
  } catch (cause) {
    toast.error(messageFromError(cause, 'Changement de grade impossible.'))
  } finally {
    transition.value = null
  }
}

// --- Modules et questions (Direction, « Gérer l'hôpital », Responsable du pôle Formation) ---

const moduleDialog = ref<HTMLDialogElement | null>(null)
const moduleForm = reactive({ id: null as number | null, category: 'basics' as Category, name: '', emoji: '', is_required: false })
const questionDialog = ref<HTMLDialogElement | null>(null)
const questionForm = reactive({ id: null as number | null, question: '', answer: '' })
const saving = ref(false)

const moduleCategoryLabel = computed(() =>
  [...CATEGORIES.trial, ...CATEGORIES.training].find((category) => category.key === moduleForm.category)?.label
)

async function openModule(category: Category, module?: FormationModule) {
  moduleForm.id = module?.id ?? null
  moduleForm.category = category
  moduleForm.name = module?.name ?? ''
  moduleForm.emoji = module?.emoji ?? ''
  moduleForm.is_required = module?.is_required ?? REQUIRED_BY_DEFAULT.includes(category)
  await nextTick()
  if (!moduleDialog.value?.open) moduleDialog.value?.showModal()
  moduleDialog.value?.querySelector<HTMLInputElement>('input[name="name"]')?.focus()
}

async function openQuestion(question?: Question) {
  questionForm.id = question?.id ?? null
  questionForm.question = question?.question ?? ''
  questionForm.answer = question?.answer ?? ''
  await nextTick()
  if (!questionDialog.value?.open) questionDialog.value?.showModal()
  questionDialog.value?.querySelector<HTMLTextAreaElement>('textarea')?.focus()
}

async function save(dialog: HTMLDialogElement | null, path: string, id: number | null, body: Record<string, unknown>) {
  if (saving.value) return
  saving.value = true
  try {
    await $fetch(id ? `${API}/${path}/${id}` : `${API}/${path}`, { method: id ? 'PATCH' : 'POST', body, credentials: 'include' })
    dialog?.close()
    await load()
  } catch (cause) {
    toast.error(messageFromError(cause, 'Enregistrement impossible.'))
  } finally {
    saving.value = false
  }
}

function saveModule() {
  if (!moduleForm.name.trim()) return
  void save(moduleDialog.value, 'modules', moduleForm.id, {
    category: moduleForm.category,
    name: moduleForm.name,
    emoji: moduleForm.emoji.trim() || null,
    is_required: moduleForm.is_required
  })
}

/** Retire l'emoji et enregistre aussitôt un module existant (un nouveau module s'enregistre avec « Ajouter »). */
function removeModuleEmoji() {
  moduleForm.emoji = ''
  if (moduleForm.id) saveModule()
}

function saveQuestion() {
  if (!questionForm.question.trim()) return
  void save(questionDialog.value, 'questions', questionForm.id, { question: questionForm.question, answer: questionForm.answer })
}

const deleting = ref<{ kind: 'modules' | 'questions'; id: number; title: string; message: string } | null>(null)
const deleteVisible = ref(false)

function askDeleteModule(module: FormationModule) {
  deleting.value = {
    kind: 'modules',
    id: module.id,
    title: `Supprimer « ${module.name} » ?`,
    message: module.emoji
      ? `Les niveaux des employés sont perdus et l’emoji ${module.emoji} quitte leurs compétences.`
      : 'Les niveaux des employés sur ce module sont perdus.'
  }
  deleteVisible.value = true
}

function askDeleteQuestion(question: Question) {
  deleting.value = {
    kind: 'questions',
    id: question.id,
    title: 'Supprimer la question ?',
    message: 'Les réponses à cette question sont perdues ; les notes sont recalculées.'
  }
  deleteVisible.value = true
}

async function confirmDelete() {
  const target = deleting.value
  if (!target) return
  try {
    await $fetch(`${API}/${target.kind}/${target.id}`, { method: 'DELETE', credentials: 'include' })
    await load()
  } catch (cause) {
    toast.error(messageFromError(cause, 'Suppression impossible.'))
  } finally {
    deleting.value = null
  }
}

// --- Rafraîchissement ---

const root = ref<HTMLElement | null>(null)

/** En arrière-plan, hors saisie (champ actif, fenêtre ouverte). */
function refresh() {
  if (busy.value || saving.value || transitionVisible.value || deleteVisible.value) return
  if (moduleDialog.value?.open || questionDialog.value?.open) return
  if (root.value?.contains(document.activeElement) && document.activeElement?.matches('input, textarea, select')) return
  void load()
}

let refreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  try {
    const saved = localStorage.getItem(TAB_KEY)
    const fragment = window.location.hash.slice(1)
    const pathStage = fragment.split('/')[0]
    const hasStageHash = pathStage === 'trial' || pathStage === 'training'
      || new URLSearchParams(fragment).has('stage')
    if ((saved === 'trial' || saved === 'training') && !hasStageHash) {
      selectStage(saved)
    }
  } catch {
    // Stockage indisponible : premier onglet.
  }
  void load()
  refreshTimer = setInterval(refresh, 10_000)
  window.addEventListener('focus', refresh)
})
onBeforeUnmount(() => {
  clearInterval(refreshTimer)
  window.removeEventListener('focus', refresh)
})
</script>

<template>
  <div ref="root" class="formation">
    <nav class="formation-tabs" role="tablist" aria-label="Étapes de la formation">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="stage === tab.key"
        :class="{ 'is-active': stage === tab.key }"
        @click="setStage(tab.key)"
      >
        <Icon :name="tab.icon" size="16" /> {{ tab.label }} <span class="formation-count">{{ tab.count }}</span>
      </button>
    </nav>

    <p v-if="loadError" class="formation-error"><Icon name="lucide:circle-alert" size="15" /> {{ loadError }}</p>
    <div v-else-if="!loaded || !page" class="formation-empty"><Icon name="lucide:loader-circle" size="20" class="formation-spin" /></div>
    <div v-else class="formation-body">
      <aside class="formation-list" :aria-label="stage === 'trial' ? trialLabel : trainingLabel">
        <p v-if="!fiches.length" class="formation-muted">
          Aucun employé : cochez « {{ stage === 'trial' ? 'Période d’essai' : 'En formation' }} » sur un grade dans Direction › Hiérarchie des grades.
        </p>
        <button
          v-for="fiche in fiches"
          :key="fiche.employee_id"
          type="button"
          class="formation-item"
          :class="{ 'is-selected': fiche.employee_id === selected[stage] }"
          :aria-pressed="fiche.employee_id === selected[stage]"
          @click="select(fiche)"
        >
          <span class="formation-item__top">
            <strong>{{ fiche.name }}</strong>
            <span class="formation-item__days">{{ fiche.days === null ? '—' : `J+${fiche.days}` }}</span>
          </span>
          <span class="formation-bar"><span :style="{ width: barWidth(stage === 'trial' ? fiche.progress.overall : fiche.progress.mandatory) }"></span></span>
          <span v-if="fiche.status" class="formation-tone" :class="`is-${fiche.status.tone}`">{{ fiche.status.label }}</span>
          <span v-else class="formation-item__days">Obligatoires : {{ percent(fiche.progress.mandatory) }}</span>
        </button>

        <div v-if="stage === 'training' && page.completed.length" class="formation-completed">
          <button type="button" class="formation-completed__toggle" :aria-expanded="completedOpen" @click="completedOpen = !completedOpen">
            <Icon name="lucide:chevron-down" size="14" :class="{ 'is-closed': !completedOpen }" />
            Formation terminée <span class="formation-count">{{ page.completed.length }}</span>
          </button>
          <ul v-show="completedOpen">
            <li v-for="fiche in page.completed" :key="fiche.employee_id">
              <span><strong>{{ fiche.name }}</strong> · {{ fiche.grade_name }} · {{ formatDate(fiche.completed_at) }}</span>
              <button type="button" class="formation-link" @click="askCancelCompletion(fiche)">Annuler la fin de formation</button>
            </li>
          </ul>
        </div>
      </aside>

      <section v-if="current" class="fiche" :aria-label="`Fiche de ${current.name}`">
        <header class="fiche-head">
          <div class="fiche-head__name">
            <h3>{{ current.name }}</h3>
            <span class="fiche-grade" :style="{ '--grade-color': current.grade_color ?? 'var(--dp-line)' }">{{ current.grade_name }}</span>
            <span v-if="current.status" class="formation-tone" :class="`is-${current.status.tone}`">{{ current.status.label }}</span>
          </div>
          <div class="fiche-pass">
            <!-- Forcer : Direction et Responsable du pôle Formation, si les modules obligatoires sont validés. -->
            <span v-if="page.can_force && !canPass" class="fiche-force" :title="forceHint">
              <label :class="{ 'is-disabled': !canForce }">
                <input v-model="force" type="checkbox" :disabled="busy || !canForce">
                Forcer
              </label>
            </span>
            <!-- Ce qui manque pour le passage, en info-bulle : sur le conteneur, car un bouton désactivé ne reçoit pas le survol. -->
            <span class="fiche-pass__hint" :title="blockers.join('\n')">
              <button
                type="button"
                class="formation-button formation-button--primary"
                :class="{ 'is-forced': force && !canPass }"
                :disabled="busy || !passEnabled"
                :aria-describedby="blockers.length ? 'fiche-pass-blockers' : undefined"
                @click="askPass(current)"
              >
                <Icon name="lucide:graduation-cap" size="14" />
                {{ current.stage === 'trial' ? `Passage ${current.next_grade_name ?? trainingLabel}` : `Fin de formation${current.next_grade_name ? ` · ${current.next_grade_name}` : ''}` }}
              </button>
              <span v-if="blockers.length" id="fiche-pass-blockers" class="fiche-sr-only">{{ blockers.join(' · ') }}</span>
            </span>
          </div>
        </header>

        <nav class="fiche-tabs" role="tablist" aria-label="Onglets de la fiche">
          <button
            v-for="tab in ficheTabs"
            :key="tab.key"
            type="button"
            role="tab"
            :aria-selected="ficheView === tab.key"
            :class="{ 'is-active': ficheView === tab.key }"
            @click="selectFicheTab(tab.key)"
          >
            <Icon :name="tab.icon" size="14" /> {{ tab.label }}
            <span v-if="tab.badge" class="formation-count">{{ tab.badge }}</span>
          </button>
        </nav>

        <p v-if="archived" class="fiche-archive">
          <Icon name="lucide:archive" size="14" />
          Archive de la période d’essai ({{ trialLabel }}), en lecture seule<template v-if="current.resident_at"> : passage {{ trainingLabel }} le {{ formatDate(current.resident_at) }}</template>.
        </p>

        <div v-if="ficheView === 'fiche'" class="fiche-top">
          <article class="fiche-box">
            <h4>Informations générales</h4>
            <dl class="fiche-info">
              <dt>Arrivée au BCES</dt>
              <dd><input type="date" :value="current.arrival_date ?? ''" :disabled="busy" aria-label="Date d’arrivée au BCES" @change="setArrival"></dd>
              <dt>Jours depuis l’arrivée</dt>
              <dd>{{ current.days ?? '—' }}</dd>
              <dt>Mentors</dt>
              <dd class="fiche-mentors">
                <span v-for="mentor in current.mentors" :key="mentor.id" class="fiche-chip">
                  {{ mentor.name }}
                  <button type="button" :aria-label="`Retirer ${mentor.name} des mentors`" :disabled="busy" @click="removeMentor(mentor.id)"><Icon name="lucide:x" size="11" /></button>
                </span>
                <select v-if="mentorOptions.length" value="" :disabled="busy" aria-label="Ajouter un mentor" @change="addMentor">
                  <option value="">+ Mentor…</option>
                  <option v-for="trainer in mentorOptions" :key="trainer.id" :value="trainer.id">{{ trainer.name }}</option>
                </select>
                <span v-else class="formation-muted">
                  {{ current.mentors.length ? 'Tous les formateurs sont déjà mentors.' : 'Aucun formateur.' }}
                  Un mentor doit avoir validé un pôle qui donne le droit Formateur (Pôles &amp; Spé).
                </span>
              </dd>
              <!--
                Barres et note de l'étape : seuil du passage sans forcer (repère sur la barre,
                valeur à droite, modifiable par ceux qui gèrent la formation). Ceux d'une étape
                passée ne s'affichent plus.
              -->
              <template v-for="barStage in infoStages" :key="barStage">
                <template v-if="barStage === 'training'">
                  <dt>Passage {{ trainingLabel }}</dt>
                  <dd>{{ formatDate(current.resident_at) }}</dd>
                </template>
                <template v-for="bar in BARS[barStage]" :key="bar.key">
                  <dt><strong v-if="bar.total">{{ bar.label }}</strong><template v-else>{{ bar.label }}</template></dt>
                  <dd class="fiche-progress">
                    <span class="formation-bar">
                      <span :style="{ width: barWidth(current.progress[bar.key]) }"></span>
                      <i v-if="goalOn(bar.key, barStage)" class="formation-bar__goal" :style="{ '--goal': page.thresholds[bar.key] }"></i>
                    </span>
                    <span class="fiche-progress__value" :class="{ 'is-ok': current.stage === barStage && reached(bar.key, current.progress[bar.key]), 'is-total': bar.total }">{{ percent(current.progress[bar.key]) }}</span>
                    <FormationGoal
                      v-if="current.stage === barStage"
                      :value="page.thresholds[bar.key]"
                      :max="100"
                      unit="%"
                      :label="bar.label"
                      :editable="page.can_manage"
                      :disabled="busy"
                      :save="(value: number) => saveThreshold(bar.key, value)"
                    />
                  </dd>
                </template>
                <template v-if="barStage === 'trial'">
                  <dt>Note du questionnaire</dt>
                  <dd>{{ score(current.questionnaire_score) }}</dd>
                  <dt>Note de la simulation {{ trialLabel }}</dt>
                  <dd>{{ score(current.simulation_score) }}</dd>
                  <dt><strong>Moyenne</strong></dt>
                  <dd class="fiche-note">
                    <strong :class="{ 'is-ok': current.stage === 'trial' && reached('average', current.average) }">{{ score(current.average) }}</strong>
                    <FormationGoal
                      v-if="current.stage === 'trial'"
                      :value="page.thresholds.average"
                      :max="20"
                      :step="0.5"
                      unit="/ 20"
                      label="Moyenne"
                      :editable="page.can_manage"
                      :disabled="busy"
                      :save="(value: number) => saveThreshold('average', value)"
                    />
                  </dd>
                </template>
                <template v-else>
                  <dt>Note de la simulation {{ trainingLabel }}</dt>
                  <dd class="fiche-note">
                    <strong :class="{ 'is-ok': reached('resident_simulation', current.resident_simulation_score) }">{{ score(current.resident_simulation_score) }}</strong>
                    <FormationGoal
                      :value="page.thresholds.resident_simulation"
                      :max="20"
                      :step="0.5"
                      unit="/ 20"
                      :label="`Simulation ${trainingLabel}`"
                      :editable="page.can_manage"
                      :disabled="busy"
                      :save="(value: number) => saveThreshold('resident_simulation', value)"
                    />
                  </dd>
                </template>
              </template>
            </dl>
          </article>

          <article class="fiche-box fiche-notes">
            <h4>Notes</h4>
            <textarea v-model="notesDraft" maxlength="4000" placeholder="Observations des formateurs…" :disabled="busy" @blur="saveNotes"></textarea>
          </article>
        </div>

        <template v-if="ficheView !== 'questionnaire'">
        <h4 class="fiche-title">Validation grade {{ viewStage === 'trial' ? trialLabel : trainingLabel }}</h4>
        <p class="fiche-legend">
          <span v-for="level in LEVELS[viewStage]" :key="level.value">{{ level.icon }} {{ level.label }}</span>
          <span><span class="fiche-required" aria-hidden="true">*</span> Obligatoire pour le passage, même forcé</span>
        </p>

        <div class="fiche-modules" :class="[`is-${viewStage}`, { 'is-archived': archived }]">
          <article v-for="category in CATEGORIES[viewStage]" :key="category.key" class="fiche-box">
            <h4>
              {{ category.label }}
              <span class="fiche-box__percent">{{ percent(current.progress[category.key]) }}</span>
              <button v-if="page.can_manage && !archived" type="button" class="fiche-icon" :aria-label="`Ajouter à ${category.label}`" title="Ajouter" @click="openModule(category.key)"><Icon name="lucide:plus" size="13" /></button>
            </h4>
            <p v-if="!modulesOf(category.key).length" class="formation-muted">Aucun module.</p>
            <ul class="fiche-rows">
              <li v-for="module in modulesOf(category.key)" :key="module.id">
                <span class="fiche-rows__name">
                  <span v-if="module.emoji" class="fiche-rows__emoji" title="Emoji ajouté aux compétences au niveau le plus haut">{{ module.emoji }}</span>
                  <span class="fiche-rows__label" :title="module.name">{{ module.name }}</span>
                  <span v-if="module.is_required" class="fiche-required" title="Obligatoire pour le passage, même forcé">*<span class="fiche-sr-only"> (obligatoire)</span></span>
                  <span v-if="page.can_manage && !archived" class="fiche-actions">
                    <button type="button" :aria-label="`Modifier ${module.name}`" title="Modifier" @click="openModule(category.key, module)"><Icon name="lucide:pencil" size="11" /></button>
                    <button type="button" class="is-danger" :aria-label="`Supprimer ${module.name}`" title="Supprimer" @click="askDeleteModule(module)"><Icon name="lucide:trash-2" size="11" /></button>
                  </span>
                </span>
                <span
                  class="fiche-level-control"
                  :class="`is-${toneOf(levelOf(current, module))}`"
                  :data-icon="LEVELS[viewStage].find((level) => level.value === levelOf(current, module))?.icon ?? '—'"
                >
                  <Icon class="fiche-level-chevron" name="lucide:chevron-down" size="11" aria-hidden="true" />
                  <select
                    class="fiche-level"
                    :value="levelOf(current, module)"
                    :disabled="busy || archived"
                    :title="levelLabel(levelOf(current, module))"
                    :aria-label="`Niveau de ${current.name} sur ${module.name}`"
                    @change="setLevel(module, $event)"
                  >
                    <option v-for="level in LEVELS[viewStage]" :key="level.value" :value="level.value" :title="level.label">{{ level.icon }} {{ level.short }}</option>
                  </select>
                </span>
              </li>
            </ul>
          </article>

          <article class="fiche-box">
            <h4>Simulation validante <span class="fiche-box__percent">{{ score(simulationScore) }}</span></h4>
            <p class="formation-muted">De 1 (pas réalisé) à 5 (très bien).</p>
            <ul class="fiche-rows">
              <li v-for="criterion in simulationCriteria" :key="criterion.key">
                <span class="fiche-rows__name"><span class="fiche-rows__label" :title="criterion.label">{{ criterion.label }}</span></span>
                <select class="fiche-score" :value="current[simulationField][criterion.key] ?? 0" :disabled="busy || archived" :aria-label="criterion.label" @change="setSimulation(criterion.key, $event)">
                  <option :value="0">—</option>
                  <option v-for="value in 5" :key="value" :value="value">{{ value }}</option>
                </select>
              </li>
            </ul>
          </article>
        </div>
        </template>

        <article v-else class="fiche-box">
          <h4>
            Questionnaire de passage {{ trainingLabel }}
            <span class="fiche-box__percent">{{ current.answers.length }} / {{ page.questions.length }} · {{ score(current.questionnaire_score) }}</span>
            <button v-if="page.can_manage && !archived" type="button" class="fiche-icon" aria-label="Ajouter une question" title="Ajouter une question" @click="openQuestion()"><Icon name="lucide:plus" size="13" /></button>
          </h4>
          <p v-if="!archived" class="formation-muted">L’objectif n’est pas une réponse parfaite : s’il essaie mais qu’il manque des informations, on coche quand même la bonne réponse.</p>
          <p v-if="!page.questions.length" class="formation-muted">Aucune question.</p>
          <ol class="fiche-questions" :class="{ 'is-archived': archived }">
            <li v-for="question in page.questions" :key="question.id">
              <label>
                <input type="checkbox" :checked="current.answers.includes(question.id)" :disabled="busy || archived" @change="setAnswer(question, $event)">
                <span>
                  <strong>{{ question.question }}</strong>
                  <small v-if="question.answer">{{ question.answer }}</small>
                </span>
              </label>
              <span v-if="page.can_manage && !archived" class="fiche-actions">
                <button type="button" aria-label="Modifier la question" title="Modifier" @click="openQuestion(question)"><Icon name="lucide:pencil" size="11" /></button>
                <button type="button" class="is-danger" aria-label="Supprimer la question" title="Supprimer" @click="askDeleteQuestion(question)"><Icon name="lucide:trash-2" size="11" /></button>
              </span>
            </li>
          </ol>
        </article>

        <!-- Retour à la période d'essai, tout en bas de la fiche. -->
        <footer v-if="current.stage === 'training'" class="fiche-revert">
          <p>
            Annuler le passage {{ trainingLabel }} : {{ current.name }} reprend son grade {{ trialLabel }}<template v-if="current.resident_at"> (passage du {{ formatDate(current.resident_at) }})</template>.
            Les emojis de ses modules de période d’essai en autonomie reviennent, ceux de ses formations partent.
          </p>
          <button type="button" class="formation-button formation-button--danger" :disabled="busy" @click="askCancelPass(current)">
            <Icon name="lucide:undo-2" size="14" /> Annuler le passage {{ trainingLabel }}
          </button>
        </footer>
      </section>
    </div>

    <dialog ref="moduleDialog" class="formation-dialog" aria-labelledby="module-dialog-title" @cancel.prevent="!saving && moduleDialog?.close()">
      <form @submit.prevent="saveModule">
        <header class="formation-dialog__head">
          <div>
            <h2 id="module-dialog-title">{{ moduleForm.id ? 'Modifier' : 'Ajouter' }}</h2>
            <p>{{ moduleCategoryLabel }}</p>
          </div>
          <button type="button" class="formation-dialog__close" aria-label="Fermer" :disabled="saving" @click="moduleDialog?.close()"><Icon name="lucide:x" size="16" /></button>
        </header>
        <div class="formation-form">
          <EmojiField v-model="moduleForm.emoji" label="Emoji (facultatif)" :maxlength="16" clearable />
          <label>
            <span>Nom</span>
            <input v-model="moduleForm.name" name="name" required maxlength="64" placeholder="Ex. DDS">
          </label>
          <label class="formation-check">
            <input v-model="moduleForm.is_required" type="checkbox">
            <span>
              <strong>Obligatoire</strong>
              <small>À valider au niveau le plus haut pour le passage, même forcé.</small>
            </span>
          </label>
          <p class="formation-muted">
            Avec un emoji, il rejoint les compétences de l’employé au niveau le plus haut.
          </p>
        </div>
        <footer class="formation-dialog__foot">
          <button type="button" class="formation-button" :disabled="saving" @click="moduleDialog?.close()">Annuler</button>
          <button v-if="moduleForm.emoji" type="button" class="formation-button formation-button--danger" :disabled="saving || !moduleForm.name.trim()" @click="removeModuleEmoji">
            <Icon name="lucide:x" size="13" /> Retirer l’emoji {{ moduleForm.emoji }}
          </button>
          <button type="submit" class="formation-button formation-button--primary" :disabled="saving || !moduleForm.name.trim()">
            {{ saving ? 'Enregistrement…' : moduleForm.id ? 'Enregistrer' : 'Ajouter' }}
          </button>
        </footer>
      </form>
    </dialog>

    <dialog ref="questionDialog" class="formation-dialog" aria-labelledby="question-dialog-title" @cancel.prevent="!saving && questionDialog?.close()">
      <form @submit.prevent="saveQuestion">
        <header class="formation-dialog__head">
          <h2 id="question-dialog-title">{{ questionForm.id ? 'Modifier la question' : 'Ajouter une question' }}</h2>
          <button type="button" class="formation-dialog__close" aria-label="Fermer" :disabled="saving" @click="questionDialog?.close()"><Icon name="lucide:x" size="16" /></button>
        </header>
        <div class="formation-form formation-form--single">
          <label>
            <span>Question</span>
            <textarea v-model="questionForm.question" required maxlength="500" rows="3"></textarea>
          </label>
          <label>
            <span>Réponse attendue</span>
            <textarea v-model="questionForm.answer" maxlength="1000" rows="3"></textarea>
          </label>
        </div>
        <footer class="formation-dialog__foot">
          <button type="button" class="formation-button" :disabled="saving" @click="questionDialog?.close()">Annuler</button>
          <button type="submit" class="formation-button formation-button--primary" :disabled="saving || !questionForm.question.trim()">
            {{ saving ? 'Enregistrement…' : questionForm.id ? 'Enregistrer' : 'Ajouter la question' }}
          </button>
        </footer>
      </form>
    </dialog>

    <ConfirmDialog
      v-model:visible="transitionVisible"
      :title="transition?.title ?? 'Changement de grade'"
      :message="transition?.message ?? ''"
      :confirm-label="transition?.label ?? 'Confirmer'"
      :danger="transition?.danger ?? false"
      @confirm="runTransition"
      @cancel="transition = null"
    />
    <ConfirmDialog
      v-model:visible="deleteVisible"
      :title="deleting?.title ?? 'Supprimer ?'"
      :message="deleting?.message ?? ''"
      confirm-label="Supprimer"
      danger
      @confirm="confirmDelete"
      @cancel="deleting = null"
    />
  </div>
</template>

<style scoped>
.formation { display: grid; gap: 14px; min-width: 0; }
.formation-tabs { display: flex; gap: 6px; padding: 7px; overflow-x: auto; border: 1px solid var(--dp-line); border-radius: 14px; background: var(--dp-panel); }
.formation-tabs button { display: inline-flex; min-height: 42px; align-items: center; gap: 8px; padding: 0 14px; border: 1px solid transparent; border-radius: 9px; color: var(--dp-text-2); background: transparent; font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; white-space: nowrap; }
.formation-tabs button:hover { color: var(--dp-text); background: var(--dp-panel-2); }
.formation-tabs button.is-active { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.formation-error { display: flex; align-items: center; gap: 8px; margin: 0; padding: 12px 14px; border: 1px solid var(--dp-danger-line); border-radius: 12px; color: var(--dp-danger); background: var(--dp-danger-soft); font-size: 12px; }
.formation-empty { display: grid; min-height: 160px; place-items: center; color: var(--dp-text-dim); }
.formation-spin { animation: formation-spin 1s linear infinite; }
@keyframes formation-spin { to { transform: rotate(360deg); } }
.formation-muted { margin: 0; color: var(--dp-text-dim); font-size: 11px; }
.formation-count { padding: 0 7px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-dim); font-size: 10px; }
.formation-link { padding: 0; border: 0; color: var(--dp-accent); background: none; font: inherit; font-size: 10px; text-decoration: underline; cursor: pointer; }
.formation-button { display: inline-flex; min-height: 34px; align-items: center; gap: 7px; padding: 0 13px; border: 1px solid var(--dp-line-strong); border-radius: 9px; color: var(--dp-text); background: var(--dp-panel-2); font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; }
.formation-button:disabled { opacity: .5; cursor: not-allowed; }
.formation-button--primary { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }

.formation-body { display: grid; grid-template-columns: minmax(220px, 260px) minmax(0, 1fr); align-items: start; gap: 14px; min-width: 0; }

/* Liste des employés de l'onglet */
.formation-list { display: grid; gap: 6px; }
.formation-item { display: grid; gap: 6px; padding: 10px 11px; border: 1px solid var(--dp-line); border-radius: 11px; color: var(--dp-text); background: var(--dp-panel-2); font: inherit; text-align: left; cursor: pointer; }
.formation-item:hover { border-color: var(--dp-line-strong); }
.formation-item.is-selected { border-color: var(--dp-accent-line); background: var(--dp-accent-soft); }
.formation-item__top { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; font-size: 12px; }
.formation-item__days { color: var(--dp-text-dim); font-size: 10px; font-variant-numeric: tabular-nums; }
.formation-bar { position: relative; display: block; height: 5px; overflow: hidden; border-radius: 999px; background: var(--dp-line); }
.formation-bar > span { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background: var(--dp-accent); }
/* Repère du seuil de passage : décalé de sa propre largeur à 100 % pour rester dans la barre. */
.formation-bar__goal { position: absolute; top: 0; bottom: 0; left: calc(var(--goal) * 1%); width: 2px; background: var(--dp-text); opacity: .6; transform: translateX(calc(var(--goal) * -1%)); }
.formation-tone { justify-self: start; padding: 2px 8px; border: 1px solid var(--dp-line); border-radius: 999px; color: var(--dp-text-2); font-size: 10px; font-weight: 600; }
.formation-tone.is-done, .formation-tone.is-ready { border-color: var(--dp-accent-line); color: var(--dp-accent); background: var(--dp-accent-soft); }
.formation-tone.is-warning { border-color: color-mix(in srgb, var(--dp-warn) 55%, transparent); color: var(--dp-warn); background: var(--dp-warn-soft); }
.formation-tone.is-urgent { border-color: var(--dp-danger-line); color: var(--dp-danger); background: var(--dp-danger-soft); }
.formation-completed { margin-top: 6px; padding-top: 8px; border-top: 1px solid var(--dp-line); }
.formation-completed__toggle { display: flex; align-items: center; gap: 6px; padding: 0; border: 0; color: var(--dp-text-2); background: none; font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; }
.formation-completed__toggle .is-closed { transform: rotate(-90deg); }
.formation-completed ul { display: grid; gap: 6px; margin: 8px 0 0; padding: 0; list-style: none; }
.formation-completed li { display: grid; gap: 3px; color: var(--dp-text-2); font-size: 11px; }
.formation-completed li .formation-link { justify-self: start; }

/* Fiche */
.fiche { display: grid; gap: 12px; min-width: 0; }
/* Nom, grade et statut centrés verticalement sur les boutons de passage. */
.fiche-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
.fiche-head__name { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.fiche-head h3 { margin: 0; font-size: 17px; line-height: 1.2; }
.fiche-grade { padding: 2px 8px; border: 1px solid color-mix(in srgb, var(--grade-color) 55%, transparent); border-radius: 999px; color: var(--dp-text-2); background: color-mix(in srgb, var(--grade-color) 14%, transparent); font-size: 10px; font-weight: 600; }
.fiche-pass { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 6px; }
.fiche-pass__hint { display: inline-flex; }
.fiche-pass__hint .formation-button:disabled { pointer-events: none; }
.fiche-pass__hint .formation-button.is-forced { border-color: color-mix(in srgb, var(--dp-warn) 55%, transparent); color: var(--dp-warn); background: var(--dp-warn-soft); }
.fiche-force { display: inline-flex; }
.fiche-revert { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-top: 4px; padding: 12px; border: 1px solid var(--dp-danger-line); border-radius: 12px; background: color-mix(in srgb, var(--dp-danger-soft) 50%, transparent); }
.fiche-revert p { flex: 1; min-width: 240px; margin: 0; color: var(--dp-text-2); font-size: 11px; }
.formation-button--danger { border-color: var(--dp-danger-line); color: var(--dp-danger); background: var(--dp-danger-soft); }
.fiche-force label { display: inline-flex; align-items: center; gap: 6px; padding: 0 10px; min-height: 34px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text-2); font-size: 11px; font-weight: 650; cursor: pointer; }
.fiche-force label.is-disabled { opacity: .5; cursor: not-allowed; }
.fiche-force input { width: 14px; height: 14px; margin: 0; accent-color: var(--dp-warn); }
.fiche-sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
/* Onglets de la fiche : fiche de formation, questionnaire. */
.fiche-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--dp-line); }
.fiche-tabs button { display: inline-flex; align-items: center; gap: 7px; margin-bottom: -1px; padding: 8px 12px; border: 0; border-bottom: 2px solid transparent; color: var(--dp-text-2); background: transparent; font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; }
.fiche-tabs button:hover { color: var(--dp-text); }
.fiche-tabs button.is-active { border-bottom-color: var(--dp-accent); color: var(--dp-accent); }
.fiche-archive { display: flex; align-items: center; gap: 8px; margin: 0; padding: 8px 12px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-2); background: var(--dp-panel-2); font-size: 11px; }
/* Archive : les valeurs restent lisibles, sans l'aspect grisé d'un champ désactivé. */
.fiche-modules.is-archived select:disabled { opacity: 1; color: var(--dp-text); cursor: default; }
.fiche-questions.is-archived label { cursor: default; }
.fiche-questions.is-archived input:disabled { opacity: 1; }
.fiche-title { margin: 4px 0 0; color: var(--dp-text); font-size: 13px; }
.fiche-box { display: grid; align-content: start; gap: 8px; min-width: 0; padding: 12px; border: 1px solid var(--dp-line); border-radius: 12px; background: var(--dp-panel-2); }
.fiche-box h4 { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--dp-text); font-size: 12px; }
.fiche-box__percent { margin-left: auto; color: var(--dp-text-2); font-size: 11px; font-weight: 650; font-variant-numeric: tabular-nums; }
.fiche-icon { display: grid; width: 24px; height: 24px; place-items: center; border: 1px solid var(--dp-line); border-radius: 7px; color: var(--dp-text-2); background: var(--dp-bg); cursor: pointer; }
.fiche-icon:hover { color: var(--dp-accent); border-color: var(--dp-accent-line); }
.fiche-top { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 12px; }
.fiche-info { --formation-goal-width: 116px; display: grid; grid-template-columns: minmax(130px, auto) minmax(0, 1fr); align-items: center; gap: 7px 12px; margin: 0; font-size: 11px; }
.fiche-info dt { color: var(--dp-text-2); }
.fiche-info dd { margin: 0; color: var(--dp-text); font-variant-numeric: tabular-nums; }
.fiche-info .is-ok { color: var(--dp-accent); }
.fiche-info input[type='date'], .fiche-mentors select, .fiche-level, .fiche-score { min-height: 28px; padding: 0 8px; border: 1px solid var(--dp-line); border-radius: 7px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 11px; }
.fiche-mentors { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }
.fiche-chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 4px 2px 9px; border: 1px solid var(--dp-accent-line); border-radius: 999px; color: var(--dp-accent); background: var(--dp-accent-soft); font-size: 10px; font-weight: 650; }
.fiche-chip button { display: grid; width: 18px; height: 18px; place-items: center; padding: 0; border: 0; border-radius: 50%; color: inherit; background: transparent; cursor: pointer; }
.fiche-chip button:hover { background: var(--dp-panel); }
/* Barre, pourcentage, seuil : la colonne du seuil reste réservée (même vide) pour aligner les barres. */
.fiche-progress { display: grid; grid-template-columns: minmax(0, 1fr) 42px var(--formation-goal-width); align-items: center; gap: 8px; text-align: right; }
.fiche-progress__value.is-total { font-weight: 700; }
.fiche-note { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.fiche-notes textarea { min-height: 160px; height: 100%; box-sizing: border-box; resize: vertical; padding: 9px 10px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.fiche-legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 18px; margin: 0; padding: 8px; border: 1px solid var(--dp-line); border-radius: 10px; color: var(--dp-text-2); font-size: 11px; }
/* Une seule rangée : les blocs de l'étape et la simulation côte à côte (sur écran étroit, ils passent à la ligne). */
.fiche-modules { display: grid; grid-template-columns: repeat(var(--fiche-columns, 3), minmax(0, 1fr)); align-items: start; gap: 12px; }
.fiche-modules.is-trial { --fiche-columns: 5; }
.fiche-modules.is-training { --fiche-columns: 3; }
.fiche-rows { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
.fiche-rows li { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px; min-height: 30px; font-size: 11px; }
/*
 * Nom sur deux lignes au plus ; au-delà, il finit par « … » et s'affiche en
 * entier au survol. Un mot trop long se coupe au lieu de passer sous la liste.
 */
.fiche-rows__name { position: relative; display: flex; align-items: center; gap: 5px; min-width: 0; color: var(--dp-text); font-weight: 600; }
.fiche-rows__label { display: -webkit-box; min-width: 0; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow-wrap: anywhere; hyphens: auto; line-height: 1.3; }
/*
 * Modifier / supprimer un module : par-dessus la fin du nom, au survol. Hors du
 * flux, sinon ils passent à la ligne sous le nom et décalent la liste du niveau.
 */
.fiche-rows__name .fiche-actions { position: absolute; top: 50%; right: 0; padding: 1px; border-radius: 6px; background: var(--dp-panel-2); transform: translateY(-50%); }
.fiche-rows__emoji { flex-shrink: 0; font-size: 13px; }
.fiche-required { position: relative; flex-shrink: 0; color: var(--dp-danger); font-weight: 700; }
.fiche-level-control { position: relative; display: inline-flex; width: 42px; height: 28px; flex: 0 0 42px; }
.fiche-level-control::before { position: absolute; z-index: 1; top: 50%; left: 5px; content: attr(data-icon); pointer-events: none; transform: translateY(-50%); }
.fiche-level-chevron { position: absolute; z-index: 1; top: 50%; right: 4px; color: var(--dp-text-2); pointer-events: none; transform: translateY(-50%); }
.fiche-level { width: 100%; padding: 0 15px 0 3px; color: transparent; appearance: none; font-weight: 600; }
.fiche-level-control.is-none .fiche-level { border: 1px solid #ff8585; background: rgba(217, 83, 79, .18); }
.fiche-level-control.is-seen .fiche-level { border: 1px solid #83c7ff; background: rgba(61, 127, 184, .2); }
.fiche-level-control.is-practiced .fiche-level { border: 1px solid #ffd166; background: rgba(201, 138, 46, .2); }
.fiche-level-control.is-done .fiche-level { border: 1px solid #79e3a5; background: rgba(70, 153, 109, .2); }
.fiche-level:focus-visible { outline: 2px solid var(--dp-text); outline-offset: 2px; }
.fiche-modules.is-archived .fiche-level-control .fiche-level:disabled { color: transparent; }
.fiche-level option, .fiche-score option { color: var(--dp-text); background: var(--dp-bg); }
.fiche-score { width: 64px; text-align: center; }
/* Modifier / supprimer un module ou une question : au survol de la ligne. */
.fiche-actions { display: inline-flex; gap: 2px; opacity: 0; transition: opacity .15s; }
.fiche-rows li:hover .fiche-actions, .fiche-rows li:focus-within .fiche-actions,
.fiche-questions li:hover .fiche-actions, .fiche-questions li:focus-within .fiche-actions { opacity: 1; }
.fiche-actions button { display: grid; width: 20px; height: 20px; place-items: center; padding: 0; border: 0; border-radius: 5px; color: var(--dp-text-dim); background: transparent; cursor: pointer; }
.fiche-actions button:hover { color: var(--dp-text); background: var(--dp-panel); }
.fiche-actions button.is-danger:hover { color: var(--dp-danger); background: var(--dp-danger-soft); }
.fiche-questions { display: grid; gap: 6px; margin: 0; padding-left: 22px; font-size: 11px; }
.fiche-questions li { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 6px; }
.fiche-questions label { display: flex; align-items: flex-start; gap: 8px; cursor: pointer; }
.fiche-questions input { flex-shrink: 0; width: 15px; height: 15px; margin: 1px 0 0; accent-color: var(--dp-accent); }
.fiche-questions label span { display: grid; gap: 2px; }
.fiche-questions strong { color: var(--dp-text); font-weight: 600; }
.fiche-questions small { color: var(--dp-text-dim); font-size: 10px; }

/* Fenêtres */
.formation-dialog { position: fixed; inset: 50% auto auto 50%; width: min(520px, calc(100vw - 24px)); max-height: 90dvh; margin: 0; overflow: auto; transform: translate(-50%, -50%); padding: 0; border: 1px solid var(--dp-line-strong); border-radius: 16px; color: var(--dp-text); background: var(--dp-panel); box-shadow: 0 24px 80px rgba(0, 0, 0, .55); }
.formation-dialog::backdrop { background: rgba(0, 0, 0, .55); }
.formation-dialog__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 18px; border-bottom: 1px solid var(--dp-line); }
.formation-dialog__head h2 { margin: 0; font-size: 15px; }
.formation-dialog__head p { margin: 3px 0 0; color: var(--dp-text-dim); font-size: 11px; }
.formation-dialog__close { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text-2); background: transparent; cursor: pointer; }
/* « dense » : le nom reste à côté de l'emoji quand le menu des emojis s'ouvre en dessous. */
.formation-form { display: grid; grid-template-columns: 80px minmax(0, 1fr); grid-auto-flow: row dense; gap: 12px; padding: 16px 18px; }
.formation-form--single { grid-template-columns: minmax(0, 1fr); }
.formation-form > label { display: grid; gap: 5px; color: var(--dp-text-2); font-size: 10px; }
.formation-form input:not([type='checkbox']), .formation-form textarea { width: 100%; min-height: 36px; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.formation-form textarea { resize: vertical; }
.formation-form > .formation-muted { grid-column: 1 / -1; }
.formation-form > label.formation-check { display: flex; grid-column: 1 / -1; align-items: flex-start; gap: 9px; color: var(--dp-text); font-size: 11px; cursor: pointer; }
.formation-check input { flex-shrink: 0; width: 15px; height: 15px; margin: 1px 0 0; accent-color: var(--dp-accent); }
.formation-check span { display: grid; gap: 2px; }
.formation-check small { color: var(--dp-text-dim); font-size: 10px; }
.formation-dialog__foot { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 18px; border-top: 1px solid var(--dp-line); }

/* Écran étroit : les blocs passent à la ligne plutôt que d'écraser les noms. */
@media (max-width: 1200px) {
  .fiche-modules { grid-template-columns: repeat(auto-fit, minmax(min(250px, 100%), 1fr)); }
}

@media (max-width: 900px) {
  .formation-body, .fiche-top { grid-template-columns: minmax(0, 1fr); }
  .fiche-pass { justify-content: flex-start; }
}
</style>
