<script setup lang="ts">
useHead({ title: 'Active ton compte' })

const config = useRuntimeConfig()
const route = useRoute()
const toast = useAppToast()
const { formatDate, formatTime, formatTzLabel, tz } = useTimezone()

type Me = {
  id: number
  discord_id: string
  discord_username: string
  discord_avatar: string | null
  prenom_rp: string | null
  nom_rp: string | null
  rp_name_deadline: string | null
  created_at: string
}

const STORAGE_KEY = 'bces:profile-draft'

const deadlineParam = computed<string | null>(() => {
  const value = route.query.deadline
  return typeof value === 'string' ? value : null
})

const { data: meData } = await useAsyncData<Me | null>('me-profile', async () => {
  try {
    const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
    return await $fetch<Me>(`${config.public.apiBase}/api/me`, {
      credentials: 'include',
      headers
    })
  } catch {
    return null
  }
})

if (!meData.value) {
  toast.error('Tu dois être connecté pour accéder à cette page.')
  await navigateTo('/')
}

if (meData.value?.prenom_rp && meData.value?.nom_rp) {
  await navigateTo('/dashboard')
}

const prenom = ref<string>('')
const nom = ref<string>('')
const phone = ref<string>('')
const error = ref<string | null>(null)
const loading = ref<boolean>(false)
const expired = ref<boolean>(false)
const now = ref<number>(Date.now())

const deadlineTimestamp = computed<number | null>(() => {
  if (meData.value?.rp_name_deadline) {
    const t = new Date(meData.value.rp_name_deadline).getTime()
    if (!Number.isNaN(t)) return t
  }
  if (deadlineParam.value) {
    const t = new Date(deadlineParam.value).getTime()
    if (!Number.isNaN(t)) return t
  }
  return null
})

const totalWindowMs = 24 * 60 * 60 * 1000
const startTimestamp = computed<number>(() => {
  const end = deadlineTimestamp.value
  if (!end) return now.value
  return end - totalWindowMs
})

const remainingMs = computed<number>(() => {
  const end = deadlineTimestamp.value
  if (!end) return totalWindowMs
  return Math.max(0, end - now.value)
})

const progressPercent = computed<number>(() => {
  const end = deadlineTimestamp.value
  if (!end) return 0
  const start = startTimestamp.value
  if (end <= start) return 100
  return Math.min(100, Math.max(0, ((now.value - start) / (end - start)) * 100))
})

type Urgency = 'safe' | 'soon' | 'warning' | 'critical' | 'expired'

const urgency = computed<Urgency>(() => {
  const ms = remainingMs.value
  if (ms <= 0) return 'expired'
  if (ms < 60 * 60 * 1000) return 'critical'
  if (ms < 3 * 60 * 60 * 1000) return 'warning'
  if (ms < 12 * 60 * 60 * 1000) return 'soon'
  return 'safe'
})

const countdownDisplay = computed<string>(() => {
  let ms = remainingMs.value
  if (ms <= 0) return '00:00:00'
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
})

