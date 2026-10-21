# BCES Dispatch

Application de dispatch du BCES : tableau de bord temps réel des agents, des
interventions et des radios, avec authentification Discord OAuth2.

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
- Statut d'intervention (27 statuts + 12 lieux, avec emoji) et code postal par carte.
- Panneau **Radios** : marche/arrêt, numéro de série éditable, agent associé,
  fréquences 147 / 570 MHz, état « attente » (chargement 2,5 s).
- En-tête d'état : fréquences radio, statut Hôpital (ouvert / fermé / nuit),
  puces **LSES** et **SAFD** en lecture seule (synchronisées depuis un Google Sheet).
- Mises à jour temps réel via WebSocket, sans rafraîchissement de page.

### Tableau de bord (`/dashboard`)

- KPI : agents affectés, agents disponibles, interventions, radios actives.
- Panneau « service en cours » avec accès rapide au dispatch.

### Comptes

- Connexion Discord OAuth2 (création de compte automatique à la première connexion).
- Complétion du profil (prénom RP / nom RP / téléphone) obligatoire, avec délai de 24 h.
- Brouillon de profil sauvegardé en `localStorage` (`bces:profile-draft`).
- Comptes en attente de validation : liste et approbation par un membre validé.

### Interface

- Thème sombre, palette `--bces-*` (écrans d'auth) et `--dp-*` (dispatch).
- Notifications (toasts) avec pause au survol, icônes Lucide servies en local.
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
│   ├── dispatch.py     # routes /api/dispatch/* + WebSocket
│   ├── cleanup.py      # purge des comptes incomplets
│   ├── status_sync.py  # synchronisation Google Sheet (LSES / SAFD)
│   └── auth/
│       ├── router.py   # routes /api/auth/*
│       ├── discord.py  # client OAuth2 Discord
│       └── session.py  # émission / vérification du JWT de session
│
├── frontend/           # application Nuxt 4
│   ├── nuxt.config.ts
│   ├── server/routes/favicon.ico.ts
│   ├── public/         # logo, fond, robots.txt
│   └── app/
│       ├── pages/      # /, /dashboard, /dispatch, /complete-profile
│       ├── layouts/    # default, dispatch
│       ├── components/ # 14 composants auto-importés
│       ├── composables/# useDispatchApi, useDispatchStore, useDispatchSocket, …
│       ├── utils/      # agent, locations, statuses, toast
│       ├── types/      # types partagés (non auto-importés)
│       └── assets/css/ # main.css (thème global), dispatch.css (palette dispatch)
│
├── .github/ISSUE_TEMPLATE/
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

### Backend — `backend/.env`

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
| `DISCORD_REDIRECT_URI` | `http://localhost:8000/api/auth/discord/callback` | URI de redirection OAuth |
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

### Frontend — variables `NUXT_PUBLIC_*`

Le front ne lit pas de fichier `.env` en développement : tout passe par
`runtimeConfig.public` dans `nuxt.config.ts`, surchargé par des variables
d'environnement.

| Variable | Défaut | Description |
|---|---|---|
| `NUXT_PUBLIC_API_BASE` | `http://localhost:8000` | Base de l'API backend |
| `NUXT_PUBLIC_DISCORD_AUTH_URL` | `/api/auth/discord/start` | Endpoint d'initiation OAuth |
| `NUXT_PUBLIC_TIMEZONE` | `Europe/Paris` | Fuseau de repli si le navigateur n'en expose pas |

```bash
# frontend/.env
NUXT_PUBLIC_API_BASE=http://localhost:8000
NUXT_PUBLIC_DISCORD_AUTH_URL=/api/auth/discord/start
NUXT_PUBLIC_TIMEZONE=Europe/Paris
```

---

## Authentification Discord

1. <https://discord.com/developers/applications> → **New Application**
2. **OAuth2 → Redirects** → ajouter `http://localhost:8000/api/auth/discord/callback`
3. Copier le **Client ID** et le **Client Secret** dans `backend/.env`
4. Lancer le backend puis ouvrir <http://localhost:3000>

### Déroulé

1. `GET /api/auth/discord/start` → génération d'un `state` (TTL 10 min, en
   mémoire) et redirection vers Discord.
