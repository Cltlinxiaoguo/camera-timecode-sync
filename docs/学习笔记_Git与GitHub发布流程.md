# 学习笔记：Git 下载安装与 GitHub 部署（相机同步检测工具项目）

> 整理自本项目的实际操作：在本机安装 Git、把代码推到 GitHub、用标签与 **Releases** 分发 exe。适合复习与给同事做入门说明。

---

## 一、为什么需要 Git 和 GitHub

| 概念 | 作用 |
|------|------|
| **Git** | 本地的「版本管理」：每次改动可 **提交（commit）**，需要时可对比、回退到某一版，避免「改坏了回不去」。 |
| **GitHub** | 远程托管：代码备份在云端、换电脑能拉取、可协作；**标签（tag）+ Releases** 用来发布「可下载的安装包」。 |

本项目中：**源码**走 Git / GitHub **代码页**；**打包好的 exe** 体积大且超过普通提交限制，走 **Releases 附件**，与常见开源桌面软件做法一致。

---

## 二、下载并安装 Git（Windows）

1. **官网**：<https://git-scm.com/download/win>  
2. 运行安装程序，建议关注：
   - **把 Git 加入 PATH**：选择可从「命令行和第三方软件」使用 Git，这样在 `cmd` / PowerShell / Cursor 终端里能直接打 `git`。
   - **Windows 资源管理器集成**：右键「Git Bash Here」便于在某文件夹里打开终端。
   - **Git LFS**、**每日检查更新**等按需要勾选即可，对基本「推送代码」不是必须。
3. 安装完成后 **关闭并重新打开** 终端，验证：

```bat
git --version
```

若提示找不到命令，检查安装时是否勾选 PATH，或重启电脑后再试。

---

## 三、第一次使用前的身份配置（每台电脑一次）

Git 每次提交会记录「是谁提交的」，需配置：

```bash
git config --global user.name "你的名字或昵称"
git config --global user.email "你的邮箱"
```

邮箱可与 GitHub 账号邮箱一致（或使用 GitHub 提供的 `noreply` 地址）。

---

## 四、把本地项目推到 GitHub（最小流程）

前提：在 GitHub 网页上已创建 **空仓库**（或已有空 `main`），并复制 **HTTPS 地址**，例如：

`https://github.com/你的用户名/仓库名.git`

在项目根目录执行：

```bash
cd /你的/项目路径
git init                    # 若尚未初始化
git checkout -b main        # 主分支命名为 main（与 GitHub 默认一致）
git add -A
git commit -m "描述本次提交"
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
git push -u origin main
```

若提示 **remote origin 已存在**：

```bash
git remote remove origin
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

**认证**：首次 `push` 时 GitHub 可能弹出浏览器登录，或在终端里要求 **Personal Access Token**（令牌的权限需包含 `repo`）。按提示完成即可。

---

## 五、为什么「文件夹里有的东西」没有全部出现在 GitHub 上

仓库根目录的 **`.gitignore`** 会告诉 Git **不要跟踪** 某些路径，常见原因：

| 被忽略的示例 | 原因 |
|--------------|------|
| **`build/`**、**`dist/`** | PyInstaller 临时与产物；体积大、可在一台有环境的机器上重新打包。 |
| **`.pytest_cache/`** | 测试缓存，删掉也能再生成。 |
| **`__pycache__`**、虚拟环境 | 与具体机器/解释器相关，不应进仓库。 |

**`.git` 文件夹**只存在于本机，是 Git 的元数据，**永远不会**被推到 GitHub。

因此：**GitHub 的「Code」里看到的是「值得版本管理的源码」**，不是磁盘上该文件夹的完整镜像。

另：**单个文件超过约 100MB** 时，GitHub 会拒绝普通推送，大 exe 应放在 **Releases**，不要强提进分支。

---

## 六、版本号与标签（例如 1.0.0 / v1.0.0）

- 源码里可在 `camera_sync/__init__.py` 的 **`__version__`** 写 `1.0.0`，表示软件语义版本。  
- **Git 标签** 常用 **`v` + 版本号**，如 `v1.0.0`，标记「某一提交 = 某一发版点」：

```bash
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0
```

之后在 GitHub 上可为该标签创建 **Release**，写更新说明、上传 **exe** 等附件。

---

## 七、GitHub Releases：让别人直接下载 exe

1. 打开仓库页右侧或顶部的 **「Releases」**。  
2. **Draft a new release**（新建发行版）。  
3. **选择已有标签**（如 `v1.0.0`），填写标题与说明。  
4. 在 **Attach binaries** 上传 **`相机同步检测工具.exe`**，并可附带 **`camera_sync_config.yaml`**。  
5. 发布后，README 里可写：**请到 Releases 下载最新 exe**，无需克隆整个仓库。

---

## 八、GitHub CLI（`gh`）：命令行创建 Release

可选工具：<https://cli.github.com/> 或用 Windows **winget** 安装：

```bat
winget install --id GitHub.cli -e --accept-package-agreements --accept-source-agreements
```

默认安装路径可能是：`C:\Program Files\GitHub CLI\gh.exe`。若终端里敲 `gh` 找不到，可把该目录加入 PATH，或用**完整路径**调用。

**首次必须登录**（会打开浏览器）：

```bat
"C:\Program Files\GitHub CLI\gh.exe" auth login -h github.com -p https -w
```

本仓库提供脚本 **`scripts/publish_github_release.ps1`**：在已登录、`dist` 下已有 exe 时，可创建 Release 并上传附件。脚本设计为 **ASCII 内容**，避免 **PowerShell 5.1 在 cmd 下用错误编码解析 UTF-8** 导致语法错误（详见脚本内注释与 `docs/release.md`）。

---

## 九、常见坑小结

1. **装完 Git 仍提示找不到 `git`**：重开终端或检查 PATH。  
2. **`push` 被拒绝**：检查是否登录、仓库地址是否正确、分支名是否与远程一致。  
3. **大 exe 不要 `git add`**：用 Release；否则易超大小限制或把仓库撑得巨大。  
4. **`用户名/用户名` 仓库**：GitHub 上这种同名仓库常是 **个人主页展示用**，不适合塞完整业务项目；业务代码应用 **单独仓库名**（本项目示例：`camera-timecode-sync`）。  
5. **PowerShell 跑 `.ps1` 乱码、报「意外标记」**：多为 **UTF-8 无 BOM** 与 **系统默认编码** 不一致；可用 **纯 ASCII 脚本**、或换 **UTF-8 BOM**、或在 **PowerShell 7** / **Git Bash** 下执行。

---

## 十、延伸阅读（本仓库内）

- [发布到 GitHub（Release 流程）](./release.md)  
- 根目录 [README.md](../README.md) 中的「下载安装」与 Releases 链接  
