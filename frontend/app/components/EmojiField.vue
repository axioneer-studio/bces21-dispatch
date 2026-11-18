<script setup lang="ts">
/**
 * Choix d'un emoji : un clic sur l'emoji ouvre le menu (catégories, recherche en
 * français), et « Autre » permet de coller n'importe quel emoji.
 */
const props = withDefaults(defineProps<{
  modelValue: string
  label?: string
  maxlength?: number
}>(), {
  label: 'Emoji',
  maxlength: 16
})

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

interface EmojiItem {
  emoji: string
  /** Mots-clés de recherche, sans accents. */
  keywords: string
}

interface EmojiCategory {
  label: string
  icon: string
  items: EmojiItem[]
}

const e = (emoji: string, keywords: string): EmojiItem => ({ emoji, keywords })

const CATEGORIES: EmojiCategory[] = [
  {
    label: 'Médical',
    icon: '🩺',
    items: [
      e('🩺', 'stethoscope medecin consultation'), e('💉', 'seringue piqure injection vaccin'),
      e('💊', 'medicament pilule pharmacie'), e('🩹', 'pansement plaie soin'),
      e('🩻', 'radio radiographie irm imagerie'), e('🩸', 'sang transfusion prise de sang'),
      e('🧬', 'adn genetique'), e('🦠', 'virus microbe infection'),
      e('🧪', 'tube test laboratoire analyse'), e('🔬', 'microscope laboratoire'),
      e('🧫', 'boite de petri culture'), e('🌡️', 'thermometre fievre temperature'),
      e('🫀', 'coeur cardio cardiologie thoracique'), e('🫁', 'poumons pneumo pneumologie'),
      e('🧠', 'cerveau neuro neurologie psychologie'), e('🦴', 'os ortho orthopedie kine'),
      e('🦷', 'dent dentiste'), e('👁️', 'oeil ophtalmo yeux'),
      e('👂', 'oreille orl'), e('🦵', 'jambe kine'),
      e('🦶', 'pied podologue'), e('💪', 'bras muscle kine'),
      e('🤰', 'grossesse maternite enceinte'), e('👶', 'bebe pediatrie naissance'),
      e('🩼', 'bequille'), e('🦽', 'fauteuil roulant'),
      e('🧑‍⚕️', 'soignant medecin infirmier'), e('👨‍⚕️', 'medecin docteur homme'),
      e('👩‍⚕️', 'medecin docteur femme'), e('⚕️', 'caducee medecine'),
      e('🏥', 'hopital'), e('❤️‍🩹', 'coeur pansement guerison'),
      e('🔪', 'bistouri chirurgie couteau scalpel'), e('✂️', 'ciseaux chirurgie'),
      e('🧤', 'gants'), e('😷', 'masque'),
      e('🤕', 'blesse bandage'), e('🤒', 'malade fievre'),
      e('🤢', 'nausee'), e('🥼', 'blouse labo'),
      e('💀', 'mort crane legiste'), e('⚰️', 'cercueil morgue'),
      e('🪦', 'tombe enterrement'), e('⚱️', 'urne incineration')
    ]
  },
  {
    label: 'Secours et véhicules',
    icon: '🚑',
    items: [
      e('🚑', 'ambulance secours'), e('🚒', 'pompiers camion'),
      e('🚓', 'police voiture'), e('🚔', 'police'),
      e('🚁', 'helicoptere medicopter pilote'), e('✈️', 'avion pilote'),
      e('🛩️', 'petit avion pilote'), e('🚤', 'bateau vedette'),
      e('🛥️', 'bateau'), e('⛵', 'voilier bateau'),
      e('🚗', 'voiture conduite'), e('🏍️', 'moto'),
      e('🚲', 'velo'), e('🚚', 'camion'),
      e('🛻', 'pick-up'), e('🚜', 'tracteur'),
      e('🚨', 'gyrophare urgence alerte'), e('🧯', 'extincteur incendie'),
      e('🪂', 'parachute'), e('🛟', 'bouee sauvetage noyade'),
      e('⛑️', 'casque secours secouriste'), e('🪖', 'casque militaire'),
      e('🔦', 'lampe torche'), e('📻', 'radio'),
      e('📡', 'antenne radio'), e('🧭', 'boussole orientation'),
      e('🗺️', 'carte'), e('⚓', 'ancre marine'),
      e('🏔️', 'montagne'), e('🌊', 'vague mer')
    ]
  },
  {
    label: 'Activités',
    icon: '🎓',
    items: [
      e('🎓', 'diplome formation'), e('🧑‍🏫', 'formateur professeur'),
      e('📚', 'livres cours'), e('📖', 'livre lecture'),
      e('✍️', 'ecriture examen'), e('🏊', 'natation nageur'),
      e('🤿', 'plongee plongeur'), e('🧗', 'escalade alpinisme'),
      e('🏃', 'course sport'), e('🏋️', 'musculation sport'),
      e('🥋', 'combat self-defense'), e('🎯', 'cible tir precision'),
      e('🔫', 'arme pistolet tir ppa'), e('🐕', 'chien cynophile'),
      e('🐾', 'pattes veterinaire animaux'), e('🐴', 'cheval'),
      e('🐈', 'chat'), e('🦅', 'aigle'),
      e('🧘', 'meditation'), e('🍳', 'cuisine'),
      e('🎤', 'micro discours'), e('🤝', 'accueil poignee de main')
    ]
  },
  {
    label: 'Symboles',
    icon: '⭐',
    items: [
      e('⭐', 'etoile'), e('🌟', 'etoile brillante'),
      e('✅', 'valide ok'), e('✔️', 'coche valide'),
      e('❌', 'croix non'), e('⚠️', 'danger attention'),
      e('☢️', 'radioactif'), e('☣️', 'biologique danger'),
      e('🔥', 'feu incendie brulure'), e('💧', 'eau goutte'),
      e('❄️', 'froid neige'), e('⚡', 'eclair electrique'),
      e('🎖️', 'medaille militaire'), e('🏅', 'medaille'),
      e('🥇', 'or premier'), e('🏆', 'trophee'),
      e('🔰', 'debutant'), e('🆘', 'sos'),
      e('➕', 'plus croix'), e('♥️', 'coeur'),
      e('🔴', 'rond rouge'), e('🟠', 'rond orange'),
      e('🟡', 'rond jaune'), e('🟢', 'rond vert'),
      e('🔵', 'rond bleu'), e('🟣', 'rond violet'),
      e('⚫', 'rond noir'), e('⚪', 'rond blanc'),
      e('🟥', 'carre rouge'), e('🟧', 'carre orange'),
      e('🟨', 'carre jaune'), e('🟩', 'carre vert'),
      e('🟦', 'carre bleu'), e('🟪', 'carre violet')
    ]
  },
  {
    label: 'Objets',
    icon: '🧰',
    items: [
      e('📋', 'presse-papier dossier'), e('📝', 'note rapport'),
      e('🗂️', 'classeur archives'), e('🔑', 'cle'),
      e('🧰', 'boite a outils'), e('🔧', 'cle mecanique'),
      e('🪛', 'tournevis'), e('🔨', 'marteau'),
      e('⚙️', 'engrenage technique'), e('💻', 'ordinateur informatique'),
      e('📱', 'telephone'), e('🎙️', 'micro radio'),
      e('📷', 'appareil photo'), e('🔋', 'batterie'),
      e('🧲', 'aimant'), e('🧳', 'valise'),
      e('🛏️', 'lit chambre'), e('🪑', 'chaise'),
      e('⏱️', 'chronometre'), e('📦', 'colis stock')
    ]
  }
]

