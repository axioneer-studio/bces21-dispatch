$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$venvPython = Join-Path $backend '.venv\Scripts\python.exe'

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description a echoue (code $LASTEXITCODE)."
    }
}

try {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $python) {
        throw 'Python est introuvable. Installez Python 3.11 ou plus recent puis relancez dev.cmd.'
    }

    if (-not (Test-Path $venvPython)) {
        Write-Host 'Creation de l environnement Python...'
        if ($python.Name -like 'py*') {
            Invoke-CheckedCommand $python.Source @('-3', '-m', 'venv', (Join-Path $backend '.venv')) 'La creation de l environnement Python'
        }
        else {
            Invoke-CheckedCommand $python.Source @('-m', 'venv', (Join-Path $backend '.venv')) 'La creation de l environnement Python'
        }
    }

    if (-not (Test-Path $venvPython)) {
        throw "Python n a pas cree l environnement attendu : $venvPython"
    }

    & $venvPython -c 'import fastapi, uvicorn, pydantic_settings, sqlalchemy, aiosqlite, httpx, jwt'
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installation des dependances Python...'
        Invoke-CheckedCommand $venvPython @('-m', 'pip', 'install', '-r', (Join-Path $backend 'requirements.txt')) 'L installation des dependances Python'
    }

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw 'npm est introuvable. Installez Node.js puis relancez dev.cmd.'
    }

    if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
        Write-Host 'Installation des dependances frontend...'
        Push-Location $frontend
        try {
            Invoke-CheckedCommand $npm.Source @('install') 'L installation des dependances frontend'
        }
        finally {
            Pop-Location
        }
    }

    Start-Process -FilePath $venvPython `
        -ArgumentList @('-m', 'uvicorn', 'main:app', '--reload') `
        -WorkingDirectory $backend

    Start-Process -FilePath $env:ComSpec `
        -ArgumentList @('/k', 'npm.cmd run dev') `
        -WorkingDirectory $frontend

    Write-Host ''
    Write-Host 'BCES Dispatch demarre dans deux fenetres separees :'
    Write-Host '  Frontend : http://localhost:3000'
    Write-Host '  API      : http://localhost:8000/docs'
}
catch {
    Write-Error $_
    exit 1
}