# setup/setup.ps1
# TTC-Map — Full Environment Setup (Windows PowerShell)
# Run:
#   powershell -ExecutionPolicy Bypass -File setup\setup.ps1

$ErrorActionPreference = "Stop"

# Project root = parent of this script directory
$PROJECT_ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Write-Host "Project root: $PROJECT_ROOT"

$reqPath    = Join-Path $PROJECT_ROOT "requirements.txt"
$venvDir    = Join-Path $PROJECT_ROOT "venv"
$apiDir     = Join-Path $PROJECT_ROOT "API"
$nodeApiDir = Join-Path $PROJECT_ROOT "node-api"

function Require-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Missing required command '$name' in PATH."
    }
}

# ─────────────────────────────────────────────
# 1. Fix requirements.txt encoding (UTF-16/BOM → UTF-8) + normalize line endings
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "Fixing requirements.txt encoding..."

if (Test-Path $reqPath) {
    [byte[]]$bytes = [System.IO.File]::ReadAllBytes($reqPath)

    $isUtf16Le = ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE)
    $isUtf16Be = ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF)
    $isUtf8Bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)

    if ($isUtf16Le -or $isUtf16Be) {
        $encoding = if ($isUtf16Be) { [System.Text.Encoding]::BigEndianUnicode } else { [System.Text.Encoding]::Unicode }
        $text = $encoding.GetString($bytes)

        $lines = $text -split "\r\n|\r|\n" | Where-Object { $_ -notmatch "^\s*$" }

        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllLines($reqPath, $lines, $utf8NoBom)

        Write-Host "Converted UTF-16 → UTF-8"
    }
    else {
        # Normalize line endings + remove empty lines; write UTF-8 no BOM
        $text  = Get-Content -Path $reqPath -Raw
        $lines = $text -split "\r\n|\r|\n" | Where-Object { $_ -notmatch "^\s*$" }

        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllLines($reqPath, $lines, $utf8NoBom)

        if ($isUtf8Bom) { Write-Host "UTF-8 BOM detected; normalized to UTF-8 (no BOM)." }
        else { Write-Host "Already UTF-8; cleaned line endings." }
    }
}
else {
    Write-Host "requirements.txt not found; it will be created by pipreqs."
}

# ─────────────────────────────────────────────
# 2. Python virtual environment + pipreqs + pip install (NO activation needed)
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "Setting up Python virtual environment..."

# Prefer 'py -3' if available, else 'python'
$pythonLauncher = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $pythonLauncher = @("py","-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonLauncher = @("python") }
else { throw "Python 3 not found in PATH." }

if (-not (Test-Path $venvDir)) {
    & $pythonLauncher[0] @($pythonLauncher[1..($pythonLauncher.Length-1)] | Where-Object { $_ }) -m venv $venvDir
    Write-Host "venv created"
}
else {
    Write-Host "venv already exists"
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Host "Upgrading pip and installing pipreqs..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install pipreqs

Write-Host "Scanning Python files for imports with pipreqs..."
& $venvPython -m pipreqs $apiDir --force --savepath $reqPath
if (Select-String -Path $reqPath -Pattern "^fastapi$") {
    (Get-Content $reqPath) `
        -replace "^fastapi$", "fastapi[standard]" `
        | Set-Content $reqPath -Encoding UTF8
}

Write-Host "requirements.txt updated:"
Get-Content $reqPath | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Installing Python dependencies..."
& $venvPython -m pip install -r $reqPath
Write-Host "Python packages installed"

# ─────────────────────────────────────────────
# 3. Node.js dependencies
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "Installing Node.js dependencies..."

Require-Command "npm"
if (-not (Test-Path $nodeApiDir)) { throw "node-api directory not found at: $nodeApiDir" }

Push-Location $nodeApiDir
try {
    npm ci
    Write-Host "Node packages installed"
}
finally {
    Pop-Location
}

# ─────────────────────────────────────────────
# 4. Summary
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================="
Write-Host "Setup complete!"
Write-Host "==========================================="
Write-Host ""
Write-Host "PYTHON API (FastAPI):"
Write-Host "  Activate venv:   .\venv\Scripts\Activate.ps1"
Write-Host "  Init DB:         cd API\src ; python update_db.py"
Write-Host "  Run server:      fastapi dev API\src\main.py"
Write-Host ""
Write-Host "NODE API (Express):"
Write-Host "  Start server:    cd node-api ; npm start"
Write-Host "  Dev mode:        cd node-api ; npm run dev"
Write-Host "  Frontend:        http://localhost:3000"
Write-Host ""
Write-Host "==========================================="
