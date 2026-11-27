
$ErrorActionPreference = 'Stop'

###############################################################################
# dev.ps1
# Starts FastAPI backend and Nuxt frontend in development mode.
# Automatically checks and installs missing dependencies.
###############################################################################

$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

$venv = Join-Path $backend '.venv'
$python = Join-Path $venv 'Scripts\python.exe'

$backendProcess = $null
$frontendProcess = $null

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

function Write-Log {
    param([string]$Message)
    Write-Host "[dev] $Message" -ForegroundColor Cyan
}

function Stop-Services {
    Write-Log 'Stopping services...'

    foreach ($proc in @($backendProcess, $frontendProcess)) {
        if ($null -eq $proc) {
            continue
        }

        try {
            $proc.Refresh()

            if (-not $proc.HasExited) {
                $proc.Kill()
                $proc.WaitForExit()
            }
        }
        catch {
            # Process may already be stopped.
        }
    }
}

function Write-Die {
    param([string]$Message)

    Write-Host "[dev] ERROR: $Message" -ForegroundColor Red
    Stop-Services
    exit 1
}

# ---------------------------------------------------------------------------
# Check required tools
# ---------------------------------------------------------------------------

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$pyCommand = Get-Command py -ErrorAction SilentlyContinue
$npmCommand = Get-Command npm -ErrorAction SilentlyContinue

if (-not $pythonCommand -and -not $pyCommand) {
    Write-Die 'Python 3.11 or newer is required.'
}

if (-not $npmCommand) {
    Write-Die 'Node.js and npm are required.'
}

if (-not (Test-Path $backend -PathType Container)) {
    Write-Die "Backend directory not found: $backend"
}

if (-not (Test-Path $frontend -PathType Container)) {
    Write-Die "Frontend directory not found: $frontend"
}

# ---------------------------------------------------------------------------
# Environment files
# ---------------------------------------------------------------------------

$backendEnv = Join-Path $backend '.env'
$backendExample = Join-Path $backend '.env.example'
$frontendEnv = Join-Path $frontend '.env'

if (-not (Test-Path $backendEnv)) {
    if (Test-Path $backendExample) {
        Write-Log 'Creating backend/.env from .env.example'
        Copy-Item $backendExample $backendEnv
    }
    else {
        Write-Die 'backend/.env and backend/.env.example are missing.'
    }
}

if (-not (Test-Path $frontendEnv)) {
    Write-Log 'frontend/.env is missing (optional).'
}

# ---------------------------------------------------------------------------
# Check critical environment variables
# ---------------------------------------------------------------------------

$missing = @()

foreach ($key in @(
        'DISCORD_CLIENT_ID',
        'DISCORD_CLIENT_SECRET',
        'SESSION_SECRET'
    )) {
    $pattern = '^\s*' + [regex]::Escape($key) + '\s*='
    $line = Select-String -Path $backendEnv -Pattern $pattern |
    Select-Object -First 1

    if ($null -eq $line) {
        $missing += $key
        continue
    }

    $value = ($line.Line -replace '^[^=]*=', '').Trim()
    $value = $value.Trim('"').Trim("'")

    if ([string]::IsNullOrWhiteSpace($value)) {
        $missing += $key
    }
}

if ($missing.Count -gt 0) {
    Write-Host "[dev] WARNING: Missing variables: $($missing -join ', ')" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Python virtual environment
# ---------------------------------------------------------------------------

if (-not (Test-Path $python)) {
    Write-Log 'Creating Python virtual environment...'

    if ($pythonCommand) {
        & $pythonCommand.Source -m venv $venv
    }
    else {
        & $pyCommand.Source -3 -m venv $venv
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Die 'Failed to create Python virtual environment.'
    }
}

if (-not (Test-Path $python)) {
    Write-Die 'Python virtual environment was not created.'
}

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------

$requirements = Join-Path $backend 'requirements.txt'

if (-not (Test-Path $requirements)) {
    Write-Die 'backend/requirements.txt not found.'
}

& $python -c 'import fastapi, uvicorn, pydantic_settings, sqlalchemy, aiosqlite, httpx, jwt' 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Log 'Installing Python dependencies...'

    & $python -m pip install --upgrade pip

    if ($LASTEXITCODE -ne 0) {
        Write-Die 'Failed to upgrade pip.'
    }

    & $python -m pip install -r $requirements

    if ($LASTEXITCODE -ne 0) {
        Write-Die 'Failed to install Python dependencies.'
    }
}
else {
    Write-Log 'Python dependencies are already installed.'
}

# ---------------------------------------------------------------------------
# Frontend dependencies
# ---------------------------------------------------------------------------

$packageJson = Join-Path $frontend 'package.json'
$nodeModules = Join-Path $frontend 'node_modules'

if (-not (Test-Path $packageJson)) {
    Write-Die 'frontend/package.json not found.'
}

if (-not (Test-Path $nodeModules)) {
    Write-Log 'Installing frontend dependencies...'

    Push-Location $frontend

    & npm.cmd install
    $npmExitCode = $LASTEXITCODE

    Pop-Location

    if ($npmExitCode -ne 0) {
        Write-Die 'Failed to install frontend dependencies.'
    }
}
else {
    Write-Log 'Frontend dependencies are already installed.'
}

# ---------------------------------------------------------------------------
# Port checks
# ---------------------------------------------------------------------------

foreach ($port in @(8000, 3000)) {
    $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue

    if ($connection) {
        Write-Host "[dev] WARNING: Port $port is already in use." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# Start backend
# ---------------------------------------------------------------------------

Write-Log 'Starting FastAPI backend on port 8000...'

$backendProcess = Start-Process `
    -FilePath $python `
    -ArgumentList @(
    '-m',
    'uvicorn',
    'main:app',
    '--reload',
    '--host',
    '127.0.0.1',
    '--port',
    '8000'
) `
    -WorkingDirectory $backend `
    -PassThru

if ($null -eq $backendProcess) {
    Write-Die 'Failed to start backend.'
}

# ---------------------------------------------------------------------------
# Start frontend
# ---------------------------------------------------------------------------

Write-Log 'Starting Nuxt frontend on port 3000...'

$frontendProcess = Start-Process `
    -FilePath $env:ComSpec `
    -ArgumentList '/c npm.cmd run dev -- --host localhost --port 3000' `
    -WorkingDirectory $frontend `
    -PassThru

if ($null -eq $frontendProcess) {
    Write-Die 'Failed to start frontend.'
}

# ---------------------------------------------------------------------------
# Display information
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '==============================================' -ForegroundColor Green
Write-Host ' BCES Dispatch started' -ForegroundColor Green
Write-Host '==============================================' -ForegroundColor Green
Write-Host ' Frontend : http://localhost:3000'
Write-Host ' API      : http://localhost:8000'
Write-Host ' Docs     : http://localhost:8000/docs'
Write-Host '==============================================' -ForegroundColor Green
Write-Host ' Press CTRL+C to stop services.'
Write-Host ''

# ---------------------------------------------------------------------------
# Process monitoring
# ---------------------------------------------------------------------------

try {
    while ($true) {
        $backendProcess.Refresh()
        $frontendProcess.Refresh()

        if ($backendProcess.HasExited) {
            Write-Host '[dev] Backend stopped.' -ForegroundColor Yellow
            break
        }

        if ($frontendProcess.HasExited) {
            Write-Host '[dev] Frontend stopped.' -ForegroundColor Yellow
            break
        }

        Start-Sleep -Seconds 1
    }
}
finally {
    Stop-Services
}
