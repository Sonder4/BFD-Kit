# Errors

编译失败、烧录失败、调试异常、脚本使用问题、其他意外行为。

**Areas**: build | flash | debug | scripts | docs | config | workflow
**Statuses**: pending | resolved

---

- id: error-20260312-jlink-flash-permission-denied
  area: flash
  status: resolved
  summary: 直接执行 ./build_tools/jlink/flash.sh 时返回 Permission denied，根因是脚本缺少执行位；改用 bash ./build_tools/jlink/flash.sh 后烧录成功。

- id: error-20260312-rtt-quick-no-payload-for-motor-check
  area: debug
  status: resolved
  summary: quick RTT attach 返回 fallback_no_payload，不能用于判定 M3508 在线状态；改用 J-Link RAM 采样读取 __hub_m3508_inst 和 measure 字段后确认 1-4 号电机均有有效反馈。

- id: error-20260312-global-symbol-sampling-too-manual
  area: scripts
  status: resolved
  summary: 缺少“ELF + symbol + decode profile”的标准命令前，AI 需要临时设计 GDB/JLink 内存读取与十六进制解码命令；现已补充 symbol mode、内置 decode profile 和 RTT 失败后的 RAM sampling 固定模板。

- id: error-20260312-bfd-data-acq-profile-default-from-bfd-kit
  area: scripts
  status: resolved
  summary: 从 BFD-Kit 镜像路径直接运行 data_acq.py 时，旧实现未正确向上定位 .codex/bfd/active_profile.env，导致设备默认值回退为硬编码 STM32H743VI；现已改为沿父目录搜索 profile。

- id: error-20260312-jlink-session-contention-on-parallel-sampling
  area: workflow
  status: resolved
  summary: 并行执行两个 J-Link RAM 采样命令会竞争同一 probe，后启动会话可能返回 Cannot connect to J-Link；对同一目标的 J-Link 采样必须串行执行。

- id: error-20260312-symbol-auto-cache-builtin-scalar-gap
  area: scripts
  status: resolved
  summary: symbol-auto 的 DWARF cache 二次回读未命中，根因是 `long long unsigned int` 等基础类型未被视为内建标量，导致递归类型装载回退到 rebuild；现已补齐基础类型白名单与通用解码支持。

- id: error-20260313-jscope-gui-automation-input-leak
  area: debug
  status: resolved
  summary: 基于 GUI 焦点和按键注入的 J-Scope 自动化会把控制字符和文本误输到其他窗口，且不满足“无输入法/按键依赖”的要求；现已改为 `libjlinkarm.so` 原生 HSS CLI 路径。

- id: error-20260313-bfd-kit-hss-external-cli-dependency
  area: scripts
  status: resolved
  summary: 原生 HSS 能力最初只存在于外部 `CLI-Anything` 仓库，导致 BFD-Kit skill 文档能引用但目标项目无法直接分发使用；现已将 HSS CLI、运行时安装脚本和 skill 入口完整收敛到 BFD-Kit。
