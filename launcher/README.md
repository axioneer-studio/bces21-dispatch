# BCES Dev Launcher

Petit gestionnaire Rust pour démarrer et arrêter le backend FastAPI et le frontend Nuxt de BCES Dispatch.

## Prérequis

- Rust stable (pour compiler le launcher)
- Python 3.11+
- Node.js et npm
- `backend/requirements.txt`
- `frontend/package.json`

Le launcher doit être compilé et exécuté dans le même environnement que les runtimes :
- PowerShell / Windows : Python Windows + Node.js Windows.
- WSL / Linux : Python Linux + Node.js Linux.

Ne réutilisez jamais un virtualenv Windows dans WSL, ni l'inverse.

## Compilation

Depuis le dossier `launcher/` :

```powershell
cargo build --release
```

Sous Linux / WSL :

```bash
cargo build --release
```

L'exécutable est créé dans `target/release/` (`bces-dev.exe` sous Windows, `bces-dev` sous Linux).

## Utilisation

Depuis la racine du dépôt :

```powershell
.\launcher\target\release\bces-dev.exe start
.\launcher\target\release\bces-dev.exe status
.\launcher\target\release\bces-dev.exe stop
```

Sous Linux / WSL :

```bash
./launcher/target/release/bces-dev start
./launcher/target/release/bces-dev status
./launcher/target/release/bces-dev stop
```

Le launcher affiche les logs des deux services dans le même terminal, avec les préfixes `[BACKEND]` et `[FRONTEND]`. `Ctrl+C` arrête les deux arbres de processus. `stop` permet également de les arrêter depuis un autre terminal.

## Virtualenv Python

- Windows : `backend/.venv/Scripts/python.exe`
- Linux / WSL : `~/.cache/bces-dev/<project-id>/venv/bin/python`

Les dépendances Python sont réinstallées seulement lorsque le contenu de `requirements.txt` change.

Le launcher crée `backend/.env` depuis `backend/.env.example` si nécessaire. Vérifiez ensuite les variables d'environnement.

## Notes

- Le port 8000 et le port 3000 doivent être libres.
- Le launcher n'installe pas Python, Node.js, Rust ou des paquets système.
- Les dépendances npm sont installées avec `npm ci` lorsqu'un `package-lock.json` est présent, sinon `npm install`.


## Running from the launcher directory

The launcher automatically searches the current directory and its parent directories for `backend/requirements.txt` and `frontend/package.json`. You can therefore run it from either the repository root or `launcher/`.

You can also specify the project root explicitly:

```powershell
cargo run -- --root "A:\kDrive\Développement\axioneer-studio\bces21-dispatch" start
```
