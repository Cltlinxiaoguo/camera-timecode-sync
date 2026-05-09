#Requires -Version 5.1
# Publishes a GitHub Release with gh. File is ASCII-only so Windows PowerShell 5.1
# (default encoding) parses it reliably. See docs/release.md

param(
    [Parameter(Mandatory = $true)]
    [string]$Tag,

    [string]$ExePath = "",

    [string]$NotesFile = "",

    [switch]$Draft,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir

if (-not $ExePath) {
    $distDir = Join-Path $Root "dist"
    $found = Get-ChildItem -LiteralPath $distDir -File -Filter "*.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $found) {
        Write-Error "No .exe under dist/. Build first: python -m PyInstaller --noconfirm camera_sync.spec"
    }
    $ExePath = $found.FullName
}

$ExePath = [System.IO.Path]::GetFullPath($ExePath)
if (-not (Test-Path -LiteralPath $ExePath)) {
    Write-Error "Exe not found: $ExePath"
}

function Resolve-GhExe {
    $g = Get-Command gh -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    $c1 = Join-Path $env:ProgramFiles "GitHub CLI\gh.exe"
    $c2 = Join-Path ${env:ProgramFiles(x86)} "GitHub CLI\gh.exe"
    foreach ($cand in @($c1, $c2)) {
        if ($cand -and (Test-Path -LiteralPath $cand)) { return $cand }
    }
    return $null
}

$GhExe = Resolve-GhExe
if (-not $GhExe) {
    Write-Error "gh not found. Install: winget install GitHub.cli"
}

if (-not $NotesFile) {
    $autoNotes = Join-Path $Root "docs\release_notes\$Tag.md"
    if ($Tag.StartsWith("v") -and -not (Test-Path -LiteralPath $autoNotes)) {
        $verPart = $Tag.TrimStart("v")
        $autoNotes = Join-Path $Root "docs\release_notes\$verPart.md"
    }
    if (Test-Path -LiteralPath $autoNotes) {
        $NotesFile = $autoNotes
    }
}

if ($NotesFile -ne "" -and -not (Test-Path -LiteralPath $NotesFile)) {
    Write-Error "Notes file not found: $NotesFile"
}

$yamlPath = Join-Path $Root "camera_sync_config.yaml"
$Repo = "Cltlinxiaoguo/camera-timecode-sync"
$title = "Camera timecode sync $Tag"

$ghList = New-Object System.Collections.Generic.List[string]
$ghList.Add("release")
$ghList.Add("create")
$ghList.Add($Tag)
$ghList.Add("--repo")
$ghList.Add($Repo)
$ghList.Add("--title")
$ghList.Add($title)

if ($NotesFile -ne "") {
    $nf = [System.IO.Path]::GetFullPath($NotesFile)
    $ghList.Add("--notes-file")
    $ghList.Add($nf)
}
else {
    $ghList.Add("--notes")
    $ghList.Add("Release $Tag. See README and docs/release.md.")
}

$ghList.Add($ExePath)
if (Test-Path -LiteralPath $yamlPath) {
    $ghList.Add([System.IO.Path]::GetFullPath($yamlPath))
}
if ($Draft) {
    $ghList.Add("--draft")
}

$ghArgs = $ghList.ToArray()

if ($DryRun) {
    Write-Host ("[DryRun] {0} {1}" -f $GhExe, ($ghArgs -join " ")) -ForegroundColor Cyan
    exit 0
}

Write-Host "Using: $GhExe" -ForegroundColor DarkGray
Write-Host "Creating release and uploading assets..." -ForegroundColor Green
& $GhExe @ghArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "If release exists, delete it on GitHub or run:" -ForegroundColor Yellow
    Write-Host "  & `"$GhExe`" release upload $Tag `"$ExePath`" --repo $Repo --clobber" -ForegroundColor Yellow
    Write-Host "If not logged in:" -ForegroundColor Yellow
    Write-Host "  & `"$GhExe`" auth login -h github.com -p https -w" -ForegroundColor Yellow
    exit $LASTEXITCODE
}
Write-Host "Done: https://github.com/$Repo/releases" -ForegroundColor Green
