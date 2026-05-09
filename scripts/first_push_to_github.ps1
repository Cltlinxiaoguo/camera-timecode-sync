#Requires -Version 5.1
<#
.SYNOPSIS
    首次把本项目推送到 GitHub（仅源码，不含 dist；exe 请用 Release 上传）。

.DESCRIPTION
    注意：GitHub 上「用户名/用户名」仓库（如 Cltlinxiaoguo/linxiaoguo666）是个人主页专用，
    仅适合放 README 展示自我介绍，不要用来存整仓业务代码。

    请先在网页新建普通仓库，例如：Cltlinxiaoguo/camera-sync-tool
    远程地址示例：https://github.com/Cltlinxiaoguo/camera-sync-tool.git

    本脚本默认不会提交 dist\*.exe（体积约 240MB+ 且超过 GitHub 单文件 100MB 限制）。

.PARAMETER RemoteUrl
    你的仓库 HTTPS 地址，必须以 .git 结尾

.PARAMETER SkipCommit
    若已有提交且仅想改 remote / push，可加此开关并自行处理分支

.EXAMPLE
    .\scripts\first_push_to_github.ps1 -RemoteUrl "https://github.com/Cltlinxiaoguo/camera-sync-tool.git"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUrl,

    [switch]$SkipCommit
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent $ScriptDir)

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Error @"
未找到 git。请先安装 Git for Windows: https://git-scm.com/download/win
安装时勾选「Add Git to PATH」，重新打开终端后再运行本脚本。
"@
}

if (-not (Test-Path -LiteralPath ".git")) {
    Write-Host "初始化本地仓库..." -ForegroundColor Cyan
    git init
    git branch -M main
}

$hasRemote = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "已存在 origin: $hasRemote ，将替换为 $RemoteUrl" -ForegroundColor Yellow
    git remote remove origin
}
git remote add origin $RemoteUrl

if (-not $SkipCommit) {
    git add -A
    $status = git status --porcelain
    if ($status) {
        git commit -m "chore: import 相机同步检测工具源码 (camera_sync)"
    } else {
        Write-Host "没有待提交变更（可能已提交过）。" -ForegroundColor Yellow
    }
}

Write-Host @"

下一步请在当前目录执行（会提示 GitHub 登录或输入 Token）：
  git push -u origin main

若远程已有 README 等初始提交导致拒绝推送，请先拉取再合并：
  git pull origin main --allow-unrelated-histories
  git push -u origin main

可执行文件请用 Release 上传（单文件超过 GitHub 100MB 限制无法普通提交）：
  1. 先成功 push 源码
  2. 安装 gh 并 gh auth login
  3. python -m PyInstaller --noconfirm camera_sync.spec
  4. .\scripts\publish_github_release.ps1 -Tag v1.0.0

详见 docs\release.md
"@ -ForegroundColor Green
