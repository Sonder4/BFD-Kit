# BFD-Kit：AI STM32 调试工具包

BFD-Kit 是一个可移植、CLI 优先的 STM32 AI 调试工具包。
它统一了 IOC 识别、运行配置生成、烧录、RTT 日志、寄存器/数据采集和故障证据归档流程。

## 适用范围

- 当前内置芯片族：`STM32F4`、`STM32H7`
- 支持代理：Codex、Claude
- 技能源目录：`BFD-Kit/skills/{codex,claude}/bfd-*`
- 运行时配置目录：`.codex/bfd/`
- 旧路径兼容镜像：`.codex/stm32/bootstrap/`

## 目录结构

- `BFD-Kit/skills/codex/`：Codex 技能源树
- `BFD-Kit/skills/claude/`：Claude 技能源树
- `BFD-Kit/resources/stm32/templates/`：芯片族模板（`f4/`、`h7/`）
- `BFD-Kit/init_project.sh`：一键项目接入入口
- `BFD-Kit/scripts/bfd_jlink_hss.sh`：带本地运行时的原生 J-Link HSS 包装入口
- `BFD-Kit/.runtime/venv`：按需安装的本地 Python 运行时
- `BFD-Kit/scripts/migrate_bfd_skills.py`：技能导入/回灌脚本
- `BFD-Kit/MAINTENANCE-zh.md`：维护者维护清单

## 技能列表

- `bfd-project-init`：扫描 `.ioc`/startup/linker/svd/cfg/build 产物，生成统一调试配置
- `bfd-ioc-parser`：解析 `.ioc`，并把 JSON 结果落到 `.codex/bfd/ioc_json/`
- `bfd-cubemx-codegen`：基于现有 `.ioc` 只读重新生成 CubeMX 工程代码
- `bfd-flash-programmer`：稳定的 J-Link/ST-Link 烧录流程
- `bfd-rtt-logger`：RTT 运行日志采集
- `bfd-debug-interface`：结构化调试流程与故障上下文处理
- `bfd-debug-executor`：一次性 J-Link 命令执行
- `bfd-register-capture`：外设寄存器采样与导出
- `bfd-data-acquisition`：运行时数据采集与分析
- `bfd-fault-logger`：HardFault/BusFault/UsageFault 归档
- `bfd-debug-orchestrator`：端到端调试编排
- `bfd-user-feedback`：用户反馈与状态回传

完成 canonical `bfd-*` 技能回灌后，应清理活动镜像中的重复 `stm32-*` 与旧调试技能目录。

`bfd-data-acquisition` 已纳入 `resources/local-probe/` 资源，用于局部变量运行时地址发布与主机侧指针采样。

## 本次版本新增能力

- `bfd-data-acquisition` 新增通用 `--mode symbol-auto`
- `bfd-data-acquisition` 新增原生 J-Link HSS CLI，可用于固定地址标量的非阻塞高速采样
- `symbol-auto` 通过 `ELF + DWARF` 自动反射全局/静态对象，不再依赖业务对象硬编码
- DWARF schema 会缓存到 `.codex/bfd/dwarf_cache/`，便于重复采样复用
- RTT 无有效 payload 时，标准流程明确切换到 RAM 采样，而不是临时拼接 GDB/J-Link 命令
- `bfd-debug-interface` 与 `bfd-rtt-logger` 已把结构化符号解码默认委托给 `bfd-data-acquisition`

当前 V1 自动反射支持：

- `struct`
- `array`
- `pointer`
- `typedef`
- `enum`

推荐顺序：

- 第一选择：对具备可用 DWARF 的稳定全局/静态符号，优先使用 `symbol-auto`
- 第二选择：当自动反射不适合时，使用 `--mode symbol` 配合显式 `decode profile` 或 `layout`
- 最后选择：原始地址采样或底层调试命令

## 快速初始化

```bash
# 一条命令完成技能接入/更新、刷新 .codex/bfd 运行配置，并准备本地 Python 运行时
bash BFD-Kit/init_project.sh --project-root .

# 可选模式
bash BFD-Kit/init_project.sh --project-root . --cutover-only
bash BFD-Kit/init_project.sh --project-root . --bootstrap-only --force-refresh
bash BFD-Kit/init_project.sh --project-root . --runtime-only
```

## 标准流程

