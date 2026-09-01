param(
    [string]$Model = "deepseek-v4-flash",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python virtual environment was not found: $pythonPath"
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Stop the existing local server and try again."
}

$secureKey = Read-Host "Enter DeepSeek API key (input is hidden)" -AsSecureString
$plainKey = [System.Net.NetworkCredential]::new("", $secureKey).Password
if ([string]::IsNullOrWhiteSpace($plainKey)) { throw "API key cannot be empty" }

$env:APP_ENV = "development"
$env:AI_ENABLED = "1"
$env:AI_PROVIDER = "deepseek"
$env:AI_LOCAL_ACCESS = "1"
$env:DEEPSEEK_MODEL = $Model
$env:DEEPSEEK_API_KEY = $plainKey
Remove-Variable plainKey, secureKey

Write-Host "DeepSeek is enabled locally. Model: $Model"
Write-Host "Open http://$HostAddress`:$Port/ . Press Ctrl+C to stop."
try {
    & $pythonPath -m uvicorn app.main:app --app-dir (Join-Path $projectRoot "backend") --host $HostAddress --port $Port --timeout-graceful-shutdown 5
} finally {
    Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:AI_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:AI_LOCAL_ACCESS -ErrorAction SilentlyContinue
}
