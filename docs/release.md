# 发布到 GitHub（源码 + 安装包）

> **仓库命名**：GitHub 上 `你的用户名/你的用户名`（例如 `Cltlinxiaoguo/Cltlinxiaoguo` 或带数字的 profile 专用名）是**个人主页 README 专用仓库**，只适合放一段 `README.md` 做自我介绍，**不要**把整个相机同步项目推进去。业务代码请新建普通仓库，例如 `camera-sync-tool`。
>
> 首次推送可使用仓库内脚本：`scripts\first_push_to_github.ps1 -RemoteUrl "https://github.com/你/仓库名.git"`

与常见开源桌面工具一致：**主仓库只跟踪源码**；**打包好的 `相机同步检测工具.exe` 作为 Release 附件**上传。这样：

- 仓库体积极小，克隆与回滚都快；
- 避免单文件 exe（约 200MB+）拖慢 `git`、触碰 GitHub 推送限制；
- 需要旧版 exe 时，到 `Releases` 页下载对应 Tag 即可。

---

## 一、环境要求（本地打包机）

- Windows 10/11 x64  
- Python 3.12（与当前开发环境一致即可）  
- 已安装本仓库 `requirements.txt` + `requirements-dev.txt`（含 PyInstaller）  
- 可选：安装 **GitHub CLI**（`gh`），用于命令行创建 Release：`https://cli.github.com/`

---

## 二、生成安装包（exe）

在项目根目录执行：

```bat
chcp 65001
python -m PyInstaller --noconfirm camera_sync.spec
```

产物路径：

```text
dist\相机同步检测工具.exe
```

发布时请**顺带**准备同目录使用的 **`camera_sync_config.yaml` 模板**（仓库根目录已有带注释版本；不必打进 exe，用户放 exe 旁即可）。

---

## 三、首次把代码推送到 GitHub

若本地尚未建远程仓库：

1. 在 GitHub 上新建空仓库（不要勾选「用 README 初始化」，避免多余合并提交）。
2. 在项目根目录：

```powershell
git init
git checkout -b main
git add .
git commit -m "chore: initial import"
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

之后日常：`git add` / `git commit` / `git push`。需要回滚时用 `git revert` 或新建分支对比 Tag，与参考项目相同。

---

## 四、发布 Release（推荐：网页或脚本）

### 方式 A：GitHub 网页（最直观）

1. 打开仓库页 → **Releases** → **Draft a new release**。  
2. **Choose a tag**：新建标签，例如 `v1.0.0`（与 `camera_sync/__init__.py` 里 `__version__` 一致更好）。  
3. **Release title**：例如 `相机同步检测工具 v1.0.0`。  
4. 在说明里写变更摘要。  
5. **Attach binaries**：上传 `dist\相机同步检测工具.exe`（可再附上一份 `camera_sync_config.yaml` 供用户改名后使用）。  
6. 发布 **Publish release**。

### 方式 B：命令行（需已 `gh auth login`）

在项目根目录执行（将 `v1.0.0` 换成实际版本）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\publish_github_release.ps1 -Tag v1.0.0
```

仅检查命令、实际上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\publish_github_release.ps1 -Tag v1.0.0 -DryRun
```

自定义 exe 路径或发布说明文件：

```powershell
.\scripts\publish_github_release.ps1 -Tag v1.0.0 -ExePath "dist\相机同步检测工具.exe" -NotesFile "docs\release_notes\v1.0.0.md"
```

---

## 五、版本号维护（建议）

- 改功能 / 修 bug 准备发版时：同步修改 **`camera_sync/__init__.py`** 中的 `__version__`。  
- 打 **Git tag** 与 `__version__` 对齐（如 `v1.0.1` ↔ `1.0.1`）。  
- **Commit message** 可写：`chore: bump version to 1.0.1`。

---

## 六、现场用户从哪里拿 exe？

在 **`README.md`** 中写明：**请到本仓库的 Releases 页面下载最新 `相机同步检测工具.exe`**（将仓库 URL 换成你的，例如 `https://github.com/你的用户名/仓库名/releases`），并随包放置或下载默认 `camera_sync_config.yaml`。不要在正文里依赖「克隆整个仓库只为了拿 dist」——`dist/` 已被 `.gitignore` 忽略，不会进主分支。

---

## 七、超短检查清单

1. 更新 `__version__` → 提交代码 → `git push`。  
2. 本地执行 PyInstaller，确认 `dist\相机同步检测工具.exe` 存在。  
3. 新建 Git **Tag**，创建 **Release**，上传 **exe**（+ 可选 yaml）。  
4. 在 Releases 页面确认附件与说明无误。