const countdownLabel = computed<string>(() => {
  const ms = remainingMs.value
  if (ms <= 0) return 'Délai dépassé'
  const totalMinutes = Math.floor(ms / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${minutes} min restantes`
  if (minutes === 0) return `${hours} h restantes`
  return `${hours} h ${minutes} min restantes`
})

const deadlineDisplay = computed<{ date: string; time: string } | null>(() => {
  const end = deadlineTimestamp.value
  if (!end) return null
  const date = new Date(end)
  const d = formatDate(date)
  const t = formatTime(date)
  if (!d || !t) return null
  return { date: d, time: t }
})

const timezoneLabel = computed<string>(() => formatTzLabel(new Date(deadlineTimestamp.value ?? Date.now())))

const discordAvatarUrl = computed<string | null>(() => {
  const me = meData.value
  if (!me?.discord_avatar) return null
  return `https://cdn.discordapp.com/avatars/${me.discord_id}/${me.discord_avatar}.png?size=80`
})

const NAME_PATTERN = /^[A-Za-zÀ-ÖØ-öø-ÿ' \-]+$/

function validateField(value: string): { ok: boolean; message: string | null } {
  const trimmed = value.trim()
  if (trimmed.length === 0) return { ok: false, message: null }
  if (trimmed.length < 2) return { ok: false, message: '2 caractères minimum.' }
  if (trimmed.length > 80) return { ok: false, message: '80 caractères maximum.' }
  if (!NAME_PATTERN.test(trimmed)) {
    return { ok: false, message: 'Lettres, espaces, tirets, apostrophes uniquement.' }
  }
  return { ok: true, message: null }
}

const prenomState = computed(() => validateField(prenom.value))
const nomState = computed(() => validateField(nom.value))

const phoneState = computed(() => {
  const t = phone.value.trim()
  if (t === '') return { ok: true, message: null as string | null }
  if (t.length < 6) return { ok: false, message: '6 chiffres minimum.' }
  if (!/^[\d\-\+\(\) ]{6,20}$/.test(t)) return { ok: false, message: 'Caractères invalides.' }
  return { ok: true, message: null as string | null }
})

const canSubmit = computed<boolean>(
  () =>
    prenomState.value.ok &&
    nomState.value.ok &&
    phoneState.value.ok &&
    !loading.value &&
    !expired.value
)

function loadDraft() {
  if (typeof window === 'undefined') return
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const data = JSON.parse(raw) as { prenom?: string; nom?: string; phone?: string }
    if (typeof data.prenom === 'string' && !prenom.value) prenom.value = data.prenom
    if (typeof data.nom === 'string' && !nom.value) nom.value = data.nom
    if (typeof data.phone === 'string' && !phone.value) phone.value = data.phone
  } catch {
    /* ignore */
  }
}

function saveDraft() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ prenom: prenom.value, nom: nom.value, phone: phone.value })
    )
  } catch {
    /* ignore */
  }
}

function clearDraft() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

