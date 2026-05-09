#Requires -Version 5.1
<#
.SYNOPSIS
    使用 GitHub CLI (gh) 创建 Release 并上传打包好的 exe。

.DESCRIPTION
    默认上传 dist\相机同步检测工具.exe。需已安装 gh 并执行过 gh auth login。
    参考: docs/release.md

.PARAMETER Tag
    版本标签，例如 v1.0.0（须尚未存在，或与 gh release 行为一致）

.PARAMETER ExePath
    可执行文件路径；默认相对本脚本上两级目录下的 dist\相机同步检测工具.exe

.PARAMETER NotesFile
    若指定，发布说明从该 UTF-8 文件读取；否则使用简短默认说明

.PARAMETER Draft
    创建为草稿 Release

.PARAMETER DryRun
    只打印将要执行的 gh 命令，不实际创建
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

$ghCmd = Get-Command gh -ErrorAction SilentlyContinue
if (-not $ghCmd) {
    Write-Error "未找到 GitHub CLI (gh)。请安装: https://cli.github.com/  并执行 gh auth login"
}

$notes = "版本 $Tag — 详见仓库 README 与 docs/release.md。"
if ($NotesFile -ne "" -and (Test-Path -LiteralPath $NotesFile)) {
    $notes = Get-Content -LiteralPath $NotesFile -Raw -Encoding UTF8
}

$title = "相机同步检测工具 $Tag"

# gh release create: TAG 后可为多个待上传文件
$ghArgs = @(
    "release", "create", $Tag,
    "--title", $title,
    "--notes", $notes,
    $ExePath
)
if ($Draft) {
    $ghArgs += "--draft"
}

if ($DryRun) {
    $quoted = $ghArgs | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }
    Write-Host "[DryRun] gh $($quoted -join ' ')" -ForegroundColor Cyan
    Write-Host "（未执行 gh；去掉 -DryRun 后才会真正发布）"
    exit 0
}

Write-Host "正在创建 Release 并上传: $ExePath" -ForegroundColor Green
& gh @ghArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-Host "完成。请到 GitHub 仓库 Releases 页面核对附件与说明。" -ForegroundColor Green
