/*******************************************************************************

                      版权所有 (C), 2025-2026, NCU_Roboteam

 *******************************************************************************
  文 件 名: debug_fault_template.c
  版 本 号: V20260307.1
  作    者: Claude
  生成日期: 2026年3月7日
  功能描述: 调试故障注入模板源文件
  补    充: 迁移时请替换日志头文件与芯片公共头文件

*******************************************************************************/

/********************************包含头文件************************************/
#include "debug_fault.h"

#include "bsp_log.h"
#include "main.h"

/*******************************文件内宏定义***********************************/
#define DEBUG_FAULT_SCENARIO_NONE                0U
#define DEBUG_FAULT_SCENARIO_IMU_COMM_FAULT      1U
#define DEBUG_FAULT_SCENARIO_FLASH_PARAM_FAULT   2U
#define DEBUG_FAULT_SCENARIO_HARDFAULT_BAD_PTR   3U
#define DEBUG_FAULT_SCENARIO_USAGEFAULT_UDF      4U

/*******************************全局变量定义***********************************/
volatile uint32_t g_debug_fault_scenario = 0U;

/********************************文件内变量************************************/
static uint32_t s_last_triggered_scenario = DEBUG_FAULT_SCENARIO_NONE;
static uint8_t s_fault_armed = 0U;

/********************************文件内函数声明********************************/
static void DebugFaultTriggerScenario(uint32_t scenario);
static void DebugFaultTriggerHardFaultByBadPointer(void);
__attribute__((noreturn)) static void DebugFaultTriggerUsageFaultByUdf(void);

/********************************自定义函数************************************/
/**********************************************************************
  * 函数名  : DebugFaultInit
  * 功能说明: 初始化调试故障注入模块状态
  * 参数    : 无
  * 返回值  : 无
  **********************************************************************/
void DebugFaultInit(void)
{
  g_debug_fault_scenario = DEBUG_FAULT_SCENARIO_NONE;
  s_last_triggered_scenario = DEBUG_FAULT_SCENARIO_NONE;
  s_fault_armed = 0U;
}

/**********************************************************************
  * 函数名  : DebugFaultTask
  * 功能说明: 在周期任务中轮询并执行一次性故障注入
  * 参数    : 无
  * 返回值  : 无
  **********************************************************************/
void DebugFaultTask(void)
{
  uint32_t scenario = g_debug_fault_scenario;

  if (scenario == DEBUG_FAULT_SCENARIO_NONE)
  {
    s_fault_armed = 0U;
    return;
  }

  if ((s_fault_armed != 0U) && (scenario == s_last_triggered_scenario))
  {
    return;
  }

  s_fault_armed = 1U;
  s_last_triggered_scenario = scenario;
  g_debug_fault_scenario = DEBUG_FAULT_SCENARIO_NONE;

  DebugFaultTriggerScenario(scenario);
}

/********************************文件内函数************************************/
/**********************************************************************
  * 函数名  : DebugFaultTriggerScenario
  * 功能说明: 根据场景值执行对应的调试故障动作
  * 参数    : uint32_t scenario - 调试故障场景编号
  * 返回值  : 无
  **********************************************************************/
static void DebugFaultTriggerScenario(uint32_t scenario)
{
  switch (scenario)
  {
    case DEBUG_FAULT_SCENARIO_IMU_COMM_FAULT:
      LOGWARNING("[DEBUG_FAULT] scenario=1 IMU_COMM_FAULT injected");
      break;

    case DEBUG_FAULT_SCENARIO_FLASH_PARAM_FAULT:
      LOGERROR("[DEBUG_FAULT] scenario=2 FLASH_PARAM_FAULT injected");
      break;

    case DEBUG_FAULT_SCENARIO_HARDFAULT_BAD_PTR:
      LOGERROR("[DEBUG_FAULT] scenario=3 trigger bad pointer hard fault");
      DebugFaultTriggerHardFaultByBadPointer();
      break;

    case DEBUG_FAULT_SCENARIO_USAGEFAULT_UDF:
      LOGERROR("[DEBUG_FAULT] scenario=4 trigger UDF usage fault");
      DebugFaultTriggerUsageFaultByUdf();
      break;

    default:
      LOGWARNING("[DEBUG_FAULT] unsupported scenario=%lu", scenario);
      break;
  }
}

/**********************************************************************
  * 函数名  : DebugFaultTriggerHardFaultByBadPointer
  * 功能说明: 通过非法地址写入触发真实 fault
  * 参数    : 无
  * 返回值  : 无
  * 补充说明: 可按目标工程替换为更稳定的 trap 手段
  **********************************************************************/
static void DebugFaultTriggerHardFaultByBadPointer(void)
{
  volatile uint32_t* fault_addr = (volatile uint32_t*)0x00000001UL;

  *fault_addr = 0xDEADBEEFUL;

  for (;;)
  {
  }
}

/**********************************************************************
  * 函数名  : DebugFaultTriggerUsageFaultByUdf
  * 功能说明: 通过未定义指令触发 UsageFault 或升级后的 HardFault
  * 参数    : 无
  * 返回值  : 无
  * 补充说明: 若工具链不支持 udf，可替换为工程内可复现 trap
  **********************************************************************/
__attribute__((noreturn)) static void DebugFaultTriggerUsageFaultByUdf(void)
{
#if defined(__CC_ARM) || defined(__ARMCC_VERSION)
  __asm("UDF #0");
#elif defined(__clang__) && defined(__arm__)
  __asm volatile("udf #0");
#else
  __builtin_trap();
#endif

  for (;;)
  {
  }
}

/******************************** 文件结束 ************************************/
