# BFD-Kit 维护说明

本文档面向维护 `BFD-Kit` 的开发者与 AI 代理，提供不暴露本地工作区结构的通用维护清单。

## 维护原则

- 维护多份 `BFD-Kit` 副本时，保持技能、脚本、文档和 `.learnings` 内容一致。
- 项目对外文档、代理提示词和示例命令中，不写入本地绝对路径、工作区拓扑、镜像关系或仓库发布边界细节。
- 发布前应在目标仓库根目录完成核查，不依赖父目录或外层工作区的默认上下文。

## 推荐调试路径

- 对全局/静态对象的 RAM 解码，默认使用 `bfd-data-acquisition --mode symbol-auto`。
- 仅当 DWARF 自动反射不适用时，才退回 `--mode symbol` + `decode profile`、原始地址采样或低层 GDB/J-Link 命令。

## 推荐维护流程

### 1. 在当前工作副本完成修改

- 先更新相关技能、脚本、文档和 `.learnings`。
- 若文档面向项目使用者，先检查是否包含不应公开的本地环境信息。

### 2. 同步到其他维护副本

- 使用保守同步方式，至少排除 `.git` 与 `__pycache__`。
- 保留目标仓库要求的专属元数据文件，例如许可证、忽略规则或仓库级说明文件。

### 3. 验证一致性

至少执行一次目录对比，确认源副本与目标副本一致：

```bash
diff -qr --exclude '.git' --exclude '__pycache__' <source_copy> <target_copy>
```

### 4. 发布前核查

在目标仓库根目录确认当前发布上下文：

```bash
git -C <publish_repo> rev-parse --show-toplevel
git -C <publish_repo> remote -v
git -C <publish_repo> branch --show-current
git -C <publish_repo> status --short
```

如需与远端对齐，再补充：

```bash
git -C <publish_repo> fetch origin
git -C <publish_repo> rev-parse HEAD
git -C <publish_repo> rev-parse origin/<default_branch>
```

## 文档更新要求

当以下内容变化时，必须同步更新文档：

- 技能路由或默认工作流变化
- `symbol-auto`、RTT fallback、RAM sampling 路径变化
- 维护流程、发布前核查要求或文档脱敏约束变化

优先检查并更新：

- `AGENTS.md`
- `README.md`
- `BFD-Kit/README.md`
- `BFD-Kit/README-zh.md`
- `BFD-Kit/STM32_AGENT_PROMPT-zh.md`
- 本文档
