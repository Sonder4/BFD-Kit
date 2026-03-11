# STM32H723 内存映射文档

本文档记录 STM32H723VGTx 芯片的内存映射信息，基于 STM32H7 系列参考手册 (RM0468)。

## 官方内存布局 (GCC Linker Script)

```ld
MEMORY
{
    /* Flash: 1MB，起始地址 0x08000000，长度 1024K */
    /* 依据：手册第 1 页 Features 及 3.3.1 节 Embedded flash memory */
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1024K

    /* DTCM RAM: 128KB，起始地址 0x20000000，长度 128K */
    /* 依据：手册 3.3.2 节 Embedded SRAM，明确 128KB DTCM-RAM (data) */
    DTCMRAM (xrw) : ORIGIN = 0x20000000, LENGTH = 128K

    /* AXI SRAM: 320KB，起始地址 0x24000000，长度 320K */
    /* 依据：手册 3.3.2 节及 Table 1，AXI SRAM 固定 128KB + 可共享 192KB = 320KB */
    RAM_D1 (xrw)  : ORIGIN = 0x24000000, LENGTH = 320K

    /* D2 域 SRAM：共 32KB，分为两块 16KB 的连续区域 */
    /* 依据：手册 3.3.2 节及 Table 1，SRAM1 (D2) = 16KB，SRAM2 (D2) = 16KB */
    /* 地址参考 STM32H7 系列参考手册 RM0468：SRAM1 0x30000000，SRAM2 0x30004000 */
    SRAM1 (xrw)   : ORIGIN = 0x30000000, LENGTH = 16K
    SRAM2 (xrw)   : ORIGIN = 0x30004000, LENGTH = 16K

    /* D3 域 SRAM4: 16KB，起始地址 0x38000000 */
    /* 依据：手册 3.3.2 节及 Table 1，SRAM4 (D3) = 16KB，地址参考 RM0468 为 0x38000000 */
    SRAM4 (xrw)   : ORIGIN = 0x38000000, LENGTH = 16K

    /* Backup SRAM: 4KB，起始地址 0x38800000 */
    /* 依据：手册 3.3.2 节及 Table 1，Backup SRAM = 4KB，地址参考 RM0468 为 0x38800000 */
    BKPSRAM (xrw) : ORIGIN = 0x38800000, LENGTH = 4K

    /* ITCM RAM: 64KB，起始地址 0x00000000 */
    /* 依据：手册 3.3.2 节及 Table 1，ITCM RAM 最小 64KB（可扩展至 256KB） */
    ITCMRAM (xrw) : ORIGIN = 0x00000000, LENGTH = 64K
}
```

## 内存区域详解

| 区域 | 起始地址 | 结束地址 | 大小 | 说明 |
|------|---------|---------|------|------|
| **FLASH** | 0x08000000 | 0x087FFFFF | 512KB x 2 | 双-bank Flash，可独立读写 |
| **DTCMRAM** | 0x20000000 | 0x2001FFFF | 128KB | Data Tightly Coupled Memory |
| **ITCMRAM** | 0x00000000 | 0x0000FFFF | 64KB | Instruction Tightly Coupled Memory |
| **RAM (AXI)** | 0x24000000 | 0x2407FFFF | 512KB | AXI SRAM (主SRAM) |
| **SRAM1 (D2)** | 0x30000000 | 0x30003FFF | 16KB | AHB SRAM |
| **SRAM2 (D2)** | 0x30004000 | 0x30007FFF | 16KB | AHB SRAM |
| **SRAM4 (D3)** | 0x38000000 | 0x38003FFF | 16KB | AHB SRAM |
| **BKPSRAM** | 0x38800000 | 0x38800FFF | 4KB | Backup SRAM (RTC域) |

## 与项目链接器脚本对比

### Keil (RSCF_H7.sct)
```scat
LR_IROM1 0x08000000 0x00100000  {  ; 1MB Flash
  ER_IROM1 0x08000000 0x00100000 { }
  RW_IRAM1 0x20000000 0x00020000 { }  ; DTCM 128KB
  RW_IRAM2 0x24000000 0x00050000 { }  ; AXI SRAM 320KB
}
```

### GCC (STM32H723VGTx_FLASH.ld)
```ld
FLASH (rx)      : ORIGIN = 0x08000000, LENGTH = 1024K
DTCMRAM (xrw)  : ORIGIN = 0x20000000, LENGTH = 128K
RAM (xrw)       : ORIGIN = 0x24000000, LENGTH = 128K
RAM_D2 (xrw)    : ORIGIN = 0x30000000, LENGTH = 32K
RAM_D3 (xrw)    : ORIGIN = 0x38000000, LENGTH = 16K
ITCMRAM (xrw)   : ORIGIN = 0x00000000, LENGTH = 64K
```

## 工具使用

### 分析脚本
```bash
# 使用 GCC 链接器脚本
python analyze_startup.py --startup startup_stm32h723xx.s --linker STM32H723VGTx_FLASH.ld

# 使用 Keil 链接器脚本
python analyze_startup.py --startup startup_stm32h723xx.s --linker RSCF_H7.sct
```

### 输出文件
- `docs/ioc_json/startup_analysis.json`
