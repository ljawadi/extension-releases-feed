# Setup-Skript für Gitea-Push
# Vorbereitung für erstes Pushen zum Gitea-Repo

param(
    [string]$Token = $env:GITEA_TOKEN,
    [switch]$UseSSH = $false
)

$RepoPath = "D:\AI\alvaro-releases"
$GiteaUrl = "https://thedoomsdayproject.ignorelist.com:3000"
$Username = "ljawadi"
$RepoName = "alvaro-releases"

Write-Host "🚀 Gitea-Push Setup für Alvaro Releases" -ForegroundColor Cyan
Write-Host ""

# 1. Prüfe Git
Write-Host "1️⃣  Prüfe Git-Installation..." -ForegroundColor Yellow
$GitVersion = & git --version 2>$null
if ($GitVersion) {
    Write-Host "✅ $GitVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Git nicht gefunden!" -ForegroundColor Red
    exit 1
}

# 2. Gehe ins Repo
Set-Location $RepoPath
Write-Host "✅ Wechsel zu: $RepoPath" -ForegroundColor Green

# 3. Prüfe Git-Status
Write-Host ""
Write-Host "2️⃣  Prüfe Git-Status..." -ForegroundColor Yellow
$Status = & git status --short
if ($Status) {
    Write-Host "⚠️  Unverpflichtete Änderungen gefunden:" -ForegroundColor Yellow
    Write-Host $Status
    Write-Host ""
    Write-Host "Diese werden hinzugefügt:" -ForegroundColor Cyan
} else {
    Write-Host "✅ Alles ist clean" -ForegroundColor Green
}

# 4. Remote-URL setzen
Write-Host ""
Write-Host "3️⃣  Konfiguriere Remote-URL..." -ForegroundColor Yellow

$RemoteExists = & git remote get-url origin 2>$null
if ($RemoteExists) {
    Write-Host "⚠️  Remote 'origin' existiert bereits:" -ForegroundColor Yellow
    Write-Host "   $RemoteExists" -ForegroundColor Gray
    $Continue = Read-Host "Soll es überschrieben werden? (j/n)"
    if ($Continue -ne "j") {
        Write-Host "❌ Abgebrochen" -ForegroundColor Red
        exit 1
    }
    & git remote remove origin
}

if ($UseSSH) {
    # SSH-Remote
    $RemoteUrl = "git@thedoomsdayproject.ignorelist.com:ljawadi/alvaro-releases.git"
    Write-Host "📍 Verwende SSH (benötigt SSH-Key)" -ForegroundColor Cyan
} else {
    # HTTPS-Remote mit Token
    if (-not $Token) {
        Write-Host "❌ Token nicht vorhanden!" -ForegroundColor Red
        Write-Host "Setze vorher: `$env:GITEA_TOKEN = 'your_token'" -ForegroundColor Yellow
        exit 1
    }
    $RemoteUrl = "https://${Username}:${Token}@thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases.git"
    Write-Host "📍 Verwende HTTPS + Token" -ForegroundColor Cyan
}

& git remote add origin $RemoteUrl
Write-Host "✅ Remote konfiguriert" -ForegroundColor Green

# 5. Erster Commit
Write-Host ""
Write-Host "4️⃣  Vorbereitung für Commit..." -ForegroundColor Yellow

& git add .
$CommitCount = (& git diff --cached --numstat | Measure-Object).Count
Write-Host "✅ $CommitCount Dateien hinzugefügt" -ForegroundColor Green

# 6. Zeige Preview
Write-Host ""
Write-Host "📋 Commit-Vorschau:" -ForegroundColor Cyan
& git diff --cached --name-only | ForEach-Object {
    Write-Host "   ✓ $_" -ForegroundColor Green
}

# 7. Bestätigung
Write-Host ""
Write-Host "🔧 Bereit zum Commit? (Weitere Schritte folgen)" -ForegroundColor Cyan
$Confirm = Read-Host "Jetzt committen und pushen? (j/n)"

if ($Confirm -eq "j") {
    # Commit
    Write-Host ""
    Write-Host "5️⃣  Erstelle Commit..." -ForegroundColor Yellow

    $CommitMsg = @"
Initial: Alvaro Release Management System

- GUI-Installer (tkinter)
- Update-Checker mit Gitea-Integration
- Release-Feed (JSON-basiert)
- Build-Skripte für Windows/Mac/Linux
- Dokumentation & Workflows

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KoShdhZDrrr2jjFT7icTxr
"@

    & git commit -m $CommitMsg
    Write-Host "✅ Commit erstellt" -ForegroundColor Green

    # Push
    Write-Host ""
    Write-Host "6️⃣  Push zu Gitea..." -ForegroundColor Yellow
    & git push -u origin main

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Push erfolgreich!" -ForegroundColor Green
        Write-Host ""
        Write-Host "🎉 Fertig!" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🔗 Repository-URL:" -ForegroundColor Cyan
        Write-Host "   $GiteaUrl/$Username/$RepoName" -ForegroundColor Gray
        Write-Host ""
        Write-Host "📋 Nächste Schritte:" -ForegroundColor Yellow
        Write-Host "   1. Update-Feed testen: python3 update_checker.py" -ForegroundColor Gray
        Write-Host "   2. Windows .exe bauen: python3 build_installer.py" -ForegroundColor Gray
        Write-Host "   3. Binaries zu releases/ hochladen" -ForegroundColor Gray
        Write-Host "   4. Release veröffentlichen: .\publish_release.ps1 -Version 1.0.0" -ForegroundColor Gray
    } else {
        Write-Host "❌ Push fehlgeschlagen" -ForegroundColor Red
        Write-Host "Fehler behoben? Versuche erneut:" -ForegroundColor Yellow
        Write-Host "   git push -u origin main" -ForegroundColor Gray
        exit 1
    }
} else {
    Write-Host "⏭️  Abgebrochen (keine Änderungen)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Später fortfahren mit:" -ForegroundColor Cyan
    Write-Host "   .\SETUP_PUSH.ps1 -Token 'your_token'" -ForegroundColor Gray
}

Write-Host ""
Write-Host "---" -ForegroundColor Gray
Write-Host "Brauchst du Hilfe? Siehe PUSH_TO_GITEA.md" -ForegroundColor Gray
