#Requires -Version 5.1
<#
.SYNOPSIS
    使用 GitHub CLI (gh) 创建 Release 并上传打包好的 exe。

.DESCRIPTION
    默认上传 dist\相机同步检测工具.exe，并在存在时附带 camera_sync_config.yaml。
    需已安装 gh 并执行过 gh auth login（或设置环境变量 GH_TOKEN / GITHUB_TOKEN）。

    参考: docs/release.md

.PARAMETER Tag
    版本标签，例如 v1.0.0（须已存在对应 git tag，或与仓库当前提交一致）

.PARAMETER ExePath
    可执行文件路径；默认项目根下 dist\相机同步检测工具.exe

.PARAMETER NotesFile
    发布说明 Markdown（UTF-8）；使用 gh 的 --notes-file

.PARAMETER Draft
    创建为草稿 Release

.PARAMETER DryRun
    只打印将要执行的命令，不实际创建
#>
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
    $ExePath = Join-Path $Root "dist\相机同步检测工具.exe"
}

$ExePath = [System.IO.Path]::GetFullPath($ExePath)
if (-not (Test-Path -LiteralPath $ExePath)) {
    Write-Error "找不到打包产物: $ExePath （请先在项目根目录执行: python -m PyInstaller --noconfirm camera_sync.spec）"
}

function Resolve-GhExe {
    $g = Get-Command gh -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    foreach ($cand in @(
            "$env:ProgramFiles\GitHub CLI\gh.exe",
            "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe"
        )) {
        if ($cand -and (Test-Path -LiteralPath $cand)) { return $cand }
    }
    return $null
}

$GhExe = Resolve-GhExe
if (-not $GhExe) {
    Write-Error "未找到 GitHub CLI (gh)。可执行: winget install GitHub.cli  然后重新打开终端。"
}

# 默认说明文件：docs/release_notes/<Tag>.md
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
    Write-Error "找不到说明文件: $NotesFile"
}

$yamlPath = Join-Path $Root "camera_sync_config.yaml"

$title = "相机同步检测工具 $Tag"

$ghArgs = @(
    "release", "create", $Tag,
    "--repo", "Cltlinxiaoguo/camera-timecode-sync",
    "--title", $title
)
if ($NotesFile -ne "") {
    $nf = [System.IO.Path]::GetFullPath($NotesFile)
    $ghArgs += "--notes-file", $nf
} else {
    $ghArgs += "--notes", "版本 $Tag — 详见 README 与 docs/release.md。"
}
$ghArgs += $ExePath
if (Test-Path -LiteralPath $yamlPath) {
    $ghArgs += [System.IO.Path]::GetFullPath($yamlPath)
}
if ($Draft) {
    $ghArgs += "--draft"
}

if ($DryRun) {
    $quoted = @('&', "`"$GhExe`"") + ($ghArgs | ForEach-Object {
            if ($null -eq $_) { "" }
            elseif ($_ -match '\s') { "`"$_`"" } else { $_ }
        })
    Write-Host "[DryRun] $($quoted -join ' ')" -ForegroundColor Cyan
    exit 0
}

Write-Host "使用: $GhExe" -ForegroundColor DarkGray
Write-Host "正在创建 Release 并上传附件…" -ForegroundColor Green
& $GhExe @ghArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host @"

若提示「already exists」：该 Tag 下已有 Release，可到网页删除草稿/旧 Release 后重试，
或使用: & `"$GhExe`" release upload $Tag `"$ExePath`" --repo Cltlinxiaoguo/camera-timecode-sync --clobber

若提示未登录：先在本机执行一次（浏览器授权）：
  & `"$GhExe`" auth login -h github.com -p https -w

"@ -ForegroundColor Yellow
    exit $LASTEXITCODE
}
Write-Host "完成: https://github.com/Cltlinxiaoguo/camera-timecode-sync/releases" -ForegroundColor Green
