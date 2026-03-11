# STM32 `g_debug_fault_scenario` 接入说明

本资源目录提供 `bfd-debug-orchestrator` 所需的最小故障注入基线，便于迁移到任意 STM32 工程。目标是在不修改调试脚本的前提下，让 J-Link 能直接向 ELF 中的 `g_debug_fault_scenario` 写入场景值，并由固件周期任务消费后产生可观测结果。

## 目标能力

- 导出全局符号 `volatile uint32_t g_debug_fault_scenario`
- 提供 `DebugFaultInit()` 与 `DebugFaultTask()` 两个最小接口
- 在周期任务中轮询一次性消费场景值，避免重复触发和 RTT 刷屏
- 为 soft fault 场景输出 RTT 证据
- 为 hard fault 场景制造调试器可见的真实 CPU 异常

## 需要新增的文件

把本目录下模板复制到目标工程的用户可维护目录，例如：

- `USER/Modules/debug_fault/debug_fault.h`
- `USER/Modules/debug_fault/debug_fault.c`

推荐直接复制：

- `f4/debug_fault_template.h`
- `f4/debug_fault_template.c`

如果目标工程不是 F4，也可以基于同样接口改写模板，但必须保留 `g_debug_fault_scenario` 符号名与 `DebugFaultInit()` / `DebugFaultTask()` 接口名。

## 需要修改的工程文件

至少修改一处现有周期入口文件，例如：

- 主控应用轮询函数
- FreeRTOS 周期任务入口
- 主循环调度点

最小接入方式：

1. 在初始化路径调用 `DebugFaultInit()`
2. 在约 1 ms 到 10 ms 的周期任务中调用 `DebugFaultTask()`
3. 保证 `debug_fault.c` 被构建系统编入最终 ELF

如果工程使用 CMake 且自动递归收集 `USER/**/*.c`，通常只需把模板放进已有源码目录即可；如果工程显式列源文件，则还需要把 `debug_fault.c` 加入工程文件列表。

## 必须暴露的全局符号

调试脚本会通过 `arm-none-eabi-nm` 查找下面这个精确符号名：

```c
volatile uint32_t g_debug_fault_scenario;
```

如果符号名不同，`inject_fault_scenario.sh` 会报错：

```text
symbol g_debug_fault_scenario not found in ELF
```

## 场景值语义

- `1`：可恢复软故障，输出 `IMU_COMM_FAULT` 风格日志，系统继续运行
- `2`：可恢复参数异常，输出 `FLASH_PARAM_FAULT` 风格日志，系统继续运行
- `3`：触发非法地址访问，制造真实 HardFault 或等价硬异常
- `4`：触发未定义指令，制造 UsageFault 或升级后的 HardFault

建议对未知值仅打印一次 warning，并在 0 被重新写回之前不重复刷屏。

## 推荐的周期挂接方式

```c
void AppInit(void)
{
  DebugFaultInit();
}

void AppTask(void)
{
  DebugFaultTask();
}
```

建议挂到应用层中心周期路径，而不是底盘、电机、通信等专用子模块内部，这样耦合最低，也更方便跨工程迁移。

## 模板中需要按工程替换的部分

模板内以下内容通常需要按目标工程调整：

- 日志头文件，例如 `bsp_log.h`
- 芯片公共头文件，例如 `main.h`
- 具体日志宏，例如 `LOGWARNING` / `LOGERROR`
- 确定性 fault 触发方式（若工具链或内核配置有差异）

## 推荐验证步骤

### 1. 基线验证

- 下载固件并启动
- 保持 `g_debug_fault_scenario = 0`
- 确认 RTT 基线输出与原工程一致，没有新增周期刷屏

### 2. RTT 语义要求

- `quick` 仅用于 attach-only 观察，适合场景 `1/2` 的软故障证据抓取
- `quick` 采集必须保证 inject 之后到日志抓取完成之前没有额外 reset，否则 RAM 中的 `g_debug_fault_scenario` 会被清空
- `dual` 用于场景 `3/4` 的故障恢复验证，允许通过同一 GDBServer 后端执行 `reset/go`
- 如果目标工程也用 RAM 注入变量承载 soft fault，迁移 RTT 工具链时必须显式保留这两种不同语义

### 3. 单项场景验证

- 写入 `1`，确认出现一次软故障日志，系统继续运行
- 写入 `2`，确认出现一次参数异常日志，系统继续运行
- 写入 `3`，确认目标进入真实 fault，可被调试链路捕获
- 写入 `4`，确认目标进入第二类真实 fault，可被调试链路捕获
- 写入未知值如 `99`，确认只出现一次 warning

### 4. Orchestrator 端到端验证

- 重新构建 ELF，确认符号可被 `arm-none-eabi-nm` 查到
- 运行 `inject_fault_scenario.sh --scenario 1`
- 再运行 `run_fault_campaign.sh --skip-build --build-dir <your-build-dir> --scenarios 1`
- 分别复测场景 `2`、`3`、`4`
- 确认 soft fault 有 RTT 证据，hard fault 能推进到快照抓取脚本

## 资源复制建议

当把 `bfd-debug-orchestrator` 迁移到新工程时，优先直接复制本资源目录中的模板，而不是手动从 `SKILL.md` 抄写代码。这样可以保证：

- 符号名一致
- 场景编号一致
- 接口名一致
- 文档与模板同步演进
