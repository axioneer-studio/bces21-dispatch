# BCES Dispatch

Application de dispatch du BCES : tableau de bord temps réel des agents, des interventions et des radios, avec authentification Discord OAuth2.

- **Frontend** : Nuxt 4 (Vue 3) + Tailwind CSS 4 + `@nuxt/ui`
- **Backend** : FastAPI (Python 3.11+) + SQLAlchemy 2 async + SQLite
- **Temps réel** : WebSocket (`/ws/dispatch`)

---

## Démarrage rapide

Trois méthodes sont disponibles :

### 1. Launcher Rust (`bces-dev`) - recommandé

Le launcher gère automatiquement le venv Python, les dépendances, le `.env` et lance les deux services dans des consoles séparées (`Windows/Linux/WSL`).

Depuis le dossier `launcher/` :

**Compilation puis exécution (mode release, recommandé) :**
```powershell
# Windows
cd .\launcher
cargo build --release
.\target\release\bces-dev.exe start
.\target\release\bces-dev.exe status
.\target\release\bces-dev.exe stop
```

```bash
# Linux / WSL
cd ./launcher
cargo build --release
./target/release/bces-dev start
./target/release/bces-dev status
./target/release/bces-dev stop
```

**Ou compilation et exécution en une seule commande (mode debug) :**
```powershell
# Windows
cd .\launcher
cargo run
cargo run -- status
cargo run -- stop
```

```bash
# Linux / WSL
cd ./launcher
cargo run
cargo run -- status
cargo run -- stop
```

Détails complets : [launcher/README.md](launcher/README.md)

### 2. Scripts `dev.ps1` / `dev.sh`

**Windows** (PowerShell) :
```powershell
.\dev.ps1
```

**Linux / WSL** :
```bash
chmod +x dev.sh
./dev.sh
```

Ces scripts vérifient automatiquement `.env`, le venv Python, les dépendances npm et lancent backend + frontend. `Ctrl+C` arrête les deux services.

### 3. Manuel

**Backend**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# renseigner DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, SESSION_SECRET
uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

Le proxy `/api/**` pointe automatiquement sur `http://localhost:8000`.

---

- Application : <http://localhost:3000>
- API : <http://localhost:8000>
- Documentation interactive : <http://localhost:8000/docs>

---

## Docker (Coolify)

Le dépôt inclut un `docker-compose.yml` et un Dockerfile par application. Créez une ressource **Docker Compose** depuis le dépôt dans Coolify et renseignez :

- `DATABASE_URL` (ex. `sqlite+aiosqlite:////app/data/BCES.db`)
- `DISCORD_CLIENT_ID` et `DISCORD_CLIENT_SECRET`
- Ajoutez `https://<domaine-frontend>/auth/discord/callback` aux Redirect URI de l'application Discord

`SESSION_SECRET` est généré automatiquement par Coolify.

---

## Configuration

### Backend (`backend/.env`)

| Variable | Défaut | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./BCES.db` | URL SQLAlchemy async |
| `DISCORD_CLIENT_ID` | - | Identifiant de l'application Discord |
| `DISCORD_CLIENT_SECRET` | - | Secret de l'application Discord |
| `SESSION_SECRET` | `change-me-in-production` | Clé de signature des JWT (**à changer en prod**) |
| `FRONTEND_BASE_URL` | `http://localhost:3000` | Base des redirections OAuth |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Origines autorisées |
| `APP_TIMEZONE` | `Europe/Paris` | Fuseau serveur |
| `SESSION_TTL_SECONDS` | `1209600` | Durée de vie de la session (14 j) |

Générer un secret de session : `openssl rand -hex 32`

### Frontend (`frontend/.env` ou `runtimeConfig.public`)

| Variable | Défaut | Description |
|---|---|---|
| `NUXT_PUBLIC_API_BASE` | `http://localhost:8000` | Base de l'API backend |
| `NUXT_PUBLIC_DISCORD_AUTH_URL` | `/api/auth/discord/url` | Endpoint d'initiation OAuth |
| `NUXT_PUBLIC_TIMEZONE` | `Europe/Paris` | Fuseau de repli |

---

## Authentification Discord

1. <https://discord.com/developers/applications> → **New Application**
2. **OAuth2 → Redirects** → ajouter `http://localhost:3000/auth/discord/callback`
3. Copier le **Client ID** et le **Client Secret** dans `backend/.env`
4. Lancer le backend puis ouvrir <http://localhost:3000>

Le premier compte créé est automatiquement validé et reçoit les droits super-admin. Un compte validé accède au Dispatch, à la Crise, à l'Hôpital, à l'Agenda et au Stock, même sans rôle.

---

## Pages principales

| Route | Description |
|---|---|
| `/` | Connexion Discord |
| `/dispatch` | Plateau de dispatch temps réel (agents, interventions, radios) |
| `/crise` | Gestion de crise : équipe et liste des blessés |
| `/hopital` | Chambres/lits et morgue |
| `/agenda` | Agenda partagé |
| `/stock` | Stock du BCES (à venir) |
| `/poles-specialites` | Formations générales, équipes et droits associés |
| `/formation` | Fiches de formation (formateurs uniquement) |
| `/ressources-humaines` | Employés, compétences et lien aux comptes |
| `/direction` | Grades et permissions opérationnelles |
| `/administration` | Utilisateurs, rôles, inscriptions, paramètres généraux |
| `/complete-profile` | Prénom RP / nom RP / téléphone (obligatoire, délai 24 h) |

---

## Stack technique

| Couche | Technologies |
|---|---|
| Frontend | Nuxt 4, Vue 3, Tailwind CSS 4, `@nuxt/ui`, `@nuxt/icon` (Lucide, local) |
| Backend | FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2 (async), aiosqlite, PyJWT |
| Auth | Discord OAuth2 + JWT HS256 en cookie `HttpOnly` |
| Temps réel | WebSocket natif FastAPI |
| Base | SQLite (fichier `backend/BCES.db`) |

---

## Sécurité (avant production)

- Remplacer `SESSION_SECRET` par une valeur aléatoire (`openssl rand -hex 32`)
- Passer `SESSION_COOKIE_SECURE=true` derrière HTTPS
- Ne jamais versionner le `.env` (ignoré par git) ; tourner les identifiants Discord en cas de fuite
- CORS avec une liste d'origines explicite (jamais `*`)
- L'API doit tourner avec un seul worker (l'état OAuth `state` est stocké en mémoire)

---

## Licence

Voir [LICENCE.md](LICENCE.md) - Axioneer Studio Source-Available License (AS-SAL) v1.3.
