# 队友 DSH 环境配置与插件指南（EcoSentinel）

> 本文只写**实测到的事实**（命令、路径、已装清单都是在本机 `dsh` 上跑出来的），不含猜测。
> 采集环境：`DSH_HOME=C:\Users\finef\.dsh`、`DSH_PROFILE=desktop`、`DSH_WEB_URL=http://127.0.0.1:19387`。

## 1. 先理解 DSH 的"插件"是什么

`dsh --help` 的原话：DSH 启动的是**一个 profile** —— "an ordered stack of plugin-bundle patch layers
under your own overrides"。

落地结构（实测目录）：

```
$DSH_HOME/
├─ AGENTS.md                      # 全局代理约定（本机已有一份参数纪律，值得保留）
├─ settings.yaml*                 # 全局设置（含若干 .bak 备份）
├─ skills/<name>/SKILL.md         # 技能包（本机已装 vision-multimodal）
└─ profiles/<profile>/
   ├─ package.json                # ★ 插件就是这里的 pnpm 依赖
   ├─ pnpm-lock.yaml
   ├─ .plugin-manager/{run.json,logs/}   # 插件管理器的运行日志
   └─ .dsh-market/state.json      # 市场状态：{"disabled":[],"groups":{},"region":"global",...}
```

**关键**：插件不是"点一下安装的扩展"，而是**该 profile 目录里的 npm 包**；`dsh plugin` 的官方描述就是
"manage a profile's plugins by **forwarding the remaining arguments to pnpm in the profile directory**"。

## 2. 命令（照抄即可，注意 `--profile` 在子命令**之前**）

```bash
dsh --profile desktop plugin list        # 列出已装插件（= profile 里的 pnpm 依赖）
dsh --profile desktop plugin add <pkg>   # 装一个插件（转发给 pnpm add）
dsh --profile desktop plugin update      # 更新
dsh --profile desktop --dump-config      # 打印合成后的 profile 树（排查"为什么某插件没生效"）
```

> 实测坑：`dsh plugin --help` 会报 `required option '--profile <name>' not specified` —— 必须
> `dsh --profile <name> plugin <cmd>` 这个顺序。

## 3. 本机已装的 11 个插件（`plugin list` 实录）

```
@changfenhuang/dsh-annotation@1.4.10
@dsh-external/dsh-normify@link:D:/SeaBreeze Inspector/.dsh-plugins/dsh-normify   # 本地 link
@liustack/modlens@3.26.5
dsh-context@0.59.2
dsh-mimir@0.21.0
dsh-orb@0.0.0
dsh-talk@0.3.15
dsh-tool-call-guard@0.1.1
dsh-tool-repair@0.1.1
dsh-vision-router@2.2.8
dshmarket@1.66.5
```

## 4. 做 EcoSentinel 这件事，真正用得上的插件 / 技能

| 插件/技能 | 用途（对应本项目的哪个环节） | 状态 |
|---|---|---|
| `dsh-mimir` | 文献库 + 图表归档 + 组会 PPT（工具：`wiki_note` / `figure_save` / `meeting_deck`） | 已装 ✅ |
| `@dsh-external/dsh-normify` + `normify-gen` 技能 | 把 `energy_system/` 的分层结构画成可下钻模块树，改架构前先看影响面 | 已装 ✅ |
| `dsh-vision-router` + `vision-multimodal` 技能 | 读**图**：INA219 接线图、评委截图、数据手册扫描件、串口抓包界面 | 已装 ✅ |
| `dsh-tool-call-guard` / `dsh-tool-repair` | 工具调用参数过大时的自愈（本机在长参数上偶发整回合失败） | 已装 ✅ |
| `office-docx` / `office-pptx` / `office-xlsx` 技能 | 仓库里已有 `EcoSentinel_作品说明书.pdf` 与 LaTeX 源码包 ⇒ 改说明书、做答辩 PPT、算能耗表 | 按需 ✅ |
| `research-lit-review` / `research-citation-audit` 技能 | `docs/literature-review.md` 是竞赛补充材料 ⇒ **逐条核引用是否真实存在**（零信任审稿） | 按需 ✅ |
| `sxng` 技能 | 查外部事实（标准条款、库版本、报错），比自带搜索更省 token | 按需 ✅ |
| `diagnose-windows-sandbox-acl` 技能 | **本机高频**：沙箱下写 `.pytest_cache`、`Arduino15`、`__pycache__` 被拒时的 ACL 自诊断与修复 | 强烈建议 ✅ |

## 5. 本机特有的坑（我和它们搏斗过，替你省时间）

1. **8080 被 Steam 占**：`steamwebhelper` 会监听 `127.0.0.1:8080`，把后端挤掉 ⇒ 用
   `python scripts/stack_acceptance.py`（**自动挑空闲端口**）或 `python api_server.py --port 8090`。
2. **项目 venv 里没有 pip**（`No module named pip`）⇒ 装临时工具用 **uv**：
   `uv run --with pythermalcomfort python xxx.py`，**不要**为此改仓库依赖。
3. **`python -m compileall` 在受限沙箱必失败**（不能写 `__pycache__`）—— 这是环境问题，不是代码问题；
   以 CI 的编译检查为准。
4. **GitHub 偶发 TLS 抖动**（`unexpected eof while reading`）⇒ `git push` 重试 2–3 次即可成功。
5. 中文写盘**不要**用 `Set-Content -Encoding utf8`（会加 BOM/乱码）；用编辑器工具或
   `[System.IO.File]::WriteAllText(path, text, New-Object System.Text.UTF8Encoding($false))`。

## 6. 队友上手 checklist（5 步）

1. `git clone` 仓库 → 读 `AGENTS.md` → 读 `docs/handoff.md`（含"明确没做的 4 件事"）
2. `python -m venv .venv` + `pip install -r requirements.txt`（要 Streamlit 再加 `-r requirements-dashboard.txt`）
3. `python -m pytest tests -q`（**252 passed**）→ `python scripts/stack_acceptance.py`（**PASS 7/7**）
4. `cd app && npm ci && npm run lint && npm run knip && npm test && npm run build`（**56 passed**）
5. 需要视觉工作时 `dsh --profile desktop plugin list` 确认 `dsh-vision-router` 在；本机装插件用
   `dsh --profile desktop plugin add <pkg>`
