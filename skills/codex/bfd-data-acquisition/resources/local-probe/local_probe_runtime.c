/*******************************************************************************

                      版权所有 (C), 2025-2026, NCU_Roboteam

 *******************************************************************************
  文 件 名: local_probe_runtime.c
  版 本 号: V20260311.1
  作    者: Codex
  生成日期: 2026-03-11
  功能描述: 局部变量运行时地址发布接口模板实现
  补    充: 通过双相序号协议保证主机侧读取地址与数据时的一致性判断

*******************************************************************************/

/********************************包含头文件************************************/
#include "local_probe_runtime.h"

/********************************自定义函数************************************/
/**********************************************************************
  * @ 函数名  ： BfdLocalProbeInit
  * @ 功能说明： 初始化局部变量发布槽位
  * @ 参数    ： slot: 需要初始化的槽位指针
  * @ 返回值  ： 无
  * @todo    后续可补充版本号和标签字段
  ********************************************************************/
void BfdLocalProbeInit(volatile BfdLocalProbeSlot_t *slot)
{
    if (slot == 0)
    {
        return;
    }

    slot->addr = 0U;
    slot->seq = 0U;
    slot->size = 0U;
    slot->type = BFD_LOCAL_PROBE_TYPE_NONE;
    slot->heartbeat = 0U;
    slot->drop_count = 0U;
}

/**********************************************************************
  * @ 函数名  ： BfdLocalProbePublish
  * @ 功能说明： 发布局部变量当前地址、尺寸和类型
  * @ 参数    ： slot: 目标槽位
  * @ 参数    ： addr: 局部变量当前地址
  * @ 参数    ： size: 局部变量字节数
  * @ 参数    ： type: 局部变量类型标识
  * @ 返回值  ： 无
  * @todo    可在无效地址时增加丢帧计数策略
  ********************************************************************/
void BfdLocalProbePublish(
    volatile BfdLocalProbeSlot_t *slot,
    const volatile void *addr,
    uint32_t size,
    uint32_t type)
{
    uint32_t seq;

    if ((slot == 0) || (addr == 0))
    {
        if (slot != 0)
        {
            slot->drop_count++;
        }
        return;
    }

    seq = slot->seq;
    slot->seq = seq + 1U;
    BFD_LOCAL_PROBE_DMB();

    slot->addr = (uintptr_t)addr;
    slot->size = size;
    slot->type = type;
    slot->heartbeat++;

    BFD_LOCAL_PROBE_DMB();
    slot->seq = seq + 2U;
}
/******************************** 文件结束 ************************************/
