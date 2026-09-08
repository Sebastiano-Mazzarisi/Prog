$ErrorActionPreference = "Stop"
$localDir = "C:\Dropbox\Prog\Allenamento"
Set-Location -LiteralPath $localDir

function Write-Info($message) {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$time] $message"
}

if (-not (Test-Path -LiteralPath (Join-Path $localDir ".git"))) {
    git init | Out-Host
    git branch -M main | Out-Host
}

$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    git remote add origin "https://github.com/Sebastiano-Mazzarisi/Allenamento.git"
} elseif ($remote -ne "https://github.com/Sebastiano-Mazzarisi/Allenamento.git") {
    git remote set-url origin "https://github.com/Sebastiano-Mazzarisi/Allenamento.git"
}

git add index.html styles.css app.js assets Aggiorna_GitHub.ps1 Aggiorna_GitHub.bat README.md .gitignore 2>$null

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Info "Nessuna modifica da pubblicare."
    exit 0
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
Write-Info "Pubblico Allenamento su GitHub..."
git commit -m "Aggiorna Allenamento $stamp" | Out-Host
git push -u origin main | Out-Host
Write-Info "Aggiornamento completato."
