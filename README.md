# bces21-dispatch

Application dispatch BCES - frontend Nuxt 4 + backend FastAPI (Discord OAuth).

## Structure

```
.
├── frontend/   # Nuxt 4 (UI, pages auth, dashboard)
└── backend/    # FastAPI (Discord OAuth + DB)
```

## Frontend (Nuxt)

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
```

Variables `.env` (optionnel) :

| Variable | Défaut |
|---|---|
| `NUXT_PUBLIC_API_BASE` | `http://127.0.0.1:8000` |
| `NUXT_PUBLIC_DISCORD_LOGIN_URL` | `/api/auth/discord/login` |
| `NUXT_PUBLIC_DISCORD_REGISTER_URL` | `/api/auth/discord/register` |

## Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env   # renseigner DISCORD_CLIENT_ID / SECRET
.venv\Scripts\python -m uvicorn main:app --reload
# http://localhost:8000
```

### Configuration Discord

1. https://discord.com/developers/applications → New Application
2. OAuth2 → Redirects → ajouter `http://localhost:8000/api/auth/discord/callback`
3. Copier `Client ID` et `Client Secret` dans `backend/.env`

### Endpoints

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/auth/discord/login` | Initie OAuth (état `login`) |
| `GET` | `/api/auth/discord/register` | Initie OAuth (état `register`) |
| `GET` | `/api/auth/discord/callback` | Callback OAuth (échange code, crée/relie le compte) |
| `POST` | `/api/auth/profile` | Définit Prénom RP / Nom RP |
| `POST` | `/api/auth/logout` | Détruit la session |
| `GET` | `/api/me` | Renvoie l'utilisateur courant |
| `GET` | `/health` | Santé

### Comptes incomplets

À la connexion Discord (état `register`), un compte est créé avec un délai de
`PROFILE_DEADLINE_SECONDS` (défaut `86400` = 1 jour). Une tâche de fond
s'exécute toutes les `CLEANUP_INTERVAL_SECONDS` (défaut `1800`) et supprime
les comptes dont `prenom_rp` / `nom_rp` sont toujours `NULL` et dont la
deadline est dépassée.

La session est un cookie `HttpOnly` (`bces_session`) signé JWT (HS256).