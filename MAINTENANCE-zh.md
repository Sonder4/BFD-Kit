# BFD-Kit 维护与同步说明

本文档面向维护 `BFD-Kit` 的开发者与 AI 代理，定义目录边界、真源规则与 GitHub 同步流程。

## 目录角色

当前存在三个需要保持同版内容的 `BFD-Kit` 目录：

1. `/home/xuan/RC2026/STM32/RSCF_A/BFD-Kit`
   - 项目内真源。
   - 任何技能、脚本、文档、`.learnings` 变更首先在这里完成。

2. `/home/xuan/RC2026/STM32/RC2026_h7/BFD-Kit`
   - 工程内镜像副本。
   - 内容应与真源保持同步。

3. `/home/xuan/RC2026/STM32/BFD-Kit`
   - 独立 git 仓库工作目录。
   - 对应 GitHub 仓库：`ssh://git@ssh.github.com:443/Sonder4/BFD-Kit.git`

## 真源规则

- 以 `RSCF_A/BFD-Kit` 为唯一内容真源。
- 不直接在 `RC2026_h7/BFD-Kit` 中做长期维护性修改。
- 不把 `/home/xuan/RC2026/STM32/BFD-Kit` 当作普通子目录维护；它既是同步副本，也是独立仓库。

## 推荐调试路径

- 对全局/静态对象的 RAM 解码，默认使用：
  - `bfd-data-acquisition --mode symbol-auto`
- 仅当 DWARF 自动反射不适用时，才退回：
  - `--mode symbol` + `decode profile`
  - 原始地址采样
  - 低层 GDB/J-Link 命令

## 同步流程

### 1. 在真源目录完成修改

先修改：

- `/home/xuan/RC2026/STM32/RSCF_A/BFD-Kit`

### 2. 同步到另外两个目录

推荐使用排除规则同步：

- 排除 `.git`
- 排除 `__pycache__`
- 对目标仓库必须保留的额外文件，按目标要求保留，例如：
  - `.gitignore`
  - `LICENSE`
  - `README-en.md`

### 3. 验证一致性

同步后至少执行：

```bash
diff -qr --exclude '__pycache__' \
  /home/xuan/RC2026/STM32/RSCF_A/BFD-Kit \
  /home/xuan/RC2026/STM32/RC2026_h7/BFD-Kit
```

以及：

```bash
diff -qr --exclude '__pycache__' \
  /home/xuan/RC2026/STM32/RSCF_A/BFD-Kit \
  /home/xuan/RC2026/STM32/BFD-Kit
```

## GitHub 同步规则

- GitHub 发布目标只认 `/home/xuan/RC2026/STM32/BFD-Kit` 这一个独立仓库边界。
- 不要在 `/home/xuan/RC2026/STM32` 父仓库中直接尝试发布 `BFD-Kit/`。
- 发布前先确认：

```bash
git -C /home/xuan/RC2026/STM32/BFD-Kit rev-parse --show-toplevel
git -C /home/xuan/RC2026/STM32/BFD-Kit remote -v
git -C /home/xuan/RC2026/STM32/BFD-Kit branch --show-current
```

- 推送前应验证目标分支与工作树状态：

```bash
git -C /home/xuan/RC2026/STM32/BFD-Kit fetch origin
git -C /home/xuan/RC2026/STM32/BFD-Kit status --short
git -C /home/xuan/RC2026/STM32/BFD-Kit rev-parse HEAD
git -C /home/xuan/RC2026/STM32/BFD-Kit rev-parse origin/main
```

## 文档更新要求

当以下内容变化时，必须同步更新文档：

- 技能路由或默认工作流变化
- `symbol-auto`、RTT fallback、RAM sampling 路径变化
- 三处 `BFD-Kit` 目录边界或 GitHub 仓库同步方式变化

优先检查并更新：

- `RSCF_A/AGENTS.md`
- `RSCF_A/README.md`
- `BFD-Kit/README.md`
- `BFD-Kit/README-zh.md`
- `BFD-Kit/STM32_AGENT_PROMPT-zh.md`
- 本文档