const open = ref(false)
const search = ref('')
const activeCategory = ref(0)
const other = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

function normalize(value: string) {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
}

const results = computed(() => {
  const query = normalize(search.value)
  if (!query) return CATEGORIES[activeCategory.value]?.items ?? []
  const seen = new Set<string>()
  return CATEGORIES.flatMap((category) => category.items).filter((item) => {
    if (seen.has(item.emoji) || !item.keywords.includes(query)) return false
    seen.add(item.emoji)
    return true
  })
})

function toggle() {
  open.value = !open.value
  if (open.value) {
    search.value = ''
    other.value = ''
    nextTick(() => searchInput.value?.focus())
  }
}

function choose(emoji: string) {
  emit('update:modelValue', emoji)
  open.value = false
}

function chooseOther() {
  const value = other.value.trim()
  if (value) choose(value.slice(0, props.maxlength))
}
</script>

<template>
  <!-- Deux cases de la grille du formulaire : le bouton, puis le menu sur toute la largeur. -->
  <div class="emoji-field">
    <div class="emoji-field__cell">
      <span class="emoji-field__label">{{ label }}</span>
      <button
        type="button"
        class="emoji-field__button"
        :class="{ 'is-open': open, 'is-empty': !modelValue }"
        :aria-label="modelValue ? `${label} : ${modelValue}, changer` : `Choisir ${label.toLowerCase()}`"
        :aria-expanded="open"
        @click="toggle"
      >{{ modelValue || '＋' }}</button>
    </div>

    <div v-if="open" class="emoji-menu" role="dialog" :aria-label="`Choisir ${label.toLowerCase()}`" @keydown.esc.stop.prevent="open = false">
      <input ref="searchInput" v-model="search" class="emoji-menu__search" type="search" placeholder="Rechercher (cœur, hélico, radio…)" aria-label="Rechercher un emoji">
      <div v-if="!search.trim()" class="emoji-menu__tabs" role="tablist">
        <button
          v-for="(category, index) in CATEGORIES"
          :key="category.label"
          type="button"
          role="tab"
          :aria-selected="activeCategory === index"
          :class="{ 'is-active': activeCategory === index }"
          :title="category.label"
          @click="activeCategory = index"
        >{{ category.icon }}</button>
      </div>
      <div class="emoji-menu__grid">
        <button
          v-for="item in results"
          :key="item.emoji"
          type="button"
          :class="{ 'is-selected': item.emoji === modelValue }"
          :title="item.keywords"
          @click="choose(item.emoji)"
        >{{ item.emoji }}</button>
        <p v-if="!results.length" class="emoji-menu__empty">Aucun emoji trouvé : collez-le dans « Autre ».</p>
      </div>
      <div class="emoji-menu__other">
        <input v-model="other" type="text" :maxlength="maxlength" placeholder="Autre : collez un emoji" aria-label="Autre emoji" @keydown.enter.prevent="chooseOther">
        <button type="button" :disabled="!other.trim()" @click="chooseOther">OK</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.emoji-field { display: contents; }
