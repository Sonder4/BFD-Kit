# STM32 数据采集技术参考

## 概述

本文档提供STM32实时数据采集的完整技术参考，包括J-Link RTT、ST-Link GDB、内存监控等方法的详细说明。

## 目录

1. [J-Link RTT 实时传输](#j-link-rtt-实时传输)
2. [ST-Link 调试接口](#st-link-调试接口)
3. [内存区域监控](#内存区域监控)
4. [采样率配置](#采样率配置)
5. [数据格式规范](#数据格式规范)
6. [波形显示与分析](#波形显示与分析)
7. [故障排除](#故障排除)

---

## J-Link RTT 实时传输

### RTT 简介

RTT (Real-Time Transfer) 是SEGGER提供的高速实时数据传输技术：

- **零开销**：对目标程序影响极小
- **高速传输**：最高可达 1 MB/s
- **双向通信**：支持主机到目标的数据传输
- **多通道**：支持最多16个独立通道

### RTT 工具路径

```text
J-Link 工具从系统 `PATH` 解析。

常用工具:
- JLinkExe             : 命令行调试器
- JLinkGDBServerCLExe  : GDB 服务器
- JLinkRTTViewer       : RTT 图形界面查看器
- JLinkRTTClient       : RTT 命令行客户端
- JLinkRTTLogger       : RTT 数据记录器
```

### 目标代码集成

#### 1. 添加RTT源文件

从J-Link安装目录复制以下文件到项目：
```
SEGGER_RTT.c
SEGGER_RTT.h
SEGGER_RTT_Conf.h
```

#### 2. 初始化配置

```c
#include "SEGGER_RTT.h"

// 在main函数开始处初始化
int main(void) {
    SEGGER_RTT_Init();
    // ...
}
```

#### 3. 数据输出

```c
// 格式化输出（类似printf）
SEGGER_RTT_printf(0, "Temperature: %d.%d C\n", temp_int, temp_frac);

// 二进制数据输出
uint8_t adc_data[64];
SEGGER_RTT_Write(0, adc_data, sizeof(adc_data));

// 多通道使用
SEGGER_RTT_printf(0, "Debug: %s\n", msg);      // 通道0：调试信息
SEGGER_RTT_printf(1, "DATA:%d,%d,%d\n", x, y, z); // 通道1：数据记录
```

#### 4. 配置选项 (SEGGER_RTT_Conf.h)

```c
// 缓冲区大小配置
#define BUFFER_SIZE_UP    (1024)  // 上行缓冲区（目标->主机）
#define BUFFER_SIZE_DOWN  (16)    // 下行缓冲区（主机->目标）

// 通道数量
#define SEGGER_RTT_MAX_NUM_UP_BUFFERS   (3)  // 上行通道数
#define SEGGER_RTT_MAX_NUM_DOWN_BUFFERS (3)  // 下行通道数

// 模式选择
#define SEGGER_RTT_MODE_DEFAULT  SEGGER_RTT_MODE_NO_BLOCK_SKIP
```

### RTT Viewer 使用

```bash
# 启动 RTT Viewer
JLinkRTTViewer

# 命令行参数
JLinkRTTViewer -device STM32F427II -if SWD -speed 4000
```

**RTT Viewer 配置：**
- Connection: USB
- Device: STM32F427II
- Interface: SWD
- Speed: 4000 kHz
- RTT Control Block: Auto Detection

### RTT Logger 使用

```bash
# 记录 RTT 数据到文件
JLinkRTTLogger -device STM32F427II -if SWD -speed 4000 -rttchannel 0 -logfile data.log
```

---

## ST-Link 调试接口

### ST-Link 工具路径

```text
ST-Link 工具从系统 `PATH` 解析。

常用工具:
- ST-LINK_gdbserver : GDB 调试服务器
- ST-LINK_CLI       : 命令行工具
```

### GDB Server 启动

```bash
# 启动 GDB 服务器（默认端口 61234）
ST-LINK_gdbserver -p 61234 -m 1

# 参数说明:
# -p : 端口号
# -m : 模式 (1=SWD, 2=JTAG)
# -v : 详细输出
# -l : 日志级别
```

### GDB 连接与数据读取

```bash
# 启动GDB
arm-none-eabi-gdb

# GDB命令
(gdb) file ${STM32_ELF}               # 加载符号
(gdb) target remote localhost:61234  # 连接目标
(gdb) load                           # 加载程序（可选）

# 读取内存
(gdb) x/100xw 0x20000000             # 读取100个word
(gdb) x/50h &g_adcBuffer             # 读取50个halfword

# 读取变量
(gdb) print g_sensorValue            # 打印变量值
(gdb) print/x g_sensorValue          # 十六进制格式

# 导出内存
(gdb) dump binary memory data.bin 0x20000000 0x20000100

# 监视点
(gdb) watch g_flag                   # 写入监视
(gdb) rwatch g_data                  # 读取监视
(gdb) awatch g_status                # 访问监视
```

### 自动化脚本示例

```python
# gdb_script.txt
file ${STM32_ELF}
target remote localhost:61234
set pagination off
set logging file data.log
set logging on

# 循环读取变量
define dump_data
    set $i = 0
    while $i < 100
        printf "%d,%d\n", $i, g_adcBuffer[$i]
        set $i = $i + 1
    end
end

dump_data
quit
```

---

## 内存区域监控

### STM32F427 内存映射

| 区域 | 起始地址 | 结束地址 | 大小 | 说明 |
|------|----------|----------|------|------|
| CCM SRAM | 0x10000000 | 0x1000FFFF | 64KB | Core Coupled Memory |
| SRAM1/2/3 | 0x20000000 | 0x2002FFFF | 192KB | 主 SRAM |
| Backup SRAM | 0x40024000 | 0x40024FFF | 4KB | 备份域 SRAM |
| Flash | 0x08000000 | 0x081FFFFF | 2MB | 主 Flash |

### 外设寄存器地址范围

| 外设 | 起始地址 | 说明 |
|------|----------|------|
| GPIOA | 0x40020000 | GPIO端口A |
| GPIOB | 0x40020400 | GPIO端口B |
| USART1 | 0x40011000 | 串口1 |
| USART2 | 0x40004400 | 串口2 |
| SPI1 | 0x40013000 | SPI1 |
| ADC1 | 0x40012000 | ADC1 |
| TIM1 | 0x40010000 | 定时器1 |
| CAN1 | 0x40006400 | bxCAN 控制器 |

### 内存监控脚本

```python
import subprocess
import struct
import time

def read_memory_jlink(device, address, size, count=1):
    """通过J-Link读取内存"""
    script = f"""device {device}
si SWD
speed 4000
connect
mem32 {hex(address)} {count}
exit
"""
    with open('temp.jlink', 'w') as f:
        f.write(script)
    
    result = subprocess.run(
        ['JLinkExe', '-CommandFile', 'temp.jlink'],
        capture_output=True, text=True
    )
    
    values = []
    for line in result.stdout.split('\n'):
        if '=' in line:
            try:
                val = int(line.split('=')[1].strip(), 16)
                values.append(val)
            except:
                pass
    
    return values

def monitor_variable(device, var_address, interval_ms, count):
    """周期性监控变量"""
    samples = []
    start_time = time.time()
    
    for i in range(count):
        elapsed = time.time() - start_time
        value = read_memory_jlink(device, var_address, 4, 1)
        if value:
            samples.append({'time': elapsed, 'value': value[0]})
        time.sleep(interval_ms / 1000.0)
    
    return samples
```

---

## 采样率配置

### 采样率选择原则

根据奈奎斯特定理，采样率应至少为信号最高频率的2倍：
```
fs >= 2 * fmax
```

实际应用中建议使用 5-10 倍的采样率。

### 不同采集方式的采样率限制

| 方式 | 最高采样率 | 典型应用 |
|------|------------|----------|
| J-Link RTT | ~1 MB/s | 高速数据流 |
| GDB内存读取 | ~1-10 kHz | 变量监控 |
| J-Link内存轮询 | ~100 Hz | 低速监控 |
| SWV (Serial Wire Viewer) | ~2 Mbps | 指令跟踪 |

### 采样率配置示例

```c
// 目标代码 - 定时数据采集
#define SAMPLE_RATE_HZ  10000  // 10 kHz采样率

void TIM2_Init(void) {
    // 配置定时器产生采样触发
    TIM_HandleTypeDef htim2;
    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 0;
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = (SystemCoreClock / SAMPLE_RATE_HZ) - 1;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_Base_Init(&htim2);
    HAL_TIM_Base_Start_IT(&htim2);
}

void TIM2_IRQHandler(void) {
    if (__HAL_TIM_GET_FLAG(&htim2, TIM_FLAG_UPDATE)) {
        __HAL_TIM_CLEAR_FLAG(&htim2, TIM_FLAG_UPDATE);
        
        // 采集数据并通过RTT输出
        uint16_t adc_value = ADC1->DR;
        SEGGER_RTT_Write(0, &adc_value, sizeof(adc_value));
    }
}
```

### Python端采样率控制

```python
import time

class RateController:
    def __init__(self, rate_hz):
        self.interval = 1.0 / rate_hz
        self.last_time = time.time()
    
    def wait(self):
        elapsed = time.time() - self.last_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_time = time.time()

# 使用示例
controller = RateController(1000)  # 1 kHz
for i in range(10000):
    data = read_data()
    process(data)
    controller.wait()
```

---

## 数据格式规范

### CSV 格式规范

#### 单通道数据
```csv
timestamp,value
0.000000,2048
0.001000,2050
0.002000,2047
```

#### 多通道数据
```csv
timestamp,ch0,ch1,ch2,ch3
0.000000,2048,2050,2047,2049
0.001000,2049,2051,2048,2050
```

#### 带元数据注释
```csv
# Device: STM32F427II
# Variable: g_adcBuffer
# Sample Rate: 10000 Hz
# Date: 2026-02-21T10:30:00Z
timestamp,value
0.000000,2048
```

### JSON 格式规范

```json
{
  "metadata": {
    "device": "STM32F427II",
    "variable": "g_adcBuffer",
    "address": "0x20000000",
    "sample_rate": 10000,
    "sample_count": 1000,
    "timestamp": "2026-02-21T10:30:00Z",
    "units": "ADC counts",
    "resolution": 12
  },
  "statistics": {
    "min": 0,
    "max": 4095,
    "mean": 2048.5,
    "std": 15.2
  },
  "data": [
    {"time": 0.000000, "value": 2048},
    {"time": 0.000100, "value": 2050}
  ]
}
```

### 二进制格式规范

#### 数据包头
```c
typedef struct {
    uint32_t magic;          // 0x44415441 ("DATA")
    uint16_t version;        // 格式版本
    uint16_t flags;          // 标志位
    uint32_t sample_count;   // 采样点数
    uint32_t sample_rate;    // 采样率
    uint32_t data_type;      // 数据类型 (0=int8, 1=int16, 2=int32, 3=float)
    uint32_t channel_count;  // 通道数
    uint8_t  reserved[40];   // 保留
} DataHeader;  // 总计64字节
```

#### 数据存储
- 小端字节序 (Little Endian)
- 交错存储多通道数据

---

## 波形显示与分析

### Matplotlib 波形绘制

```python
import matplotlib.pyplot as plt
import numpy as np

def plot_waveform(timestamps, values, output_file, title="Waveform"):
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, values, linewidth=0.8)
    plt.xlabel('Time (s)')
    plt.ylabel('Value')
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()

def plot_multi_channel(timestamps, channels_data, output_file):
    fig, axes = plt.subplots(len(channels_data), 1, figsize=(12, 8), sharex=True)
    
    for ax, (name, values) in zip(axes, channels_data.items()):
        ax.plot(timestamps, values, linewidth=0.8)
        ax.set_ylabel(name)
        ax.grid(True, alpha=0.3)
    
    axes[-1].set_xlabel('Time (s)')
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()
```

### FFT 频谱分析

```python
import numpy as np
from scipy import signal

def analyze_spectrum(data, sample_rate):
    n = len(data)
    
    # FFT计算
    fft_result = np.fft.fft(data)
    freqs = np.fft.fftfreq(n, 1.0 / sample_rate)
    
    # 取正频率部分
    positive_mask = freqs >= 0
    freqs = freqs[positive_mask]
    magnitudes = np.abs(fft_result[positive_mask]) * 2 / n
    
    # 找主频率
    peak_idx = np.argmax(magnitudes[1:]) + 1  # 跳过DC分量
    peak_freq = freqs[peak_idx]
    
    return {
        'frequencies': freqs.tolist(),
        'magnitudes': magnitudes.tolist(),
        'peak_frequency': peak_freq,
        'peak_magnitude': magnitudes[peak_idx]
    }

def plot_spectrum(freqs, magnitudes, output_file, max_freq=None):
    plt.figure(figsize=(12, 6))
    plt.plot(freqs, magnitudes, linewidth=0.8)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('Frequency Spectrum')
    plt.grid(True, alpha=0.3)
    
    if max_freq:
        plt.xlim(0, max_freq)
    else:
        plt.xlim(0, max(freqs) / 2)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()
```

### 统计分析

```python
import numpy as np

def calculate_statistics(data):
    arr = np.array(data)
    
    return {
        'count': len(arr),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'mean': float(np.mean(arr)),
        'std': float(np.std(arr)),
        'variance': float(np.var(arr)),
        'median': float(np.median(arr)),
        'rms': float(np.sqrt(np.mean(arr ** 2))),
        'peak_to_peak': float(np.max(arr) - np.min(arr)),
        'percentile_25': float(np.percentile(arr, 25)),
        'percentile_75': float(np.percentile(arr, 75)),
    }
```

---

## 故障排除

### 常见问题与解决方案

#### 1. RTT 连接失败

**症状：** RTT Viewer 无法连接或找不到控制块

**解决方案：**
```c
// 确保RTT已初始化
SEGGER_RTT_Init();

// 检查缓冲区配置
#define BUFFER_SIZE_UP (1024)  // 增大缓冲区

// 确认链接器配置，RTT控制块需要在可访问的内存区域
```

#### 2. 数据丢失

**症状：** 采集数据不完整或有间隙

**解决方案：**
- 增大RTT上行缓冲区大小
- 降低采样率
- 使用DMA传输数据
- 检查目标CPU负载

#### 3. 采样率不稳定

**症状：** 实际采样率与设定不符

**解决方案：**
```python
# 使用精确的定时控制
import time

class PreciseTimer:
    def __init__(self, rate_hz):
        self.period = 1.0 / rate_hz
        self.next_time = time.perf_counter()
    
    def wait(self):
        self.next_time += self.period
        sleep_time = self.next_time - time.perf_counter()
        if sleep_time > 0:
            time.sleep(sleep_time)
```

#### 4. 内存读取错误

**症状：** GDB读取内存返回错误值

**解决方案：**
- 确认目标已停止或处于调试模式
- 检查内存地址是否有效
- 确认MPU配置允许访问
- 检查时钟配置

#### 5. 连接超时

**症状：** 无法连接到目标设备

**解决方案：**
```bash
# 检查连接
JLinkExe -device STM32F427II -if SWD -speed 1000

# 降低速度重试
JLinkExe -device STM32F427II -if SWD -speed 100

# 复位目标
# 在JLink命令中添加:
connect
rsettype 0  # 硬件复位
```

### 调试检查清单

- [ ] 目标板供电正常
- [ ] 调试接口连接正确 (SWDIO, SWCLK, GND)
- [ ] 目标芯片型号匹配
- [ ] 调试探针驱动已安装
- [ ] RTT代码已正确集成
- [ ] 内存地址在有效范围内
- [ ] 采样率在接口能力范围内
- [ ] 目标程序正在运行

---

## 参考链接

- [SEGGER RTT 文档](https://www.segger.com/products/debug-probes/j-link/technology/about-real-time-transfer/)
- [STM32F427 参考手册](https://www.st.com/resource/en/reference_manual/dm00031020.pdf)
- [ARM Debug Interface](https://developer.arm.com/documentation/ihi0031/latest/)
