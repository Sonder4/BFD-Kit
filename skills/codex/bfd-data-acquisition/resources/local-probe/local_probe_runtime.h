/*******************************************************************************

                      版权所有 (C), 2025-2026, NCU_Roboteam

 *******************************************************************************
  文 件 名: local_probe_runtime.h
  版 本 号: V20260311.1
  作    者: Codex
  生成日期: 2026-03-11
  功能描述: 局部变量运行时地址发布接口模板
  补    充: 供 BFD 数据采集技能复用，用于把栈上局部变量地址发布到全局槽位

*******************************************************************************/

/****************************头文件开头必备内容********************************/
#ifndef __LOCAL_PROBE_RUNTIME_H
#define __LOCAL_PROBE_RUNTIME_H

/********************************包含头文件************************************/
#include <stdint.h>

/*******************************文件内宏定义***********************************/
#ifndef BFD_LOCAL_PROBE_DMB
#define BFD_LOCAL_PROBE_DMB() __asm volatile("dmb" ::: "memory")
#endif

/*******************************文件内结构体***********************************/
typedef enum
{
    BFD_LOCAL_PROBE_TYPE_NONE = 0U,
    BFD_LOCAL_PROBE_TYPE_U32 = 1U,
    BFD_LOCAL_PROBE_TYPE_S32 = 2U,
    BFD_LOCAL_PROBE_TYPE_F32 = 3U,
} BfdLocalProbeType_e;

typedef struct
{
    volatile uintptr_t addr;
    volatile uint32_t seq;
    volatile uint32_t size;
    volatile uint32_t type;
    volatile uint32_t heartbeat;
    volatile uint32_t drop_count;
} BfdLocalProbeSlot_t;

/*******************************全局变量声明***********************************/
#define BFD_LOCAL_PROBE_DEFINE_SLOT(name) BfdLocalProbeSlot_t name = {0}

/********************************自定义函数************************************/
/**********************************************************************
  * @ 函数名  ： BfdLocalProbeInit
  * @ 功能说明： 初始化局部变量发布槽位
  * @ 参数    ： slot: 需要初始化的槽位指针
  * @ 返回值  ： 无
  * @todo    可扩展为多槽位注册表
  ********************************************************************/
void BfdLocalProbeInit(volatile BfdLocalProbeSlot_t *slot);

/**********************************************************************
  * @ 函数名  ： BfdLocalProbePublish
  * @ 功能说明： 发布局部变量当前地址、尺寸和类型
  * @ 参数    ： slot: 目标槽位
  * @ 参数    ： addr: 局部变量当前地址
  * @ 参数    ： size: 局部变量字节数
  * @ 参数    ： type: 局部变量类型标识
  * @ 返回值  ： 无
  * @todo    后续可扩展为结构体字段描述
  ********************************************************************/
void BfdLocalProbePublish(
    volatile BfdLocalProbeSlot_t *slot,
    const volatile void *addr,
    uint32_t size,
    uint32_t type);

#endif
/******************************** 文件结束 ************************************/
