# Learnings

经验、纠正、知识空白、最佳实践、任务回顾。

**Categories**: correction | knowledge_gap | best_practice | task_review
**Areas**: build | flash | debug | scripts | docs | config | workflow
**Statuses**: pending | resolved | promoted | promoted_to_skill

---

- id: learning-20260311-bfd-kit-feedback-loop
  category: best_practice
  area: workflow
  status: promoted_to_skill
  summary: 编译、烧录、调试与脚本问题在解决后，应立即回写到 BFD-Kit 的 skill 与脚本，避免同类问题重复处理。
  promoted_to:
    - AGENTS.md
    - BFD-Kit/skills/codex/*
    - BFD-Kit/skills/claude/*

- id: learning-20260312-bfd-jlink-flash-bash-wrapper
  category: best_practice
  area: flash
  status: promoted
  summary: 当 build_tools/jlink/flash.sh 缺少执行权限时，应直接使用 bash 包装调用并保留原始日志，而不是误判为 J-Link 或目标连接失败。
  promoted_to:
    - BFD-Kit/skills/codex/bfd-flash-programmer/SKILL.md

- id: learning-20260312-bfd-motor-feedback-ram-first
  category: best_practice
  area: debug
  status: promoted
  summary: 在本仓库的 STM32F427 + DJI M3508 联调中，quick RTT 可能没有有效 payload；电机在线与反馈核查应优先读取 RAM 中的 DJIMotor measure 结构体。
  promoted_to:
    - BFD-Kit/skills/codex/bfd-rtt-logger/SKILL.md

- id: learning-20260312-bfd-symbol-sampling-standard
  category: best_practice
  area: scripts
  status: promoted
  summary: 对全局变量、指针数组和 DJI 电机实例反馈的 RAM 采样，应统一走 ELF symbol + decode profile + summary/json/csv 输出流程，而不是临时拼接 GDB/JLink 命令和手工解码。
  promoted_to:
    - BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py
    - BFD-Kit/skills/codex/bfd-data-acquisition/SKILL.md
    - BFD-Kit/skills/codex/bfd-debug-interface/SKILL.md
    - BFD-Kit/skills/codex/bfd-rtt-logger/SKILL.md

- id: learning-20260312-bfd-profile-search-upward
  category: best_practice
  area: scripts
  status: promoted
  summary: 供 AI 直接调用的 BFD-Kit 脚本不能假定固定目录深度，应沿父目录搜索 `.codex/bfd/active_profile.env` 与兼容 profile，否则镜像路径与活跃路径会出现默认设备不一致。
  promoted_to:
    - BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py

- id: learning-20260312-jlink-sampling-must-be-serialized
  category: best_practice
  area: workflow
  status: resolved
  summary: 对同一目标板的 J-Link RAM sampling、RTT 和 GDB attach 需要串行执行；并发会话会导致 probe 争用并返回 Cannot connect to J-Link。

- id: learning-20260312-bfd-symbol-auto-cache
  category: best_practice
  area: scripts
  status: promoted
  summary: 对全局或静态对象的 RAM 解码应优先使用 `symbol-auto`，并把 `.codex/bfd/dwarf_cache/` 作为标准 schema cache；cache 回读必须把基础整数、浮点和布尔类型视为内建叶子节点，而不是要求每个基础类型都落盘为独立 schema 文件。
  promoted_to:
    - BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py
    - BFD-Kit/skills/codex/bfd-data-acquisition/scripts/dwarf_decode.py
    - BFD-Kit/skills/codex/bfd-data-acquisition/SKILL.md
    - BFD-Kit/skills/codex/bfd-debug-interface/SKILL.md
    - BFD-Kit/skills/codex/bfd-rtt-logger/SKILL.md

- id: learning-20260313-jlink-hss-native-nonhalting-path
  category: best_practice
  area: debug
  status: promoted
  summary: 当任务要求 J-Link 高速、非阻塞、无 GUI 输入依赖地采样固定地址标量变量时，应优先使用基于 `libjlinkarm.so` 的原生 HSS CLI，而不是 J-Scope 自动化或 halt/read/go 轮询。
  promoted_to:
    - BFD-Kit/scripts/bfd_jlink_hss.py
    - BFD-Kit/scripts/bfd_jlink_hss.sh
    - BFD-Kit/scripts/install_python_runtime.sh
    - BFD-Kit/init_project.sh
    - BFD-Kit/skills/codex/bfd-data-acquisition/SKILL.md
    - BFD-Kit/skills/claude/bfd-data-acquisition/SKILL.md
    - BFD-Kit/README.md
    - BFD-Kit/README-zh.md
    - BFD-Kit/README-en.md

- id: learning-20260314-jlink-hss-multi-block-descriptor
  category: correction
  area: debug
  status: promoted
  summary: J-Link HSS 的多 block 原生描述符在当前 DLL 上需要 16-byte stride；若按 8-byte `{address, byte_size}` 传入，第二个 block 会被解释为 `0 bytes @ 0x00000000`，导致输出只包含第一个 symbol。
  promoted_to:
    - BFD-Kit/scripts/bfd_jlink_hss_core/jlink_dll.py
    - BFD-Kit/scripts/bfd_jlink_hss_core/hss_sampling.py
    - BFD-Kit/scripts/tests/test_bfd_jlink_hss_core.py
    - BFD-Kit/scripts/tests/test_bfd_jlink_hss_cli.py
    - BFD-Kit/skills/codex/bfd-data-acquisition/SKILL.md
    - BFD-Kit/skills/claude/bfd-data-acquisition/SKILL.md
    - BFD-Kit/README.md
    - BFD-Kit/README-zh.md
    - BFD-Kit/README-en.md

- id: learning-20260314-jlink-hss-cap-word-2-not-var-limit
  category: correction
  area: debug
  status: promoted
  summary: `JLINK_HSS_GetCaps()` 返回的第 3 个 raw word 不能直接解释为最大变量数；在当前 `J-Link PLUS` 上它读到 2，但原生 HSS 和官方型号限制都表明实际可采样上限是 10 个变量。
  promoted_to:
    - BFD-Kit/scripts/bfd_jlink_hss_core/jlink_dll.py
    - BFD-Kit/scripts/bfd_jlink_hss_core/hss_sampling.py
    - BFD-Kit/scripts/tests/test_bfd_jlink_hss_core.py
    - BFD-Kit/README.md
    - BFD-Kit/README-zh.md
    - BFD-Kit/README-en.md
    - BFD-Kit/skills/codex/bfd-data-acquisition/SKILL.md
    - BFD-Kit/skills/claude/bfd-data-acquisition/SKILL.md

- id: learning-20260314-bfd-doc-sanitization
  category: best_practice
  area: docs
  status: promoted
  summary: 面向项目使用者的 BFD-Kit 文档与代理提示词应保持通用维护表述，不暴露本地绝对路径、工作区拓扑、镜像关系或仓库发布边界；内部真源规则只保留在工作区级 AGENTS 文档。
  promoted_to:
    - BFD-Kit/README.md
    - BFD-Kit/README-zh.md
    - BFD-Kit/STM32_AGENT_PROMPT-zh.md
    - BFD-Kit/MAINTENANCE-zh.md