.emoji-field__cell { display: grid; gap: 5px; }
.emoji-field__label { color: var(--dp-text-2); font-size: 10px; }
.emoji-field__button { display: grid; width: 100%; min-height: 36px; place-items: center; border: 1px solid var(--dp-line); border-radius: 9px; color: var(--dp-text); background: var(--dp-bg); font-size: 19px; line-height: 1; cursor: pointer; }
.emoji-field__button:hover, .emoji-field__button.is-open { border-color: var(--dp-accent-line); }
.emoji-field__button.is-empty { color: var(--dp-text-dim); font-size: 15px; }
.emoji-menu { display: grid; grid-column: 1 / -1; gap: 8px; padding: 10px; border: 1px solid var(--dp-line-strong); border-radius: 12px; background: var(--dp-panel-2); }
.emoji-menu input { box-sizing: border-box; width: 100%; min-height: 32px; padding: 0 10px; border: 1px solid var(--dp-line); border-radius: 8px; color: var(--dp-text); background: var(--dp-bg); font: inherit; font-size: 12px; }
.emoji-menu__tabs { display: flex; gap: 4px; }
.emoji-menu__tabs button { flex: 1; min-height: 30px; border: 1px solid transparent; border-radius: 8px; background: transparent; font-size: 16px; cursor: pointer; }
.emoji-menu__tabs button.is-active { border-color: var(--dp-accent-line); background: var(--dp-accent-soft); }
.emoji-menu__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(36px, 1fr)); gap: 2px; max-height: 190px; overflow-y: auto; }
.emoji-menu__grid button { display: grid; height: 36px; place-items: center; border: 1px solid transparent; border-radius: 8px; background: transparent; font-size: 20px; cursor: pointer; }
.emoji-menu__grid button:hover { background: var(--dp-panel); }
.emoji-menu__grid button.is-selected { border-color: var(--dp-accent-line); background: var(--dp-accent-soft); }
.emoji-menu__empty { grid-column: 1 / -1; margin: 6px 0; color: var(--dp-text-dim); font-size: 11px; }
.emoji-menu__other { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; }
.emoji-menu__other button { min-height: 32px; padding: 0 12px; border: 1px solid var(--dp-accent-line); border-radius: 8px; color: var(--dp-accent); background: var(--dp-accent-soft); font: inherit; font-size: 11px; font-weight: 700; cursor: pointer; }
.emoji-menu__other button:disabled { opacity: .5; cursor: not-allowed; }
</style>
