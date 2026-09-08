$ErrorActionPreference = "Stop"

$localDir = "C:\Dropbox\Prog\Allenamento"
$tempDir = Join-Path $env:TEMP "allenamento_auto_push"
$repoUrl = "https://github.com/Sebastiano-Mazzarisi/Prog.git"
$repoSubdir = "Allenamento"

function Write-Info($message) {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$time] $message"
}

if (-not (Test-Path -LiteralPath $localDir)) {
    throw "Cartella locale non trovata: $localDir"
}

if (Test-Path -LiteralPath $tempDir) {
    Remove-Item -LiteralPath $tempDir -Recurse -Force
}

Write-Info "Scarico il repository Prog..."
git clone $repoUrl $tempDir | Out-Host

$targetDir = Join-Path $tempDir $repoSubdir
if (Test-Path -LiteralPath $targetDir) {
    Remove-Item -LiteralPath $targetDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

Write-Info "Copio i file di Allenamento..."
Get-ChildItem -LiteralPath $localDir -Force | Where-Object {
    $_.Name -notin @(".git", "Aggiorna_GitHub.log")
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $targetDir -Recurse -Force
}

git -C $tempDir add $repoSubdir

$hasChanges = $true
git -C $tempDir diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    $hasChanges = $false
}

if (-not $hasChanges) {
    Write-Info "Nessuna modifica da pubblicare."
    Remove-Item -LiteralPath $tempDir -Recurse -Force
    exit 0
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
Write-Info "Pubblico su GitHub..."
git -C $tempDir commit -m "Aggiorna Allenamento $stamp" | Out-Host
git -C $tempDir push origin main | Out-Host

Remove-Item -LiteralPath $tempDir -Recurse -Force
Write-Info "Aggiornamento completato."