2. `GET /api/auth/discord/callback` → échange du `code`, récupération du profil
   Discord, création ou mise à jour de l'utilisateur, pose du cookie de session.
3. Redirection selon l'état du compte :
   - profil incomplet → `/complete-profile?deadline=<iso>`
   - compte en attente → `/?status=pending`
   - compte valide → `/dashboard`
4. La **session** est un JWT HS256 (`sub`, `iat`, `exp`, `type`) stocké dans un
   cookie `HttpOnly` `bces_session` (`SameSite=Lax`, `Path=/`).

> Le premier compte créé est automatiquement validé (compte « fondateur »).

---

## API REST

Toutes les routes sauf `/`, `/health`, `/api/auth/discord/start`,
`/api/auth/discord/callback` et `/api/auth/logout` exigent une session valide.
Un compte en attente de validation reçoit un `403`.

### Authentification & comptes

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/` | Nom et version de l'API |
| `GET` | `/health` | Santé (`status`, `version`, `timezone`) |
| `GET` | `/api/me` | Utilisateur courant |
| `GET` | `/api/auth/discord/start` | Initie le flux OAuth Discord |
| `GET` | `/api/auth/discord/callback` | Callback OAuth (échange du code, pose de la session) |
| `POST` | `/api/auth/profile` | Enregistre prénom RP / nom RP / téléphone |
| `POST` | `/api/auth/logout` | Détruit la session |
| `GET` | `/api/auth/pending` | Liste des comptes en attente de validation |
| `POST` | `/api/auth/validate/{user_id}` | Valide un compte en attente |
| `GET` | `/api/users` | Liste des agents (Roster) |

### Dispatch

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/dispatch/snapshot` | Slots + radios + état courant |
| `POST` | `/api/dispatch/slots` | Crée un slot (`kind`: `intervention` \| `consultation`) |
| `PATCH` | `/api/dispatch/slots/{id}` | Modifie un slot (titre, statut, code postal, lieu, type) |
| `DELETE` | `/api/dispatch/slots/{id}` | Supprime un slot (et ses affectations) |
| `POST` | `/api/dispatch/slots/{id}/assign` | Affecte un agent (`user_id`) |
| `DELETE` | `/api/dispatch/slots/{id}/assign/{user_id}` | Désaffecte un agent |
| `PATCH` | `/api/dispatch/radios/{id}` | Modifie une radio (série, agent, marche, chargement) |
| `PATCH` | `/api/dispatch/state` | Statut Hôpital (`ouvert` \| `ferme` \| `nuit`) et codes radio |

> `lses_status` et `safd_status` ne sont **pas** modifiables via l'API : ils sont
> pilotés par la synchronisation Google Sheet.

---

## WebSocket

