# BCES Dispatch

Application de dispatch du BCES : tableau de bord temps réel des agents, des interventions et des radios, avec authentification Discord OAuth2.

- **Frontend** : Nuxt 4 (Vue 3) + Tailwind CSS 4 + `@nuxt/ui` + `@nuxt/icon`
- **Backend** : FastAPI (Python 3.11+) + SQLAlchemy 2 async + SQLite
- **Temps réel** : WebSocket (`/ws/dispatch`) avec diffusion d'un snapshot à chaque mutation

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Installation](#installation)
- [Configuration](#configuration)
- [Authentification Discord](#authentification-discord)
- [API REST](#api-rest)
- [WebSocket](#websocket)
- [Tâches de fond](#tâches-de-fond)
- [Base de données](#base-de-données)
- [Frontend](#frontend)
- [Sécurité](#sécurité)
- [Licence](#licence)

---

## Fonctionnalités

### Dispatch (`/dispatch`)

- Plateau de dispatch en grille CSS : **Centrale**, **Hôpital**, **Astreinte**,
  **Congés**, **IPT**, **Astreinte fin de service**, **Pause**, plus les
  **interventions / consultations** créées à la volée.
- Glisser-déposer des agents entre les créneaux et la réserve « hors service ».
- Statut d'intervention, choisi dans la liste gérée dans Administration, avec
  emoji, et code postal par carte. La liste a deux parties, toujours dans cet
  ordre : les statuts (Patrouille, Inter, Renfort, Enterrement…), puis les lieux
  (BCES, LSES, Zombie, salles de l'hôpital…). Une entrée peut avoir une couleur,
  qui teinte l'intervention, et être cochée « Primo Inter » pour lier
  l'intervention à la page Crise. Les 22 statuts et 17 lieux d'origine sont
  injectés au démarrage quand la liste est vide.
- Panneau **Radios** : marche/arrêt, numéro de série éditable, agent associé,
  fréquences 147 / 570 MHz, état « attente » (chargement 2,5 s).
- Les tuiles d'employés viennent du registre RH et ne nécessitent pas de compte
  Discord ; les affectations persistent par employé.
- En-tête d'état : fréquences radio, statut Hôpital (ouvert / fermé / nuit),
  puces **LSES** et **SAFD** en lecture seule (synchronisées depuis un Google Sheet).
- Panneau de flotte de véhicules (emplacement préparé) et bloc-notes Dispatch
  partagé, modifiable au double-clic puis sauvegardé automatiquement à la
  sortie de l'édition.
- Événements de l’Agenda du jour visibles sous les radios ; tous les comptes
  actifs peuvent consulter l’agenda, tandis que sa gestion reste réservée aux
  grades autorisés.
- Mises à jour temps réel via WebSocket, sans rafraîchissement de page.

### Crise (`/crise`)

- Page ouverte à tout compte validé, même sans rôle, pour gérer une situation de
  crise. En pratique, c'est la Centrale du Dispatch qui la pilote.
- Équipe : un Primo Intervenant et les agents qui l'assistent, choisis parmi les
  employés actifs. Désigner un Primo l'affecte aussi, sur le Dispatch, à
  l'intervention « Primo » de la crise, créée au besoin ; un Primo remplacé y
  reste affecté.
- Dans l'autre sens, passer une intervention du Dispatch à un statut coché
  « Primo Inter » dans Administration (« Primo » par défaut) en
  fait celle de la crise, si la crise n'en a pas encore. L'équipe suit alors les
  membres de cette intervention : le premier arrivé est Primo, les suivants en
  assistance ; qui en est retiré ou déplacé quitte l'équipe, et si c'était le
  Primo, le suivant de l'intervention prend sa place. Supprimer ou vider
  l'intervention (Tempête du Dispatch) vide l'équipe (`backend/crisis_link.py`).
- En-tête : code postal (ZIP) de la crise, partagé avec l'intervention « Primo »
  du Dispatch (modifiable d'un côté ou de l'autre), et heure de saisie de la
  première ligne.
- Liste des blessés, sous forme de tableau modifiable sur place : nom et prénom,
  appartenance (groupe), coma, blessure grave, inconscient, analyse sommaire des
  blessures, médecin qui rapatrie, médecin soignant, arrivée à l'hôpital (l'heure
  est prise automatiquement quand on coche) et soins terminés. Côté Centrale :
  ajout au canal radio et chambre (lit de l'onglet Chambres) où le blessé est
  installé.
- Choisir un lit y installe le blessé dans l'onglet Chambres (nom, accident
  « Crise », date du jour), avec la raison de présence « En attente
  d'opération », ajoutée à la liste des raisons si besoin. Seuls les lits libres sont
  proposés. Une fois soigné, ou retiré de la liste, le blessé quitte le lit, qui
  redevient libre ; libérer le lit depuis l'onglet Chambres le retire aussi de
  la ligne de crise.
- L'appartenance se choisit parmi les Groupes gérés dans Administration, et les
  médecins parmi les employés ; ces listes ne sont pas exhaustives : « Autre… »
  permet de saisir une autre valeur. Un groupe qui a une couleur teinte la case
  Appartenance.
- Celui qui coche « Arrivé » devient le médecin qui rapatrie, et celui qui coche
  « Soigné » le médecin soignant, si ces cases sont vides (nom de sa tuile
  employé, sinon son nom RP).
- « Canal » ne se coche qu'une fois le blessé soigné ; décocher « Soigné »
  décoche aussi « Canal ». Une ligne soignée mais pas encore au canal est
  surlignée en vert ; soignée et au canal, elle est grisée.
- La « Tempête » vide la liste des blessés et l'équipe, et libère les lits
  occupés par des blessés de la crise.
- Les blessés sont regroupés par appartenance : les groupes dans l'ordre où ils
  sont apparus, et dans chaque groupe l'ordre de saisie (le plus récent en bas
  de son groupe). Le blessé arrivé à l'hôpital depuis le plus longtemps sans
  médecin soignant est surligné en orange, sans changer de place.
- La page se rafraîchit toutes les 5 secondes, sauf pendant une saisie dans le
  tableau.

### Hôpital (`/hopital`)

- Page ouverte à tout compte validé, même sans rôle, avec deux onglets : Chambres et
  Morgue.
- **Chambres** : des chambres contenant des lits. Un lit est créé vide ; tout
  compte connecté y affecte un patient (nom, accident, date d'arrivée, raison de
  sa présence), indique si les soins sont faits et si les forces de l'ordre sont
  à prévenir ou déjà prévenues, puis libère le lit. La raison se choisit dans
  une liste, ou se saisit avec « Autre… ». Seuls la Direction (grade Direction,
  par défaut) et les rôles ayant la permission applicative « Gérer l'hôpital »
  ajoutent, renomment et suppriment les chambres et les lits, ainsi que les
  raisons de la liste. Un lit est créé sous le nom « Lit N » et peut être
  renommé ensuite ; les lits restent affichés dans leur ordre de création.
- **Morgue** : défunts pris en charge, avec date du décès, identité, appartenance
  connue (Groupes d'Administration, ou « Autre… » ; l'étiquette prend la couleur
  du groupe, ou à défaut une teinte tirée du nom), informations communicables ou non, autopsie, médecin légiste, contacts
  d'urgence et possibilité de récupération par les proches. Un corps en cellule
  réfrigérée et une urne s'affichent dans deux formes de case différentes.
  L'autopsie et la récupération se renseignent après l'ajout, d'un clic sur la
  case.
- Tout compte connecté ajoute, modifie et retire un défunt, et indique s’il est
  récupérable. L’autopsie et le légiste ne se renseignent que par un médecin légiste
  (compte lié à un employé qui a validé une formation donnant le droit « Médecin
  légiste », voir Pôles & Spé) ou par la Direction (grade Direction) ; le légiste
  qui la déclare devient le légiste du défunt. Seuls les légistes procèdent à
  l’incinération.

### Pôles & Spé (`/poles-specialites`) et Formation (`/formation`)

- Valider une formation pour un employé ajoute l'emoji de la formation à ses
  compétences (Ressources humaines) ; la retirer enlève l'emoji. L'emoji est la
  trace de la validation : un emoji ajouté à la main dans Ressources humaines
  compte aussi.
- **Pôles & Spé**, ouverte à tout compte validé : les **formations générales**,
  en deux sections, **Pôles** (ex. Pilote Medicopter, Stock, Formateur) et
  **Spécialités** (ex. Médecin légiste). Le bouton « Ajouter » de chaque section
  fixe la catégorie. Une carte par formation, avec son équipe et le numéro de
  chacun. Rôles : Responsable, Second, Validé (ils ont l'emoji) et En cours (pas
  encore). Un employé d'un grade « Période d'essai » ou « En formation » ne
  rejoint ni pôle ni spécialité (`409`) ; il peut seulement en être retiré.
- **Formation**, réservée aux formateurs (droit « Formateur ») : une fiche par
  employé en formation, comme l'ancienne feuille de suivi. Deux onglets, nommés
  d'après les grades cochés « Période d'essai » et « En formation » dans
  Direction. La page n'écrit jamais « Interne » ni « Résident » en dur : elle
  reprend ces noms de grades.
  - **Commun** : arrivée (celle de la fiche RH, corrigeable ici), jours depuis
    l'arrivée, mentors (des formateurs uniquement), notes.
  - **Période d'essai**
    - Les modules sont rangés par type : Validations basiques, Gestion des
      outils, Type d'intervention, Blessures. Chacun se note sur quatre niveaux :
      ❌ Non observé, 👁️ Observé, 🧾 Pratiqué avec aide, ✅ Pratiqué en autonomie.
    - Questionnaire de passage : les bonnes réponses sont ramenées sur 20, quel
      que soit le nombre de questions.
    - Simulation validante : cinq critères.
    - Le statut de progression est calculé à partir des jours, des basiques et
      de la progression globale.
  - **En formation** : la fiche garde les résultats de la période d'essai et
    ajoute :
    - les formations obligatoires et facultatives, notées ❌ Non observé, 🧾
      Pratiqué, ✅ Validé ;
    - une simulation validante à six critères (avec « Gestion Malus »).
  - **Calculs**
    - La progression d'un type est la somme des niveaux sur les points
      possibles (3 par module de période d'essai, 2 par formation).
    - Une simulation note chaque critère de 1 (pas réalisé) à 5 (très bien),
      soit de 0 à 4 points ; le total est ramené sur 20.
  - **Emoji d'un module** (facultatif) : il rejoint les compétences au niveau le
    plus haut et les quitte en dessous, tant que l'employé est à l'étape du
    module.
  - **Passages**, avec confirmation, et annulables :
    - **Passage au grade « En formation »** juste au-dessus. Il faut tous les
      modules de période d'essai en autonomie et une moyenne questionnaire +
      simulation d'au moins 14/20. Les emojis des modules de période d'essai
      quittent les compétences. Le bouton d'annulation, tout en bas de la
      fiche « En formation », rend le grade d'avant et ses emojis. Pour un
      employé passé « En formation » hors de la page, il rend le grade «
      Période d'essai » juste en dessous du sien.
    - **Fin de formation**, passage au grade juste au-dessus. Il faut toutes
      les formations obligatoires validées et une simulation d'au moins 14/20.
      Les emojis des formations quittent les compétences. Annuler (depuis «
      Formation terminée ») rend le grade « En formation » et ses emojis.
    - **Forcer** : une case à côté du bouton dégrise le passage malgré les
      conditions manquantes. Même forcé, il faut toutes les validations
      basiques (période d'essai) ou toutes les formations obligatoires
      (période de formation).
  - **Qui fait quoi** : tous les formateurs remplissent les fiches. Les modules
    et le questionnaire se gèrent par la Direction, « Gérer l'hôpital » et le
    Responsable du pôle qui donne le droit Formateur. Forcer un passage est
    réservé à la Direction et au Responsable de ce pôle (pas « Gérer
    l'hôpital »).
  - **Au premier démarrage**, la base reçoit une seule fois les modules, les
    formations et le questionnaire de la feuille de suivi
    (`backend/app/services/intern_defaults.py`).
- Une formation générale peut donner des droits à ceux qui l'ont validée (qui
  ont son emoji) : **Formateur**, **Médecin légiste**, **Ressources humaines**
  et **Stock** (gestion des stocks, pour la future page Stock). Le compte lié à
  la tuile de l'employé reçoit ces droits ; ils ne se donnent plus par les
  rôles d'Administration ni par les grades. La Direction a le droit Ressources
  humaines par défaut.
- Ajouter, modifier et supprimer une formation est réservé à ceux qui gèrent
  l'hôpital (rôle « Gérer l'hôpital » ou grade de la Direction). Ce rôle donne
  des actions en plus sans ouvrir de page : sur Formation, il faut aussi être
  formateur.
- L'équipe d'une formation générale se gère par la Direction, qui seule nomme
  ou retire un Responsable ; par son Responsable (Second, Validé, En cours) ; et
  par ses Seconds, qui ajoutent, changent ou retirent des Validés et des En
  cours, sans toucher aux Seconds ni au Responsable.
- Changer l'emoji d'une formation le remplace chez les employés qui l'ont ; la
  supprimer le retire de leurs compétences, et avec lui les droits qu'elle
  donnait.

### Ressources humaines (`/ressources-humaines`)

- Création et gestion des employés, de leurs compétences et du lien facultatif
  à un compte utilisateur ; les tuiles sont créées dans RH, puis liées
  séparément aux comptes. Attribution d'un grade centralisé par la Direction.
- La page est réservée aux RH et à la Direction : elle s'ouvre avec le droit
  Ressources humaines (formation générale qui le donne, ou grade de la
  Direction) et ne se coche plus dans les rôles. Ce droit permet toutes les
  actions de la page : gérer les employés et lier les comptes aux tuiles.

### Direction (`/direction`)

- Création, modification et suppression des grades et de leur niveau
  hiérarchique numérique.
- Configuration des permissions opérationnelles rattachées à chaque grade.
- Un grade peut être marqué « Période d'essai » (en formation initiale) ou « En
  formation » (en formation complémentaire), pas les deux : leurs employés
  seront suivis sur la page des formateurs. Plusieurs grades peuvent avoir
  chaque case.

### Administration (`/administration`)

- Gestion des utilisateurs, des demandes d’inscription et de l’activation des
  comptes.
- Création des rôles applicatifs, attribution des rôles et configuration de
  l’accès aux pages et des permissions applicatives, dont la liaison d’un
  compte à une tuile employé.
- Paramètres généraux, dont l’ouverture des inscriptions.
- Le premier compte de l'application est le super-admin initial.

### Comptes

- Connexion Discord OAuth2 (création de compte automatique à la première connexion).
- Complétion du profil (prénom RP / nom RP / téléphone) obligatoire, avec délai de 24 h.
- Brouillon de profil sauvegardé en `localStorage` (`bces:profile-draft`).
- Comptes en attente de validation : traitement par un administrateur. Un
  compte validé accède au Dispatch, à la Crise, à l'Hôpital, à l'Agenda et au Stock, même
  sans rôle ; un rôle ajoute les autres pages.
- Un compte peut avoir plusieurs rôles (par exemple Ressources humaines et
  Gestion de l'hôpital) : il cumule les pages et les permissions de tous ses
  rôles.
- Désactiver un compte le suspend : il ne peut plus se connecter ni appeler
  l'API. Le réactiver lui rend ses accès sans nouvelle validation.

### Interface

- Thème sombre, palette `--bces-*` (écrans d'auth) et `--dp-*` (dispatch).
- Notifications (toasts) avec pause au survol, icônes Lucide servies en local.
- Navigation par rôle ; les API appliquent aussi les permissions côté serveur.
- Barre latérale à 3 modes d'affichage (réduite / étendue / au survol), mémorisés
  dans `localStorage` (`bces:sidebar-mode`).
- Affichage des dates/heures dans le fuseau horaire du navigateur.

---

## Architecture

```
bces21-dispatch/
├── backend/            # API FastAPI + base SQLite
│   ├── main.py         # point d'entrée ASGI (main:app), lifespan, CORS
│   ├── config.py       # Settings pydantic-settings (lecture de .env)
│   ├── database.py     # moteur async, session, init_db + migrations
│   ├── models.py       # modèles SQLAlchemy
│   ├── schemas.py      # schémas Pydantic (entrées / sorties)
│   ├── deps.py         # dépendances FastAPI (auth)
│   ├── agents.py       # routes /api/users
│   ├── administration.py # routes d'administration
│   ├── agenda.py       # routes de l'agenda
│   ├── cleanup.py      # purge des comptes incomplets
│   ├── direction.py    # routes grades et permissions (Direction)
│   ├── dispatch.py     # routes /api/dispatch/* + WebSocket
│   ├── fleet.py        # gestion de la flotte de véhicules
│   ├── frequencies.py  # gestion des fréquences radio
│   ├── frequency_settings.py # paramètres de fréquences
│   ├── fix_google_sheets.py
│   ├── google_sheets_service.py
│   ├── google_sheets_service_fixed.py
│   ├── google_sheets_service_v2.py
│   ├── grade_permissions.py
│   ├── hospital_access.py
│   ├── hospital_rooms.py
│   ├── human_resources.py # employés, rôles, permissions, résumé du dashboard
│   ├── morgue.py       # routes morgue
│   ├── requirements.txt
│   ├── s3_service.py
│   ├── sheets_sync.py
│   ├── status_sync.py  # synchronisation Google Sheet (LSES / SAFD)
│   ├── Dockerfile
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── router.py   # routes /api/auth/*
│   │   ├── discord.py  # client OAuth2 Discord
│   │   └── session.py  # émission / vérification du JWT de session
│   └── migrations/
├── frontend/           # application Nuxt 4
│   ├── nuxt.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── Dockerfile
│   ├── app.vue
│   ├── app/
│   │   ├── assets/
│   │   │   └── css/
│   │   │       ├── dispatch.css
│   │   │       └── main.css
│   │   ├── components/
│   │   │   ├── AgentTile.vue
│   │   │   ├── AppLogo.vue
│   │   │   ├── ConfirmDialog.vue
│   │   │   ├── DiscordButton.vue
│   │   │   ├── DispatchHeader.vue
│   │   │   ├── EmptySlotState.vue
│   │   │   ├── FleetPanel.vue
│   │   │   ├── FrequencyPicker.vue
│   │   │   ├── InterventionCard.vue
│   │   │   ├── MorguePanel.vue
│   │   │   ├── RadioPanel.vue
│   │   │   ├── RoomsPanel.vue
│   │   │   ├── Sidebar.vue
│   │   │   ├── SlotPanel.vue
│   │   │   ├── StatusPicker.vue
│   │   │   ├── ToastStack.vue
│   │   │   └── ZipPicker.vue
│   │   ├── composables/
│   │   │   ├── useAppToast.ts
│   │   │   ├── useDispatchApi.ts
│   │   │   ├── useDispatchSocket.ts
│   │   │   ├── useDispatchStore.ts
│   │   │   ├── useSyncApi.ts
│   │   │   ├── useTimezone.ts
│   │   │   └── useToastStore.ts
│   │   ├── layouts/
│   │   │   ├── default.vue
│   │   │   └── dispatch.vue
│   │   ├── middleware/
│   │   │   └── access.global.ts
│   │   ├── pages/
│   │   │   ├── acces-refuse.vue
│   │   │   ├── administration.vue
│   │   │   ├── agenda.vue
│   │   │   ├── complete-profile.vue
│   │   │   ├── direction.vue
│   │   │   ├── dispatch.vue
│   │   │   ├── hopital.vue
│   │   │   ├── index.vue
│   │   │   ├── ressources-humaines.vue
│   │   │   ├── stock.vue
│   │   │   ├── administration/
│   │   │   ├── direction/
│   │   │   ├── hopital/
│   │   │   └── stock/
│   │   ├── types/
│   │   │   └── toast.ts
│   │   └── utils/
│   │       ├── agent.ts
│   │       ├── radios.ts
│   │       ├── statuses.ts
│   │       └── toast.ts
│   ├── public/
│   │   ├── robots.txt
│   │   └── images/
│   └── server/
│       └── routes/
│           └── favicon.ico.ts
├── .github/ISSUE_TEMPLATE/
├── docker-compose.yml
├── dev.cmd
├── dev.ps1
├── LICENCE.md
└── README.md
```

Le front appelle le back via deux chemins :

- **URL relatives** (`/api/...`) → proxy Nitro configuré dans `nuxt.config.ts`
  (`routeRules['/api/**']`), pratique pour le SSR.
- **URL absolues** (`runtimeConfig.public.apiBase`) → appelées directement au
  backend, notamment par `useDispatchApi` et le WebSocket (`/ws/dispatch` n'est
  pas couvert par le proxy).

---

## Stack technique

| Couche | Technologies |
|---|---|
| Frontend | Nuxt 4.6, Vue 3.5, Vue Router 5, Tailwind CSS 4 (`@tailwindcss/vite`), `@nuxt/ui` 4, `@nuxt/icon` 2 + `@iconify-json/lucide` |
| Backend | FastAPI, Uvicorn, Pydantic v2, pydantic-settings, SQLAlchemy 2 (async), aiosqlite, httpx, PyJWT |
| Auth | Discord OAuth2 + JWT HS256 en cookie `HttpOnly` |
| Temps réel | WebSocket natif FastAPI (Starlette) |
| Base | SQLite (fichier `backend/bces21.db`) |

---

## Installation

### Démarrage en un clic (Windows)

Double-cliquez sur `dev.cmd` à la racine du projet. Le script prépare les
dépendances si nécessaire, puis lance le backend et le frontend dans deux
fenêtres séparées :

- Application : <http://localhost:3000>
- API : <http://localhost:8000/docs>

Vous pouvez aussi le lancer depuis PowerShell avec `.\dev.ps1`.

### Déploiement Docker avec Coolify

Le dépôt inclut un `docker-compose.yml` ainsi qu'un Dockerfile pour chaque
application. Dans Coolify, créez une ressource **Docker Compose** depuis le
dépôt et renseignez les paramètres de base de données et les identifiants
Discord (voir `.env.example`) :

- Les valeurs par défaut du backend (base de données, sessions, tâches de fond,
  etc.) sont définies directement dans `docker-compose.yml`, à l'exception de
  `DATABASE_URL`, qui doit être configurée explicitement dans Coolify. Le fichier local
  `backend/.env` n'est pas copié dans l'image ni chargé automatiquement.
- Les domaines publics sont configurés dans Coolify pour les services
  `frontend` et `backend`. Le Compose utilise leurs noms d'hôte
  (`SERVICE_URL_FRONTEND` et `SERVICE_URL_BACKEND`) sans suffixe de port :
  `3000` et `8000` restent les ports internes des conteneurs et ne figurent pas
  dans les URLs du navigateur.
- Ajoutez `https://<domaine-frontend>/auth/discord/callback` aux Redirect URI
  de l'application Discord, en remplaçant le domaine par celui généré ou
  configuré dans Coolify.
- `DISCORD_CLIENT_ID` et `DISCORD_CLIENT_SECRET` : identifiants Discord.

Coolify génère et conserve automatiquement `SESSION_SECRET` via sa variable
`SERVICE_REALBASE64_64_SESSION`. Les champs à saisir manuellement sont
`DATABASE_URL`, `DISCORD_CLIENT_ID` et `DISCORD_CLIENT_SECRET`. Pour conserver
SQLite dans le volume `dispatch-data`, utilisez
`sqlite+aiosqlite:////app/data/BCES.db` ; pour une base externe, utilisez une
URL SQLAlchemy async correspondante.

Le cookie de session utilise le domaine partagé `.bces.axioneer.com` afin
qu'il soit transmis entre le frontend et l'API sur leurs sous-domaines.

Associez chaque domaine au service correspondant dans Coolify, sur les ports
`3000` (frontend) et `8000` (backend). L'API doit être joignable par le
navigateur depuis son domaine HTTPS ; l'origine CORS est dérivée
automatiquement du domaine frontend. Le backend et le frontend communiquent
aussi sur le réseau interne Compose. La base SQLite est conservée dans le
volume `dispatch-data`.
Ne définissez pas plusieurs réplicas du backend avec cette base SQLite.

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Linux/macOS : cp .env.example .env
# renseigner DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET / SESSION_SECRET
uvicorn main:app --reload
```

- API : <http://localhost:8000>
- Documentation interactive : <http://localhost:8000/docs>
- La base SQLite et les 7 créneaux par défaut sont créés automatiquement au
  démarrage (voir [Base de données](#base-de-données)).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- Application : <http://localhost:3000>
- Le proxy `/api/**` pointe automatiquement sur `http://localhost:8000`.

### Scripts frontend

| Script | Commande |
|---|---|
| `npm run dev` | serveur de développement (HMR) |
| `npm run build` | build de production |
| `npm run generate` | génération statique |
| `npm run preview` | prévisualisation du build |
| `npm run postinstall` | `nuxt prepare` (types générés) |

> Il n'existe pas de script `typecheck` : la vérification de types se fait via
> `npx nuxt typecheck` (nécessite `vue-tsc`).

---

## Configuration

### Backend - `backend/.env`

Toutes les variables sont lues par `pydantic-settings` (fichier `.env` à la
racine du dossier `backend/`). Les variables non listées ici sont ignorées.

| Variable | Défaut | Description |
|---|---|---|
| `APP_NAME` | `BCES Dispatch API` | Titre de l'API |
| `APP_VERSION` | `0.1.0` | Version affichée par `/health` |
| `DEBUG` | `false` | Mode debug (echo SQL, logs verbeux) |
| `APP_TIMEZONE` | `Europe/Paris` | Fuseau serveur (le front utilise celui du navigateur) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./BCES.db` | URL SQLAlchemy async |
| `FRONTEND_BASE_URL` | `http://localhost:3000` | Base des redirections OAuth |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Origines autorisées, séparées par `,` |
| `DISCORD_CLIENT_ID` | *(vide)* | Identifiant de l'application Discord |
| `DISCORD_CLIENT_SECRET` | *(vide)* | Secret de l'application Discord |
| `DISCORD_REDIRECT_URI` | `http://localhost:3000/auth/discord/callback` | URI de redirection OAuth |
| `DISCORD_SCOPES` | `identify` | Scopes Discord, séparés par `,` |
| `SESSION_SECRET` | `change-me-in-production` | Clé de signature des JWT (**à changer**) |
| `SESSION_COOKIE_NAME` | `bces_session` | Nom du cookie de session |
| `SESSION_TTL_SECONDS` | `1209600` (14 j) | Durée de vie de la session |
| `SESSION_COOKIE_DOMAIN` | *(vide)* | Domaine du cookie (ex. `localhost`) |
| `SESSION_COOKIE_SECURE` | `false` | Passer à `true` derrière HTTPS |
| `PROFILE_DEADLINE_SECONDS` | `86400` (24 h) | Délai pour compléter le profil RP |
| `CLEANUP_INTERVAL_SECONDS` | `1800` (30 min) | Intervalle de purge des comptes incomplets |
| `STATUS_SHEET_CSV_URL` | *(export CSV du Sheet public)* | Source des statuts LSES / SAFD |
| `STATUS_SYNC_INTERVAL_SECONDS` | `30` | Intervalle de synchronisation du Sheet |

Générer un secret de session :

```bash
openssl rand -hex 32
```

### Frontend - variables `NUXT_PUBLIC_*`

Le front ne lit pas de fichier `.env` en développement : tout passe par
`runtimeConfig.public` dans `nuxt.config.ts`, surchargé par des variables
d'environnement.

| Variable | Défaut | Description |
|---|---|---|
| `NUXT_PUBLIC_API_BASE` | `http://localhost:8000` | Base de l'API backend |
| `NUXT_PUBLIC_DISCORD_AUTH_URL` | `/api/auth/discord/url` | Endpoint d'initiation OAuth |
| `NUXT_PUBLIC_TIMEZONE` | `Europe/Paris` | Fuseau de repli si le navigateur n'en expose pas |

```bash
# frontend/.env
NUXT_PUBLIC_API_BASE=http://localhost:8000
NUXT_PUBLIC_DISCORD_AUTH_URL=/api/auth/discord/url
NUXT_PUBLIC_TIMEZONE=Europe/Paris
```

---

## Authentification Discord

1. <https://discord.com/developers/applications> → **New Application**
2. **OAuth2 → Redirects** → ajouter `http://localhost:3000/auth/discord/callback`
3. Copier le **Client ID** et le **Client Secret** dans `backend/.env`
4. Lancer le backend puis ouvrir <http://localhost:3000>

### Déroulé

1. `GET /api/auth/discord/url` → génération d'un `state` (TTL 10 min, en
   mémoire) et retour de l'URL d'autorisation Discord ; le frontend redirige
   ensuite le navigateur vers Discord (il ne transite plus par `localhost:8000`).
2. `GET /auth/discord/callback` (frontend) → reçoit le code de Discord, appelle
   `POST /api/auth/discord/exchange` (backend) pour échanger le code contre une
   session, pose le cookie `bces_session` et redirige vers `/dispatch`.
3. Redirection selon l'état du compte :
   - profil incomplet → `/complete-profile?deadline=<iso>`
   - compte en attente → `/?status=pending`
   - compte valide → `/dispatch`
4. La **session** est un JWT HS256 (`sub`, `iat`, `exp`, `type`) stocké dans un
   cookie `HttpOnly` `bces_session` (`SameSite=Lax`, `Path=/`).

> Le premier compte créé est automatiquement validé et reçoit les droits
> super-admin. Les bases existantes sans super-admin attribuent ce rôle au
> compte le plus ancien lors de la migration.

---

## API REST

Les routes authentifiées exigent une session valide et un compte validé : un
compte en attente ou désactivé reçoit un `403`. Les API du Dispatch, de la
Crise, de l'Hôpital et de l'Agenda sont ouvertes à tout compte validé, même sans rôle ;
celles des ressources humaines, de la Direction et de l'administration
vérifient en plus la page cochée dans le rôle.

### Authentification & comptes

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/` | Nom et version de l'API |
| `GET` | `/health` | Santé (`status`, `version`, `timezone`) |
| `GET` | `/api/me` | Utilisateur courant |
| `GET` | `/api/auth/discord/url` | Initie le flux OAuth Discord (retourne l'URL d'autorisation) |
| `POST` | `/api/auth/discord/exchange` | Échange le code Discord contre une session (appelé depuis le frontend) |
| `GET` | `/auth/discord/callback` | Route frontend qui reçoit le callback Discord et pose le cookie de session |
| `POST` | `/api/auth/profile` | Enregistre prénom RP / nom RP / téléphone |
| `POST` | `/api/auth/logout` | Détruit la session |
| `GET` | `/api/auth/pending` | Liste des comptes en attente de validation |
| `GET` | `/api/users` | Liste des comptes utilisateurs |

### Administration, Direction et RH

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/admin/users` | Liste les utilisateurs et leur état (Administration) |
| `PUT` | `/api/admin/users/{id}/roles` | Remplace les rôles applicatifs du compte (`role_ids`, liste éventuellement vide) |
| `PATCH` | `/api/admin/users/{id}/activation` | Active ou désactive un compte |
| `DELETE` | `/api/admin/users/{id}` | Supprime un compte en conservant sa tuile RH |
| `POST` | `/api/admin/registrations/{id}/approve` | Valide une inscription |
| `POST` | `/api/admin/registrations/{id}/reject` | Refuse une inscription |
| `GET` / `POST` | `/api/admin/roles` | Liste ou crée des rôles applicatifs |
| `PATCH` / `DELETE` | `/api/admin/roles/{id}` | Modifie ou supprime un rôle applicatif |
| `GET` / `POST` | `/api/admin/intervention-statuses` | Liste (statuts puis lieux) ou crée une entrée : `kind` (`status` \| `place`), libellé, emoji, couleur facultative, « Primo Inter » |
| `PATCH` / `DELETE` | `/api/admin/intervention-statuses/{id}` | Modifie ou supprime un statut ; suppression refusée (`409`) si une intervention l'a |
| `POST` | `/api/admin/intervention-statuses/{id}/move?direction=-1\|1` | Monte ou descend l'entrée dans la liste de son type |
| `GET` / `POST` | `/api/admin/groups` | Liste ou crée des groupes d'appartenance (Crise, Morgue) |
| `PATCH` / `DELETE` | `/api/admin/groups/{id}` | Renomme un groupe et change sa couleur, ou le supprime ; les blessés et défunts gardent leur appartenance |
| `GET` | `/api/admin/permissions` | Liste les permissions applicatives configurables |
| `GET` / `PUT` | `/api/admin/settings` | Lit ou modifie les paramètres généraux |
| `GET` | `/api/direction/grades` | Liste les grades et leurs permissions |
| `GET` | `/api/direction/permissions` | Liste les capacités opérationnelles configurables |
| `POST` / `PATCH` / `DELETE` | `/api/direction/grades[/{id}]` | Gère les grades (Direction) |
| `GET` | `/api/employees` | Liste les employés (Dispatch ou RH) ; « RH » ci-dessous : droit Ressources humaines (`human_resources.manage`), donné par une formation ou par le grade Direction |
| `POST` | `/api/employees` | Crée une tuile sans compte lié (RH) |
| `PATCH` | `/api/employees/{id}` | Modifie la fiche (RH) |
| `PATCH` | `/api/employees/{id}/account` | Lie ou délie un compte (RH) |
| `DELETE` | `/api/employees/{id}` | Supprime un employé (RH) |
| `GET` | `/api/employee-accounts` | Liste les comptes actifs (RH) |
| `GET` | `/api/employee-grades` | Grades disponibles pour l’attribution RH |
| `GET` | `/api/dashboard/summary` | Indicateurs agrégés du tableau de bord |

### Dispatch

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/dispatch/snapshot` | Slots + radios + état courant |
| `PUT` | `/api/dispatch/note` | Met à jour le bloc-notes partagé du Dispatch |
| `POST` | `/api/dispatch/assignments/reset` | Ferme l’hôpital, remet les employés hors service et peut supprimer les interventions |
| `POST` | `/api/dispatch/slots` | Crée un slot (`kind`: `intervention` \| `consultation`) |
| `PATCH` | `/api/dispatch/slots/{id}` | Modifie un slot (titre, statut, code postal, lieu, type) |
| `DELETE` | `/api/dispatch/slots/{id}` | Supprime un slot (et ses affectations) |
| `POST` | `/api/dispatch/slots/{id}/assign` | Affecte un employé (`employee_id`) |
| `DELETE` | `/api/dispatch/slots/{id}/assign/{employee_id}` | Désaffecte un employé |
| `PATCH` | `/api/dispatch/radios/{id}` | Modifie une radio (série, agent, marche, chargement) |
| `PATCH` | `/api/dispatch/state` | Statut Hôpital (`ouvert` \| `ferme` \| `nuit`) et codes radio |

> `lses_status` et `safd_status` ne sont **pas** modifiables via l'API : ils sont
> pilotés par la synchronisation Google Sheet.

### Hôpital

> « `hospital.manage` » ci-dessous : permission applicative « Gérer l’hôpital »,
> ou grade Direction, qui l’a par défaut. « `hospital.forensic` » : droit
> « Médecin légiste », donné par une formation générale.

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/hospital/rooms` | Chambres et leurs lits, raisons proposées, et droit de gestion du compte connecté |
| `POST` | `/api/hospital/rooms` | Ajoute une chambre (`hospital.manage`) |
| `PATCH` | `/api/hospital/rooms/{id}` | Renomme une chambre (`hospital.manage`) |
| `DELETE` | `/api/hospital/rooms/{id}` | Supprime une chambre et ses lits, s’ils sont tous libres (`hospital.manage`) |
| `POST` | `/api/hospital/rooms/{id}/beds` | Ajoute un lit vide à la chambre (`hospital.manage`) |
| `PATCH` | `/api/hospital/beds/{id}` | Renomme un lit ; nom unique dans sa chambre (`hospital.manage`) |
| `DELETE` | `/api/hospital/beds/{id}` | Supprime un lit libre (`hospital.manage`) |
| `PUT` | `/api/hospital/beds/{id}/patient` | Affecte un patient au lit ou met à jour sa fiche (compte connecté) |
| `PATCH` | `/api/hospital/beds/{id}/flags` | Soins faits, forces de l’ordre à prévenir (compte connecté) |
| `DELETE` | `/api/hospital/beds/{id}/patient` | Libère le lit (compte connecté) |
| `POST` | `/api/hospital/bed-reasons` | Ajoute une raison proposée (`hospital.manage`) |
| `DELETE` | `/api/hospital/bed-reasons/{id}` | Supprime une raison proposée (`hospital.manage`) |
| `GET` | `/api/hospital/morgue` | Défunts, groupes proposés, et droits du compte connecté sur l’autopsie et l’incinération |
| `POST` | `/api/hospital/morgue` | Ajoute un défunt (compte connecté) |
| `PATCH` | `/api/hospital/morgue/{id}` | Modifie la fiche d’un défunt et sa récupération (compte connecté) |
| `PUT` | `/api/hospital/morgue/{id}/autopsy` | Déclare l’autopsie faite ou non ; le légiste qui la déclare devient le légiste du défunt (`hospital.forensic` ou grade Direction) |
| `PUT` | `/api/hospital/morgue/{id}/examiner` | Change le légiste du défunt, parmi les employés liés à un compte qui ont le droit « Médecin légiste » (`hospital.forensic` ou grade Direction) |
| `POST` | `/api/hospital/morgue/{id}/incinerate` | Incinère le corps, qui devient une urne (`hospital.forensic`) |
| `DELETE` | `/api/hospital/morgue/{id}` | Retire un corps ou une urne de la morgue (compte connecté) |

### Crise

Toutes les routes sont ouvertes à tout compte validé.

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/crisis` | Équipe (Primo et agents en assistance), blessés, employés actifs, lits et groupes proposés |
| `PUT` | `/api/crisis/team` | Remplace l'équipe : `primo_id` (ou `null`) et `helper_ids` ; un nouveau Primo est affecté à l'intervention « Primo » du Dispatch |
| `PUT` | `/api/crisis/zip` | Code postal de la crise, repris sur l'intervention « Primo » |
| `POST` | `/api/crisis/victims` | Ajoute un blessé |
| `PATCH` | `/api/crisis/victims/{id}` | Modifie un blessé ; `arrived: true` prend l'heure d'arrivée, `false` l'efface. Cocher l'arrivée ou les soins renseigne le médecin correspondant s'il est vide ; `channel_added` exige `care_done` (`409` sinon) |
| `DELETE` | `/api/crisis/victims/{id}` | Retire un blessé de la liste |
| `POST` | `/api/crisis/reset` | Tempête : vide la liste des blessés et l'équipe, libère leurs lits |

### Pôles & Spé

Formations générales uniquement : une formation de période d'essai ou de
période de formation y est introuvable (`404`). `GET` est ouvert à tout compte
validé. Ajouter, modifier et supprimer une formation demandent « Gérer
l'hôpital » (rôle) ou un grade de la Direction. L'équipe (routes
`/employees/…`) se gère par la Direction (tous les rôles), le Responsable de la
formation (`second`, `validated`, `in_progress`) et ses Seconds (`validated`,
`in_progress`) ; chacun ne change ou ne retire que les membres dont il peut
donner le rôle (`403` sinon). Les super-admins ont tous les droits.

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/trainings` | Formations générales, employés actifs (compétences, grade, téléphone), rôles des équipes, droits qu'une formation peut donner, `can_manage` et `can_assign_lead` |
| `POST` | `/api/trainings` | Crée une formation générale : `name`, `emoji` (unique parmi toutes les formations), `category` (`pole` par défaut \| `specialty`), `permissions` (droits donnés : `training.validate`, `hospital.forensic`, `human_resources.manage`, `stock.manage`) |
| `PATCH` | `/api/trainings/{id}` | Modifie une formation ; un nouvel emoji remplace l'ancien chez les employés |
| `DELETE` | `/api/trainings/{id}` | Supprime la formation et retire son emoji des compétences |
| `PUT` | `/api/trainings/{id}/employees/{employee_id}` | Donne un rôle dans la formation : `status` facultatif (`validated` par défaut, `lead`, `second`, `in_progress`) |
| `DELETE` | `/api/trainings/{id}/employees/{employee_id}` | Retire l'employé de la formation et l'emoji de ses compétences |

### Formation

Toutes les routes demandent le droit « Formateur » (`403` sinon). Les modules et
les questions se gèrent par la Direction, « Gérer l'hôpital » ou le Responsable
du pôle qui donne le droit Formateur (`403` sinon). Une fiche ne se remplit que
pour un employé d'un grade « Période d'essai » ou « En formation », et seulement
pour son étape : modules, simulation et questionnaire (`409` sinon). Un emoji
est unique parmi toutes les formations et tous les modules.

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/formation` | Modules, questions, critères des deux simulations, fiches des deux étapes (progression, notes, statut, `can_pass_resident`, `can_complete`, `next_grade_name`), formations terminées, formateurs (mentors possibles), grades « Période d'essai » et « En formation », `can_manage` |
| `PATCH` | `/api/formation/{employee_id}` | `arrival_date` (fiche RH), `notes`, `mentor_ids` (formateurs), `simulation` ou `resident_simulation` selon l'étape (`{critère: 1 à 5}`) |
| `PUT` | `/api/formation/{employee_id}/modules/{module_id}` | Niveau `level` (0 à 3 en période d'essai, 0 à 2 en formation) ; l'emoji du module suit le niveau le plus haut |
| `PUT` | `/api/formation/{employee_id}/questions/{question_id}` | Bonne réponse ou non : `correct` (période d'essai) |
| `POST` | `/api/formation/{employee_id}/resident` | Passage au grade « En formation » (modules de période d'essai au plus haut, moyenne ≥ 14 ; `409` sinon) ; leurs emojis quittent les compétences. `{"force": true}` : validations basiques seules exigées, Direction ou Responsable du pôle Formation (`403` sinon) |
| `DELETE` | `/api/formation/{employee_id}/resident` | Annule le passage d'un employé « En formation » : grade d'avant (à défaut, le grade « Période d'essai » juste en dessous), ses emojis reviennent |
| `POST` | `/api/formation/{employee_id}/complete` | Fin de formation : grade au-dessus (formations obligatoires validées, simulation ≥ 14 ; `409` sinon) ; leurs emojis quittent les compétences. `{"force": true}` : formations obligatoires seules exigées, Direction ou Responsable du pôle Formation (`403` sinon) |
| `DELETE` | `/api/formation/{employee_id}/complete` | Annule la fin de formation : grade « En formation », ses emojis reviennent |
| `POST` | `/api/formation/modules` | Crée un module : `category` (`basics` \| `tools` \| `interventions` \| `injuries` pour la période d'essai, `mandatory` \| `optional` pour la formation), `name`, `emoji` facultatif |
| `PATCH` | `/api/formation/modules/{id}` | Modifie un module (sans changer d'étape) ; l'emoji est remplacé, ajouté ou retiré chez les employés |
| `DELETE` | `/api/formation/modules/{id}` | Supprime le module, les niveaux et son emoji des compétences |
| `POST` | `/api/formation/questions` | Crée une question : `question`, `answer` |
| `PATCH` | `/api/formation/questions/{id}` | Modifie une question |
| `DELETE` | `/api/formation/questions/{id}` | Supprime la question et les réponses |

---

## WebSocket

- **Endpoint** : `ws://<apiBase>/ws/dispatch` (et `wss://` en HTTPS ; chemin
  hors `/api`, donc **non** proxifié par Nitro - le client cible l'origine du
  backend directement).
- En production, `NUXT_PUBLIC_API_BASE` doit être l'URL HTTPS publique du
  backend (`API_URL` dans la configuration Docker/Coolify), pour les requêtes
  API directes et le WebSocket.
- **Authentification** : le cookie et l'accès Dispatch sont vérifiés avant
  l'`accept()`. En cas d'échec, la connexion est close avec le code `1008` (le client arrête
  alors de se reconnecter).
- **Messages serveur** : `{"type": "snapshot", "data": {slots, radios, state}}`
  envoyé à la connexion puis à chaque mutation REST ou changement de statut.
- **Keep-alive** : le client envoie `"ping"` toutes les 25 s, le serveur répond
  `{"type": "pong"}`.
- **Reconnexion** : back-off exponentiel (1 s → 30 s max).

---

## Tâches de fond

Deux tâches `asyncio` sont lancées au démarrage de l'API (lifespan FastAPI) et
arrêtées proprement à l'extinction.

| Tâche | Fichier | Rôle |
|---|---|---|
| Purge des comptes | `cleanup.py` | Supprime les comptes dont `prenom_rp` / `nom_rp` sont restés vides au-delà du délai. Intervalle : `CLEANUP_INTERVAL_SECONDS` (min 30 s). |
| Sync Google Sheet | `status_sync.py` | Lit l'export CSV du Sheet *Disponibilités LSES/BCES/SAFD* et met à jour `lses_status` / `safd_status`. |

### Mapping des statuts du Sheet

| Sheet (LSES) | Valeur API | Sheet (SAFD) | Valeur API |
|---|---|---|---|
| commence par `off` | `ferme` | nombre > 0 | `disponible` |
| contient 🌙 | `nuit` | nombre ≤ 0 / non numérique | `indisponible` |
| contient 🎙 | `ouvert` | | |
| autre | `bug` | | |

La tâche respecte les en-têtes HTTP : `Cache-Control: max-age` et `Retry-After`
allongent l'attente suivante en cas de `429` / `503`.

---

## Base de données

SQLite via SQLAlchemy 2 async. Le schéma est créé automatiquement au démarrage
(`init_db()`), sans Alembic : les tables manquantes sont créées, puis des
`ALTER TABLE` idempotents mettent à niveau les colonnes utilisateur et radio.
Les affectations et radios existantes sont recopiées vers les identifiants
d'employés.

### Tables

| Table | Contenu |
|---|---|
| `users` | Comptes Discord et accès : profil, `is_super_admin`, `status`, `last_login_at` (l'ancienne colonne `role_id` est reprise dans `user_roles` au démarrage, puis vidée) |
| `roles` | Rôles personnalisés et pages autorisées |
| `intervention_statuses` | Statuts d'intervention du Dispatch : `key` (valeur stockée dans `dispatch_slots.status`, fixe), `label`, `emoji`, `color` (facultative), `is_primo`, `kind` (`status` \| `place`, les statuts avant les lieux), `order` (dans son type) |
| `affiliation_groups` | Groupes d'appartenance proposés dans la Crise et la Morgue : `name`, `color` facultative (les fiches gardent leur appartenance en texte) |
| `user_roles` | Rôles de chaque compte : `user_id` → `users`, `role_id` → `roles` (cascade des deux côtés) |
| `employees` | Employés indépendants des comptes, compétences, grade et lien facultatif vers un compte |
| `grades` | Hiérarchie de service et permissions opérationnelles par grade ; `is_trial` (Période d'essai, formation initiale) et `is_training` (En formation, formation complémentaire), exclusifs sur un même grade |
| `trainings` | Formations de Pôles & Spé : `name`, `emoji` (unique, ajouté aux compétences de l'employé validé), `kind` (`general`), `category` (`pole` \| `specialty`), `permissions` (JSON, droits donnés à ceux qui l'ont validée) |
| `training_members` | Rôles dans une formation générale autres que « Validé » : `training_id` → `trainings`, `employee_id` → `employees`, `status` (`lead` \| `second` \| `in_progress`) |
| `intern_modules` | Modules de la page Formation : `category` (`basics` \| `tools` \| `interventions` \| `injuries` pour la période d'essai, `mandatory` \| `optional` pour la formation), `name`, `emoji` facultatif (unique) |
| `intern_questions` | Questionnaire de passage Résident : `question`, `answer` |
| `intern_records` | Fiche de formation : `employee_id` → `employees`, `notes`, `simulation` et `resident_simulation` (JSON, 1 à 5 par critère), `resident_at` et `previous_grade_id` (passage au grade « En formation » et grade d'avant), `completed_at` et `completed_from_grade_id` (fin de formation et grade d'avant) |
| `intern_mentors` | Mentors : `intern_id` et `mentor_id` → `employees` |
| `intern_module_levels` | Niveau d'un employé sur un module (1 à 3 en période d'essai, 1 à 2 en formation ; sans ligne : Non observé) |
| `intern_answers` | Bonnes réponses d'un Interne au questionnaire |
| `application_settings` | Paramètres généraux configurés dans Administration |
| `dispatch_slots` | Créneaux : `kind`, `title`, `status`, `zip_code`, `location`, `type_label`, `order` |
| `dispatch_employee_assignments` | Affectations : `slot_id` → `employee_id`, `order` (cascade `DELETE`) |
| `dispatch_radios` | Radios : `serial`, `employee_id`, `is_on`, `is_loading`, `is_direction` |
| `hospital_rooms` | Chambres de l’hôpital : `name`, `order` |
| `hospital_beds` | Lits : `room_id` → `hospital_rooms` (cascade), `label`, puis le patient : `patient_name` (vide si le lit est libre), `accident`, `arrival_date`, `care_done`, `police_status` (`none` \| `to_notify` \| `notified`), `reason` |
| `hospital_bed_reasons` | Raisons proposées pour la présence d’un patient dans un lit |
| `morgue_entries` | Défunts de la morgue : `death_date`, `identity`, `affiliation`, `info_shareable`, `autopsy_done`, `examiner_id` → `employees`, `emergency_contacts`, `recoverable`, `incinerated_at` (vide tant que le corps est en cellule) |
| `crisis_state` | Ligne unique `id = 1` : `zip_code` de la crise et `slot_id` → `dispatch_slots`, l'intervention « Primo » (vidée si elle est supprimée) |
| `crisis_members` | Équipe de crise : `employee_id` → `employees` (cascade), `is_primo` (un seul Primo) |
| `crisis_victims` | Blessés de la crise : `full_name`, `affiliation`, `coma`, `severe`, `unconscious`, `injuries`, `repatriating_doctor`, `treating_doctor`, `arrived_at`, `care_done`, `channel_added`, `bed_id` → `hospital_beds` (vidé si le lit est supprimé) |
| `dispatch_state` | Ligne unique `id = 1` : `hospital_status`, `lses_status`, `safd_status`, `freq_bces`, `freq_shared` (fréquences actuelles, vides tant qu'elles ne sont pas réglées ; bornes dans `application_settings`), `radio_codes` |

### Créneaux amorcés

| `kind` | `title` | `order` |
|---|---|---|
| `centrale` | Centrale | -100 |
| `hopital` | Hôpital | -90 |
| `astreinte` | Astreinte | -80 |
| `conges` | Congés | -70 |
| `ipt` | IPT | -60 |
| `astreinte-fin` | Astreinte fin de service | -50 |
| `pause` | Pause | -40 |

Le fichier de base est ignoré par git. Attention : la valeur par défaut de
`DATABASE_URL` pointe vers `BCES.db` alors que le `.env` local utilise
`bces21.db` - aligner les deux pour éviter un fichier non suivi.

---

## Frontend

### Pages

| Route | Fichier | Description |
|---|---|---|
| `/` | `app/pages/index.vue` | Connexion Discord, gestion des erreurs `?error=` / `?status=pending` |
| `/dispatch` | `app/pages/dispatch.vue` | Plateau de dispatch temps réel |
| `/crise` | `app/pages/crise.vue` | Gestion de crise : équipe et liste des blessés |
| `/hopital` | `app/pages/hopital.vue` | Hôpital : onglets Chambres et Morgue |
| `/stock` | `app/pages/stock.vue` | Stock du BCES (à venir) |
| `/agenda` | `app/pages/agenda.vue` | Agenda partagé |
| `/poles-specialites` | `app/pages/poles-specialites.vue` | Pôles & Spé : formations générales, leurs équipes et les droits qu'elles donnent |
| `/formation` | `app/pages/formation.vue` | Formation (formateurs) : fiches de formation, période d'essai puis période de formation (`FormationPanel.vue`) |
| `/ressources-humaines` | `app/pages/ressources-humaines.vue` | Employés, rôles et accès (selon les droits) |
| `/complete-profile` | `app/pages/complete-profile.vue` | Formulaire prénom RP / nom RP / téléphone avec compte à rebours |

Le middleware global vérifie `/api/me` avant l'accès aux pages privées. Les
permissions sont aussi contrôlées par les dépendances FastAPI.

Dispatch, Crise, Hôpital, Agenda, Stock et Pôles & Spé n'ont pas de case dans les « Pages
accessibles » des rôles : ils sont ouverts à tout compte validé, même sans rôle
(`OPEN_PAGES` dans `backend/app/deps.py`). Formation n'a pas de case non plus : elle
s'ouvre avec le droit « Formateur ». Un compte en attente ou désactivé reçoit
un `403` sur `/api/me` et repart vers la connexion. Les rôles ne cochent que
Direction et Administration (Ressources humaines suit le droit RH, voir
Pôles & Spé) ; au démarrage, les pages qui
ne sont plus à cocher sont retirées des rôles existants. Un compte à plusieurs
rôles cumule leurs pages et leurs permissions. Les super-admins ont accès à
tout.

### Composables

| Fichier | Rôle |
|---|---|
| `useDispatchApi.ts` | Couche API : `fetchSnapshot`, `createSlot`, `updateSlot`, `deleteSlot`, `assignUser`, `unassignUser`, `updateRadio`, `updateState` |
| `useDispatchStore.ts` | État global via `useState` : snapshot, slots, radios, état, connexion |
| `useDispatchSocket.ts` | Client WebSocket : connexion, ping, back-off de reconnexion |
| `useToastStore.ts` | File de notifications (pause/reprise des minuteries, max 6) |
| `useAppToast.ts` | Facade `info` / `success` / `error` / `warning` |
| `useTimezone.ts` | Formatage des dates dans le fuseau du navigateur |
| `useSyncApi.ts` | Synchronisation des données avec le backend |

### Composants

| Composant | Description |
|---|---|
| `Sidebar.vue` | Navigation latérale selon les permissions, sélecteur de mode, déconnexion |
| `DispatchHeader.vue` | Fréquences, statut Hôpital, puces LSES / SAFD |
| `SlotPanel.vue` | Zone de dépôt d'agents pour un créneau de service |
| `InterventionCard.vue` | Carte d'intervention (statut, code postal, agents) |
| `AgentTile.vue` | Tuile agent compacte (nom, compétences, indicatif radio) |
| `RadioPanel.vue` | Colonne radios (marche/arrêt, série, agent, fréquences) |
| `RoomsPanel.vue` | Onglet Chambres de la page Hôpital : chambres, lits, affectation des patients, raisons proposées |
| `MorguePanel.vue` | Onglet Morgue de la page Hôpital : cases des corps et des urnes, ajout, modification, incinération, retrait |
| `ChoiceField.vue` | Liste de choix non exhaustive, avec « Autre… » pour une saisie libre |
| `StatusPicker.vue` | Liste déroulante des statuts d'intervention gérés dans Administration (statuts et lieux), teintée par la couleur du statut |
| `ZipPicker.vue` | Saisie du code postal (validation différée 400 ms) |
| `ToastStack.vue` | Pile de notifications (bas droite) |
| `EmptySlotState.vue` | Message d'état vide |
| `DiscordButton.vue` | Bouton OAuth Discord |
| `AppLogo.vue`, `RadioCard.vue` | Composants non utilisés (code mort) |

### Styles

- `app/assets/css/main.css` : thème global `--bces-*`, resets, classes utilitaires
  (`.bces-card`, `.bces-btn`, `.bces-field`, `.bces-toast*`…).
- `app/assets/css/dispatch.css` : palette `--dp-*` du dispatch, activée par
  `body[data-layout='dispatch']` (posé par le layout `dispatch`).
- Les composants utilisent du CSS scoped avec un préfixe BEM par bloc
  (`.iv`, `.at`, `.sp`, `.zp`, `.lp`, `.rp`, `.rc`, `.dh`, `.dp`…).
- Tailwind 4 est chargé (`@import "tailwindcss"`) mais le code s'appuie
  principalement sur ces CSS maison ; aucun composant `U*` de Nuxt UI n'est
  utilisé.

### Icônes

Les icônes utilisent `@nuxt/icon` avec le jeu `lucide:` servi localement
(`@iconify-json/lucide` + `icon.localApiEndpoint: '/_nuxt_icon'`) : aucune
requête CDN.

---

## Sécurité

Points à vérifier avant une mise en production :

- **`SESSION_SECRET`** doit être remplacé par une valeur aléatoire
  (`openssl rand -hex 32`). La valeur par défaut rend les sessions falsifiables.
- **`SESSION_COOKIE_SECURE=true`** obligatoire derrière HTTPS.
- **Discord Client ID / Secret** : ne jamais versionner le `.env` (il est ignoré
  par git) ; les faire tourner en cas de fuite.
- **CORS** : `allow_credentials=True` avec une liste d'origines explicite
  (jamais `*`).
- **OAuth `state`** stocké en mémoire : l'API doit tourner avec **un seul
  worker** (`uvicorn main:app` sans `--workers > 1`), sinon le `state` peut
  résider sur un autre processus.
- **Permissions par page** : les rôles applicatifs sont configurés dans
  Administration ; les permissions opérationnelles dépendent du grade et sont
  vérifiées par l’API. Le premier compte est le super-admin initial.
- **Cookie** : `SESSION_COOKIE_NAME` n'est honoré qu'à l'écriture ; la
  dépendance REST lit en dur le nom `bces_session`.
- **Dépendances** : `backend/requirements.txt` n'épingle pas les versions
  (bornes `>=` uniquement).

---

## Licence

Voir [LICENCE.md](LICENCE.md) - Axioneer Studio Source-Available License (AS-SAL) v1.3.