async function logout() {
  try {
    await $fetch(`${config.public.apiBase}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    })
  } finally {
    clearDraft()
    await navigateTo('/')
  }
}

async function submit() {
  if (!canSubmit.value) return
  error.value = null
  loading.value = true
  try {
    const result = await $fetch<{ status?: string }>(`${config.public.apiBase}/api/auth/profile`, {
      method: 'POST',
      body: {
        prenomRP: prenom.value.trim(),
        nomRP: nom.value.trim(),
        phone: phone.value.trim()
      },
      credentials: 'include'
    })
    clearDraft()
    if (result.status === 'pending') {
      toast.warning('Profil envoyé. Ton compte est en attente de validation.')
      await navigateTo('/?status=pending')
      return
    }
    toast.success('Compte activé. Bienvenue !')
    await navigateTo('/dashboard')
  } catch (e: unknown) {
    const fetchError = e as { data?: { detail?: string | string[] }; statusMessage?: string }
    const detail = fetchError.data?.detail
    const message =
      (Array.isArray(detail) ? detail.join(' ') : detail) ||
      fetchError.statusMessage ||
      "Impossible d'enregistrer le profil."
    error.value = message
    toast.error(message)
  } finally {
    loading.value = false
  }
}

let intervalId: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadDraft()
  intervalId = setInterval(() => {
    now.value = Date.now()
    if (deadlineTimestamp.value && remainingMs.value <= 0 && !expired.value) {
      expired.value = true
      const message = 'Délai dépassé. Ton compte va être supprimé, reconnecte-toi pour recommencer.'
      error.value = message
      toast.error(message, { duration: 0 })
    }
  }, 1000)
})

watch([prenom, nom, phone], () => saveDraft())

onBeforeUnmount(() => {
  if (intervalId !== null) clearInterval(intervalId)
})
</script>

<template>
  <main class="bces-card bces-card--wide">
    <div class="bces-card__brand">
      <img src="/images/logo.png" alt="BCES" />
      <span class="bces-card__brand-name">BCES Dispatch</span>
    </div>

    <template v-if="meData">
      <h1 class="bces-card__title">Active ton compte</h1>
      <p class="bces-card__subtitle">
        Renseigne ton identité pour finaliser la création de ton compte.
      </p>

      <div class="bces-identity">
        <img
          v-if="discordAvatarUrl"
          :src="discordAvatarUrl"
          :alt="meData.discord_username"
          class="bces-identity__avatar"
          width="44"
          height="44"
        />
        <div v-else class="bces-identity__avatar bces-identity__avatar--placeholder" aria-hidden="true">
          {{ meData.discord_username.charAt(0).toUpperCase() }}
        </div>
        <div class="bces-identity__meta">
          <span class="bces-identity__label">Connecté avec Discord</span>
          <span class="bces-identity__name">{{ meData.discord_username }}</span>
        </div>
        <button type="button" class="bces-identity__logout" @click="logout">
          Déconnexion
        </button>
      </div>

      <div class="bces-countdown" :data-urgency="urgency">
        <div class="bces-countdown__row">
          <span class="bces-countdown__label">
            {{ expired ? 'Temps écoulé' : 'Temps restant' }}
          </span>
          <span class="bces-countdown__timer" aria-live="polite">
            {{ expired ? 'Expiré' : countdownDisplay }}
          </span>
        </div>
        <div
          class="bces-countdown__bar"
          role="progressbar"
          :aria-valuenow="Math.round(progressPercent)"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <div
            class="bces-countdown__bar-fill"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>
<p class="bces-countdown__hint">
          <template v-if="expired">
            Ton compte n'a pas été activé à temps. Reconnecte-toi via Discord pour
            relancer la procédure.
          </template>
          <template v-else>
            <strong>{{ countdownLabel }}</strong>
            <template v-if="deadlineDisplay">
              — délai fixé au {{ deadlineDisplay.date }} à {{ deadlineDisplay.time }}.
            </template>
            <template v-else>
              . Passé ce délai, le compte est automatiquement supprimé.
            </template>
          </template>
        </p>

        <div class="bces-countdown__tz" role="status">
          Heure affichée selon&nbsp;: <strong>{{ timezoneLabel }}</strong>
        </div>
      </div>

      <form class="bces-form" @submit.prevent="submit">
        <div class="bces-grid-2">
          <div class="bces-field">
            <label for="prenom" class="bces-field__label">Prénom</label>
            <input
              id="prenom"
              v-model="prenom"
              type="text"
              class="bces-input"
              :class="{
                'bces-input--ok': prenomState.ok,
                'bces-input--err': prenomState.message !== null
              }"
              placeholder="ex. Jean"
              autocomplete="given-name"
              :disabled="expired"
              required
            />
            <p
              v-if="prenomState.message"
              class="bces-field__hint bces-field__hint--err"
            >
              {{ prenomState.message }}
            </p>
          </div>

          <div class="bces-field">
            <label for="nom" class="bces-field__label">Nom</label>
            <input
              id="nom"
              v-model="nom"
              type="text"
              class="bces-input"
              :class="{
                'bces-input--ok': nomState.ok,
                'bces-input--err': nomState.message !== null
              }"
              placeholder="ex. Dupont"
              autocomplete="family-name"
              :disabled="expired"
              required
            />
            <p
              v-if="nomState.message"
              class="bces-field__hint bces-field__hint--err"
            >
              {{ nomState.message }}
            </p>
          </div>
        </div>

        <div class="bces-field">
          <label for="phone" class="bces-field__label">Téléphone <span class="bces-field__opt">(optionnel)</span></label>
          <input
            id="phone"
            v-model="phone"
            type="tel"
            class="bces-input"
            :class="{
              'bces-input--ok': phoneState.ok && phone.trim() !== '',
              'bces-input--err': phoneState.message !== null
            }"
            placeholder="555-1234"
            autocomplete="tel"
            inputmode="tel"
            :disabled="expired"
          />
          <p
            v-if="phoneState.message"
            class="bces-field__hint bces-field__hint--err"
          >
            {{ phoneState.message }}
          </p>
        </div>

        <button
          type="submit"
          class="bces-btn"
          :disabled="!canSubmit"
        >
          <template v-if="loading">Enregistrement…</template>
          <template v-else-if="expired">Compte expiré</template>
          <template v-else>Activer mon compte</template>
        </button>
      </form>
    </template>
  </main>
</template>