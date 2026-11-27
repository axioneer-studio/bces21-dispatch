
#!/usr/bin/env bash
set -Eeuo pipefail

###############################################################################
# dev.sh
# Starts the FastAPI backend and Nuxt frontend in development mode.
# Automatically checks and installs missing dependencies.
###############################################################################

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

VENV_DIR="$BACKEND/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

BACKEND_ENV="$BACKEND/.env"
BACKEND_ENV_EXAMPLE="$BACKEND/.env.example"
FRONTEND_ENV="$FRONTEND/.env"

BACKEND_PID=""
FRONTEND_PID=""
CLEANING_UP=false

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log() {
    echo "[dev] $*"
}

warn() {
    echo "[dev] WARNING: $*" >&2
}

die() {
    echo "[dev] ERROR: $*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Process cleanup
# ---------------------------------------------------------------------------

cleanup() {
    if [[ "$CLEANING_UP" == "true" ]]; then
        return
    fi

    CLEANING_UP=true

    log "Stopping services..."

    for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
        if [[ -n "$pid" ]]; then
            wait "$pid" 2>/dev/null || true
        fi
    done

    log "Services stopped."
}

handle_signal() {
    cleanup
    exit 130
}

trap cleanup EXIT
trap handle_signal INT TERM

# ---------------------------------------------------------------------------
# Command verification
# ---------------------------------------------------------------------------

require_cmd() {
    local command="$1"
    local hint="$2"

    if ! command -v "$command" >/dev/null 2>&1; then
        die "$command not found. $hint"
    fi
}

require_cmd npm "Install Node.js and npm."
require_cmd python3 "Install Python 3.11 or newer."

# ---------------------------------------------------------------------------
# Directory verification
# ---------------------------------------------------------------------------

if [[ ! -d "$BACKEND" ]]; then
    die "Backend directory not found: $BACKEND"
fi

if [[ ! -d "$FRONTEND" ]]; then
    die "Frontend directory not found: $FRONTEND"
fi

# ---------------------------------------------------------------------------
# Environment files
# ---------------------------------------------------------------------------

if [[ ! -f "$BACKEND_ENV" ]]; then
    if [[ -f "$BACKEND_ENV_EXAMPLE" ]]; then
        log "Creating backend/.env from .env.example"

        cp "$BACKEND_ENV_EXAMPLE" "$BACKEND_ENV"

        warn "Configure DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET and SESSION_SECRET in backend/.env."
    else
        die "backend/.env and backend/.env.example are missing."
    fi
fi

if [[ ! -f "$FRONTEND_ENV" ]]; then
    log "frontend/.env is missing (optional)."
fi

# ---------------------------------------------------------------------------
# Critical environment variables
# ---------------------------------------------------------------------------

missing=()

for key in DISCORD_CLIENT_ID DISCORD_CLIENT_SECRET SESSION_SECRET; do
    value=""

    line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$BACKEND_ENV" 2>/dev/null | head -n 1 || true)"

    if [[ -n "$line" ]]; then
        value="${line#*=}"

        # Remove surrounding whitespace.
        value="$(printf '%s' "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

        # Remove surrounding quotes.
        if [[ "$value" == \"*\" ]]; then
            value="${value#\"}"
            value="${value%\"}"
        elif [[ "$value" == \'*\' ]]; then
            value="${value#\'}"
            value="${value%\'}"
        fi
    fi

    if [[ -z "$value" || "$value" == \#* ]]; then
        missing+=("$key")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    missing_string="$(IFS=', '; echo "${missing[*]}")"

    warn "$missing_string is missing or empty in backend/.env."
    warn "Discord authentication will not work until these variables are configured."
fi

# ---------------------------------------------------------------------------
# Python virtual environment
# ---------------------------------------------------------------------------

USE_SYSTEM_PYTHON=false

remove_venv() {
    local directory="$1"

    if [[ -d "$directory" ]]; then
        chmod -R u+w "$directory" 2>/dev/null || true
        rm -rf "$directory"
    fi
}

create_venv() {
    log "Creating Python virtual environment..."

    if python3 -m venv "$VENV_DIR"; then
        return 0
    fi

    warn "Virtual environment creation failed. Checking system packages..."

    if command -v apt-get >/dev/null 2>&1; then
        if command -v sudo >/dev/null 2>&1; then
            sudo apt-get update -qq &&
                sudo apt-get install -y -qq python3-venv
        elif [[ "$(id -u)" -eq 0 ]]; then
            apt-get update -qq &&
                apt-get install -y -qq python3-venv
        else
            warn "Install python3-venv manually using your package manager."
            return 1
        fi

    elif command -v apk >/dev/null 2>&1; then
        if command -v sudo >/dev/null 2>&1; then
            sudo apk add py3-virtualenv
        elif [[ "$(id -u)" -eq 0 ]]; then
            apk add py3-virtualenv
        else
            warn "Install Python virtual environment support manually."
            return 1
        fi
    else
        warn "No supported package manager found."
        return 1
    fi

    python3 -m venv "$VENV_DIR"
}

if [[ ! -x "$VENV_PYTHON" ]]; then
    if [[ -d "$VENV_DIR" ]]; then
        log "Removing incomplete or corrupted virtual environment..."
        remove_venv "$VENV_DIR"
    fi

    if ! create_venv; then
        die "Unable to create Python virtual environment. Install python3-venv and retry."
    fi
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    die "Python executable not found in virtual environment."
fi

# ---------------------------------------------------------------------------
# Python environment verification
# ---------------------------------------------------------------------------

if ! "$VENV_PYTHON" -c 'import sys; sys.exit(0)' 2>/dev/null; then
    warn "Virtual environment is corrupted. Recreating..."

    remove_venv "$VENV_DIR"

    if ! python3 -m venv "$VENV_DIR"; then
        die "Unable to recreate Python virtual environment."
    fi
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    die "Python virtual environment is unavailable."
fi

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------

REQUIREMENTS="$BACKEND/requirements.txt"

if [[ ! -f "$REQUIREMENTS" ]]; then
    die "backend/requirements.txt not found."
fi

if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
    log "Installing pip through ensurepip..."

    "$VENV_PYTHON" -m ensurepip --upgrade || {
        die "pip is unavailable. Reinstall Python with venv and ensurepip support."
    }
fi

log "Checking Python dependencies..."

if ! "$VENV_PYTHON" -c 'import fastapi, uvicorn, pydantic_settings, sqlalchemy, aiosqlite, httpx, jwt' 2>/dev/null; then
    log "Installing Python dependencies..."

    "$VENV_PYTHON" -m pip install --upgrade pip

    "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS"

    if ! "$VENV_PYTHON" -c 'import fastapi, uvicorn, pydantic_settings, sqlalchemy, aiosqlite, httpx, jwt' 2>/dev/null; then
        die "Python dependency verification failed."
    fi
else
    log "Python dependencies are already installed."
fi

# ---------------------------------------------------------------------------
# Frontend dependencies
# ---------------------------------------------------------------------------

if [[ ! -f "$FRONTEND/package.json" ]]; then
    die "frontend/package.json not found."
fi

if [[ ! -d "$FRONTEND/node_modules" ]]; then
    log "Installing frontend dependencies..."

    (
        cd "$FRONTEND"
        npm install
    )
else
    log "Frontend dependencies are already installed."
fi

# ---------------------------------------------------------------------------
# Port verification
# ---------------------------------------------------------------------------

check_port() {
    local port="$1"

    if command -v ss >/dev/null 2>&1; then
        if ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"; then
            warn "Port $port is already in use."
        fi

    elif command -v lsof >/dev/null 2>&1; then
        if lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
            warn "Port $port is already in use."
        fi
    fi
}

check_port 8000
check_port 3000

# ---------------------------------------------------------------------------
# Start backend
# ---------------------------------------------------------------------------

log "Starting FastAPI backend on port 8000..."

(
    cd "$BACKEND"
    exec "$VENV_PYTHON" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
) &

BACKEND_PID=$!

# ---------------------------------------------------------------------------
# Start frontend
# ---------------------------------------------------------------------------

log "Starting Nuxt frontend on port 3000..."

(
    cd "$FRONTEND"
    exec npm run dev -- --host localhost --port 3000
) &

FRONTEND_PID=$!

# ---------------------------------------------------------------------------
# Startup information
# ---------------------------------------------------------------------------

echo
echo "=============================================="
echo " BCES Dispatch started"
echo "=============================================="
echo " Frontend : http://localhost:3000"
echo " API      : http://localhost:8000"
echo " Docs     : http://localhost:8000/docs"
echo "=============================================="
echo " Press CTRL+C to stop services."
echo

# ---------------------------------------------------------------------------
# Process monitoring
# ---------------------------------------------------------------------------

while true; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        wait "$BACKEND_PID" || true
        log "Backend stopped."
        break
    fi

    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        wait "$FRONTEND_PID" || true
        log "Frontend stopped."
        break
    fi

    sleep 1
done

exit 1
