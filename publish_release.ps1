# Automatisches Release Publishing zu Gitea

param(
    [string]$Version = "1.0.0",
    [string]$ChangelogFile = "CHANGELOG.md",
    [string]$GiteaToken = $env:GITEA_TOKEN
)

$GiteaUrl = "https://thedoomsdayproject.ignorelist.com:3000"
$Username = "ljawadi"
$RepoName = "alvaro-releases"

Write-Host "📦 Alvaro Release Publisher" -ForegroundColor Cyan
Write-Host ""

# Validierung
if (-not $GiteaToken) {
    Write-Host "❌ GITEA_TOKEN nicht gesetzt!" -ForegroundColor Red
    Write-Host "Setze: `$env:GITEA_TOKEN = 'your_token'" -ForegroundColor Yellow
    exit 1
}

# Prüfe ob Tag existiert
$TagExists = & git rev-parse "v$Version" 2>$null
if (-not $TagExists) {
    Write-Host "⚠️  Tag v$Version nicht gefunden" -ForegroundColor Yellow
    Write-Host "Erstelle Tag..."
    & git tag -a "v$Version" -m "Release $Version"
    & git push origin "v$Version"
}

# Lese Changelog
$Changelog = ""
if (Test-Path $ChangelogFile) {
    $Changelog = Get-Content $ChangelogFile -Raw
}

# Erstelle Release auf Gitea
$ApiUrl = "$GiteaUrl/api/v1/repos/$Username/$RepoName/releases"
$Headers = @{
    "Authorization" = "token $GiteaToken"
    "Content-Type" = "application/json"
}

$ReleaseBody = @{
    "tag_name" = "v$Version"
    "name" = "Release $Version"
    "body" = $Changelog
    "draft" = $false
    "prerelease" = $false
} | ConvertTo-Json

Write-Host "📤 Erstelle Release auf Gitea..." -ForegroundColor Cyan

try {
    $Response = Invoke-WebRequest `
        -Uri $ApiUrl `
        -Method POST `
        -Headers $Headers `
        -Body $ReleaseBody `
        -SkipHttpsValidation

    $Release = $Response.Content | ConvertFrom-Json

    Write-Host "✅ Release erstellt!" -ForegroundColor Green
    Write-Host "🔗 URL: $GiteaUrl/$Username/$RepoName/releases/tag/v$Version" -ForegroundColor Cyan
    Write-Host ""

    # Lade Binaries hoch (optional)
    $BinariesPath = ".\releases"
    if (Test-Path $BinariesPath) {
        Write-Host "📁 Binaries gefunden in: $BinariesPath" -ForegroundColor Cyan
        Write-Host "💡 Lade diese manuell oder per Skript hoch:"
        Get-ChildItem $BinariesPath -File | ForEach-Object {
            Write-Host "   • $($_.Name)"
        }
    }

} catch {
    Write-Host "❌ Fehler beim Release-Erstellen: $_" -ForegroundColor Red
    exit 1
}