- **Endpoint** : `ws://<apiBase>/ws/dispatch` (chemin hors `/api`, donc **non**
  proxifié par Nitro — le client cible l'origine du backend directement).
- **Authentification** : le cookie de session est vérifié avant l'`accept()`.
  En cas d'échec, la connexion est close avec le code `1008` (le client arrête
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
`ALTER TABLE` idempotents ajoutent les colonnes `phone`, `status` et
`competencies` si elles n'existent pas encore.

### Tables

| Table | Contenu |
|---|---|
| `users` | Comptes Discord : `discord_id`, `discord_username`, `discord_avatar`, `prenom_rp`, `nom_rp`, `phone`, `status` (`active` \| `pending`), `competencies` (JSON texte), `rp_name_deadline`, `last_login_at` |
| `dispatch_slots` | Créneaux : `kind`, `title`, `status`, `zip_code`, `location`, `type_label`, `order` |
| `dispatch_assignments` | Affectations : `slot_id` → `user_id`, `order` (cascade `DELETE`) |
| `dispatch_radios` | Radios : `serial`, `doctor_id`, `is_on`, `is_loading`, `frequency`, `common_frequency`, `is_direction` |
| `dispatch_state` | Ligne unique `id = 1` : `hospital_status`, `lses_status`, `safd_status`, `freq_147`, `freq_570`, `radio_codes` |

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
`bces21.db` — aligner les deux pour éviter un fichier non suivi.

---

## Frontend

### Pages

| Route | Fichier | Description |
|---|---|---|
| `/` | `app/pages/index.vue` | Connexion Discord, gestion des erreurs `?error=` / `?status=pending` |
| `/dashboard` | `app/pages/dashboard.vue` | KPI du roster et service en cours |
| `/dispatch` | `app/pages/dispatch.vue` | Plateau de dispatch temps réel |
| `/complete-profile` | `app/pages/complete-profile.vue` | Formulaire prénom RP / nom RP / téléphone avec compte à rebours |

La protection des pages est faite dans chaque page via `useAsyncData('/api/me')`
puis `navigateTo('/')` — il n'y a pas de middleware global.

### Composables

| Fichier | Rôle |
|---|---|
| `useDispatchApi.ts` | Couche API : `fetchSnapshot`, `createSlot`, `updateSlot`, `deleteSlot`, `assignUser`, `unassignUser`, `updateRadio`, `updateState` |
| `useDispatchStore.ts` | État global via `useState` : snapshot, slots, radios, état, connexion |
| `useDispatchSocket.ts` | Client WebSocket : connexion, ping, back-off de reconnexion |
| `useToastStore.ts` | File de notifications (pause/reprise des minuteries, max 6) |
| `useAppToast.ts` | Facade `info` / `success` / `error` / `warning` |
| `useTimezone.ts` | Formatage des dates dans le fuseau du navigateur |

### Composants

| Composant | Description |
|---|---|
| `Sidebar.vue` | Navigation latérale (Dashboard / Dispatch), sélecteur de mode d'affichage, déconnexion |
| `DispatchHeader.vue` | Fréquences, statut Hôpital, puces LSES / SAFD |
| `SlotPanel.vue` | Zone de dépôt d'agents pour un créneau de service |
| `InterventionCard.vue` | Carte d'intervention (statut, code postal, agents) |
| `AgentTile.vue` | Tuile agent compacte (nom, compétences, indicatif radio) |
| `RadioPanel.vue` | Colonne radios (marche/arrêt, série, agent, fréquences) |
| `StatusPicker.vue` | Liste déroulante statuts + lieux |
| `ZipPicker.vue` | Saisie du code postal (validation différée 400 ms) |
| `ToastStack.vue` | Pile de notifications (bas droite) |
| `EmptySlotState.vue` | Message d'état vide |
| `DiscordButton.vue` | Bouton OAuth Discord |
| `AppLogo.vue`, `LocationPicker.vue`, `RadioCard.vue` | Composants non utilisés (code mort) |

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

- **`SESSION_SECRET`** doit être replaced par une valeur aléatoire
  (`openssl rand -hex 32`). La valeur par défaut rend les sessions falsifiables.
- **`SESSION_COOKIE_SECURE=true`** obligatoire derrière HTTPS.
- **Discord Client ID / Secret** : ne jamais versionner le `.env` (il est ignoré
  par git) ; les faire tourner en cas de fuite.
- **CORS** : `allow_credentials=True` avec une liste d'origines explicite
  (jamais `*`).
- **OAuth `state`** stocké en mémoire : l'API doit tourner avec **un seul
  worker** (`uvicorn main:app` sans `--workers > 1`), sinon le `state` peut
  résider sur un autre processus.
- **Modèle de rôles absent** : tout utilisateur authentifié et validé peut
  lister (`/api/auth/pending`) et approuver (`/api/auth/validate/{id}`) des
  comptes. À restreindre si l'usage grandit.
- **Cookie** : `SESSION_COOKIE_NAME` n'est honoré qu'à l'écriture ; la
  dépendance REST lit en dur le nom `bces_session`.
- **Dépendances** : `backend/requirements.txt` n'épingle pas les versions
  (bornes `>=` uniquement).

---

## Licence

Voir [LICENCE.md](LICENCE.md) — Axioneer Studio Source-Available License (AS-SAL) v1.3.
