Set-Location -LiteralPath $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')) {
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') server.py
} elseif (Test-Path -LiteralPath $bundledPython) {
    & $bundledPython server.py
} else {
    python server.py
}