```bash
# 1) 生成/刷新统一运行配置
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check

# 1.5) 可选：基于现有 .ioc 只读重新生成 CubeMX 管理代码
python3 ./.codex/skills/bfd-cubemx-codegen/scripts/generate_from_ioc.py --project-root . --log-dir logs/skills

# 2) 烧录
./build_tools/jlink/flash.sh builds/gcc/debug | tee logs/flash/flash_$(date +%Y%m%d_%H%M%S).log

# 3) RTT 日志
./build_tools/jlink/rtt.sh logs/rtt/rtt_$(date +%Y%m%d_%H%M%S).log 5 --mode quick

# 3.5) 若 RTT 没有有效 payload，则切换到通用 RAM 解码
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol <global_symbol> \
  --follow-depth 1 \
  --format summary \
  --output logs/data_acq/<global_symbol>.summary

# 3.6) 若需求是高频、非阻塞标量采样，则切到原生 HSS
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol chassis_parameter.IMU.yaw \
  --symbol chassis_parameter.IMU.pitch \
  --duration 0.3 \
  --period-us 1000 \
  --output logs/data_acq/imu_yaw_pitch_hss.csv

# 4) 一次性调试会话
./build_tools/jlink/debug.sh | tee logs/debug/debug_$(date +%Y%m%d_%H%M%S).log
```

## 推荐的数据采集路径

```bash
# 通用全局/静态对象解码
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol g_object_state \
  --follow-depth 0 \
  --format summary

# 通用指针 hub / 指针数组解码
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol g_object_hub \
  --follow-depth 1 \
  --format json

# 自动反射不适用时的手工回退路径
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol \
  --symbol g_object_array \
  --count <N> \
  --decode-profile <profile_name> \
  --format csv

# 一个或多个固定地址标量的原生 J-Link HSS 采样
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol chassis_parameter.IMU.yaw \
  --symbol chassis_parameter.IMU.pitch \
  --duration 1 \
  --period-us 1000 \
  --output logs/data_acq/imu_yaw_pitch_hss.csv
```

对 `J-Link PLUS`，SEGGER 官方型号限制和本地 HSS 实测都表明上限是 10 个 symbol。不要把 `hss inspect` 返回的原始 capability 第 3 个 word 当作 symbol 数量上限。`hss sample` 会把同步宽表 CSV 写到 `--output`，并额外生成 `--output.meta.json` 元数据文件。

## 运行配置约定

- 规范路径：
  - `.codex/bfd/active_profile.json`
  - `.codex/bfd/active_profile.env`
  - `.codex/bfd/bootstrap_report.md`
  - `.codex/bfd/ioc_json/`
- 兼容镜像：
  - `.codex/stm32/bootstrap/active_profile.json`
  - `.codex/stm32/bootstrap/active_profile.env`
- 自动刷新：
  - `build_tools/jlink/profile_env.sh` 会调用 `ensure_profile.py`
  - `rtt_plot_live.py` 会优先读取 `.codex/bfd/active_profile.env`
- 本地运行时：
  - `BFD-Kit/.runtime/venv`
  - `BFD-Kit/scripts/install_python_runtime.sh` 负责安装 `pyelftools`
  - `BFD-Kit/scripts/bfd_jlink_hss.sh` 会自动使用该本地运行时

## 在现有项目中接入

```bash
bash BFD-Kit/init_project.sh --project-root .
python3 BFD-Kit/scripts/migrate_bfd_skills.py --mode stage
python3 BFD-Kit/scripts/migrate_bfd_skills.py --mode cutover
```

- `stage`：把当前 `.codex/.claude` 活动 BFD 技能导入到 `BFD-Kit/`
- `cutover`：把 `BFD-Kit/` 技能回灌到活动镜像，并自动备份到 `archive/skills_migration/`

## 维护说明

- 维护多份 BFD-Kit 副本时，应保持技能、脚本、文档和 `.learnings` 内容一致。
- 对外文档与代理提示词中不要暴露本地绝对路径、工作区拓扑、镜像关系或仓库边界细节。
- 从任意仓库发布前，先核对当前仓库根目录、remote、branch 和 worktree 状态。
- 通用维护清单见 `BFD-Kit/MAINTENANCE-zh.md`。

## 快速验证

```bash
bash BFD-Kit/init_project.sh --help
bash BFD-Kit/scripts/install_python_runtime.sh --help
python3 BFD-Kit/scripts/bfd_jlink_hss.py --help
python3 BFD-Kit/scripts/migrate_bfd_skills.py --help
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
python3 ./.codex/skills/bfd-project-init/scripts/ensure_profile.py --project-root . --print-env-path
python3 ./.codex/skills/bfd-cubemx-codegen/scripts/generate_from_ioc.py --help
```
