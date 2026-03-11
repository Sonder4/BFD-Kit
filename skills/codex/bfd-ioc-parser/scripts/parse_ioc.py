#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STM32CubeMX IOC Configuration Parser
解析STM32CubeMX配置文件(.ioc)，提取硬件配置信息并生成JSON文件

功能:
1. 扫描指定目录查找.ioc文件
2. 解析.ioc文件键值对格式
3. 生成简略级别JSON (外设清单)
4. 生成详细级别JSON (按功能模块拆分)
5. 版本管理 (保留最近N个版本)
6. 链接器脚本分析 (动态提取内存配置)

作者: RSCF_A Project
日期: 2026-02-12
"""

import os
import re
import json
import shutil
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

try:
    from .analyze_startup import StartupAnalyzer
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from analyze_startup import StartupAnalyzer


class IOCParser:
    """STM32CubeMX IOC配置文件解析器"""

    def __init__(self, ioc_path: str, output_dir: str = None, history_dir: str = None, max_versions: int = 5):
        self.ioc_path = Path(ioc_path)
        # 如果没有指定输出目录，则在ioc文件所在目录下创建docs/ioc_json
        if output_dir is None:
            self.output_dir = self.ioc_path.parent / 'docs' / 'ioc_json'
        else:
            self.output_dir = Path(output_dir)

        # 如果没有指定历史目录，则在输出目录下创建history
        if history_dir is None:
            self.history_dir = self.output_dir / 'history'
        else:
            self.history_dir = Path(history_dir)

        self.max_versions = max_versions
        self.config: Dict[str, str] = {}
        self.parsed_data: Dict[str, Any] = {}
        self.current_backup_dir: Optional[Path] = None

    def parse(self) -> bool:
        """解析IOC文件"""
        if not self.ioc_path.exists():
            print(f"错误: IOC文件不存在 - {self.ioc_path}")
            return False

        try:
            with open(self.ioc_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(self.ioc_path, 'r', encoding='latin-1') as f:
                content = f.read()

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                self.config[key.strip()] = value.strip()

        self._categorize_config()
        return True

    def _categorize_config(self):
        """将配置按类别分组"""
        categories = {
            'mcu': {},
            'project': {},
            'rcc': {},
            'gpio': {},
            'usart': {},
            'can': {},
            'spi': {},
            'i2c': {},
            'tim': {},
            'dma': {},
            'nvic': {},
            'rtos': {},
            'usb': {},
            'rtc': {},
            'adc': {},
            'other': {}
        }

        mcu_keys = ['Mcu.', 'File.Version', 'MxCube.', 'MxDb.', 'PinOutPanel.', 'board']
        project_keys = ['ProjectManager.', 'CAD.']

        for key, value in self.config.items():
            categorized = False

            if any(key.startswith(k) for k in mcu_keys):
                categories['mcu'][key] = value
                categorized = True
            elif any(key.startswith(k) for k in project_keys):
                categories['project'][key] = value
                categorized = True
            elif key.startswith('RCC.'):
                categories['rcc'][key] = value
                categorized = True
            elif key.startswith('GPIO.') or '.GPIO' in key or '.Signal=GPIO' in key or '.Locked=' in key:
                categories['gpio'][key] = value
                categorized = True
            elif key.startswith('USART') or key.startswith('UART'):
                categories['usart'][key] = value
                categorized = True
            elif key.startswith('CAN') or key.startswith('FDCAN'):
                categories['can'][key] = value
                categorized = True
            elif key.startswith('SPI'):
                categories['spi'][key] = value
                categorized = True
            elif key.startswith('I2C'):
                categories['i2c'][key] = value
                categorized = True
            elif key.startswith('TIM') or key.startswith('SH.S_TIM'):
                categories['tim'][key] = value
                categorized = True
            elif key.startswith('Dma.'):
                categories['dma'][key] = value
                categorized = True
            elif key.startswith('NVIC.'):
                categories['nvic'][key] = value
                categorized = True
            elif key.startswith('FREERTOS.') or key.startswith('VP_FREERTOS'):
                categories['rtos'][key] = value
                categorized = True
            elif key.startswith('USB') or key.startswith('VP_USB'):
                categories['usb'][key] = value
                categorized = True
            elif key.startswith('RTC.') or key.startswith('VP_RTC'):
                categories['rtc'][key] = value
                categorized = True
            elif key.startswith('ADC'):
                categories['adc'][key] = value
                categorized = True

            if not categorized:
                categories['other'][key] = value

        self.parsed_data = categories

    def generate_summary_json(self) -> Dict[str, Any]:
        """生成简略级别JSON - 外设清单"""
        summary = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'ioc_file': str(self.ioc_path.name),
                'parser_version': '1.2.0'
            },
            'project_info': self._extract_project_info(),
            'mcu_info': self._extract_mcu_info(),
            'peripherals': self._extract_peripheral_list(),
            'pin_count': self._count_pins()
        }
        return summary

    def _extract_project_info(self) -> Dict[str, Any]:
        """提取工程基本信息"""
        return {
            'project_name': self.config.get('ProjectManager.ProjectName', 'Unknown'),
            'toolchain': self.config.get('ProjectManager.TargetToolchain', 'Unknown'),
            'firmware_package': self.config.get('ProjectManager.FirmwarePackage', 'Unknown'),
            'cube_mx_version': self.config.get('MxCube.Version', 'Unknown'),
            'heap_size': self.config.get('ProjectManager.HeapSize', '0'),
            'stack_size': self.config.get('ProjectManager.StackSize', '0')
        }

    def _extract_mcu_info(self) -> Dict[str, Any]:
        """提取MCU信息"""
        return {
            'name': self.config.get('Mcu.Name', 'Unknown'),
            'user_name': self.config.get('Mcu.UserName', 'Unknown'),
            'family': self.config.get('Mcu.Family', 'Unknown'),
            'package': self.config.get('Mcu.Package', 'Unknown'),
            'cpn': self.config.get('Mcu.CPN', 'Unknown'),
            'ip_count': self.config.get('Mcu.IPNb', '0'),
            'pin_count': self.config.get('Mcu.PinsNb', '0')
        }

    def _extract_peripheral_list(self) -> Dict[str, List[str]]:
        """提取外设清单"""
        peripherals = {
            'usart': [],
            'can': [],
            'spi': [],
            'i2c': [],
            'tim': [],
            'adc': [],
            'dac': [],
            'usb': [],
            'other': []
        }

        for key, value in self.config.items():
            if key.startswith('Mcu.IP') and key[6:].isdigit():
                ip_name = value
                if ip_name.startswith('USART') or ip_name.startswith('UART'):
                    peripherals['usart'].append(ip_name)
                elif ip_name.startswith('FDCAN') or ip_name.startswith('CAN'):
                    peripherals['can'].append(ip_name)
                elif ip_name.startswith('SPI'):
                    peripherals['spi'].append(ip_name)
                elif ip_name.startswith('I2C'):
                    peripherals['i2c'].append(ip_name)
                elif ip_name.startswith('TIM'):
                    peripherals['tim'].append(ip_name)
                elif ip_name.startswith('USB'):
                    peripherals['usb'].append(ip_name)
                elif ip_name not in ['DMA', 'NVIC', 'RCC', 'SYS', 'CRC', 'RNG', 'FREERTOS', 'RTC']:
                    peripherals['other'].append(ip_name)

        for key in peripherals:
            peripherals[key] = sorted(set(peripherals[key]))

        return peripherals

    def _count_pins(self) -> Dict[str, int]:
        """统计引脚使用情况"""
        gpio_pins = []
        for key, value in self.config.items():
            if key.endswith('.Signal') and 'GPIO' in value:
                pin_name = key.rsplit('.', 1)[0]
                gpio_pins.append(pin_name)

        return {
            'total_configured': int(self.config.get('Mcu.PinsNb', 0)),
            'gpio_output': len([p for p in gpio_pins if 'Output' in self.config.get(f'{p}.Signal', '')]),
            'gpio_input': len([p for p in gpio_pins if 'Input' in self.config.get(f'{p}.Signal', '')])
        }

    def generate_detailed_json(self) -> Dict[str, Dict[str, Any]]:
        """生成详细级别JSON - 按功能模块拆分"""
        detailed = {}

        detailed['clock_config'] = self._generate_clock_config()
        detailed['usart_config'] = self._generate_usart_config()
        detailed['can_config'] = self._generate_can_config()
        detailed['spi_config'] = self._generate_spi_config()
        detailed['tim_config'] = self._generate_tim_config()
        detailed['dma_config'] = self._generate_dma_config()
        detailed['gpio_config'] = self._generate_gpio_config()
        detailed['nvic_config'] = self._generate_nvic_config()
        detailed['rtos_config'] = self._generate_rtos_config()
        detailed['usb_config'] = self._generate_usb_config()
        detailed['i2c_config'] = self._generate_i2c_config()
        detailed['rtc_config'] = self._generate_rtc_config()
        detailed['adc_config'] = self._generate_adc_config()
        detailed['memory_config'] = self._generate_memory_config()
        detailed['freertos_detailed'] = self._generate_freertos_detailed_config()

        return detailed

    def _generate_clock_config(self) -> Dict[str, Any]:
        """生成时钟配置JSON"""
        clock_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'STM32H7 RCC时钟树完整配置'
            },
            'system_clock': {},
            'oscillator': {},
            'pll': {},
            'bus_clocks': {},
            'peripheral_clocks': {}
        }

        rcc_data = self.parsed_data['rcc']

        osc_keys = {
            'HSE_VALUE': 'hse_freq_hz',
            'HSI_VALUE': 'hsi_freq_hz',
            'LSE_VALUE': 'lse_freq_hz',
            'LSI_VALUE': 'lsi_freq_hz',
            'SYSCLKSource': 'sysclk_source'
        }
        for key, attr in osc_keys.items():
            if f'RCC.{key}' in rcc_data:
                value = rcc_data[f'RCC.{key}']
                try:
                    clock_config['oscillator'][attr] = int(value)
                except ValueError:
                    clock_config['oscillator'][attr] = value

        sysclk_freq = 0
        if 'RCC.SYSCLKFreq_VALUE' in rcc_data:
            try:
                sysclk_freq = int(rcc_data['RCC.SYSCLKFreq_VALUE'])
            except ValueError:
                pass

        clock_config['system_clock'] = {
            'source': clock_config['oscillator'].get('sysclk_source', 'Unknown'),
            'frequency_hz': sysclk_freq,
            'frequency_mhz': sysclk_freq / 1_000_000 if sysclk_freq else 0
        }

        pll_source = rcc_data.get('RCC.PLLSourceVirtual', 'Unknown')
        clock_config['pll']['source'] = pll_source

        vco_input_keys = {
            'VCOInput1Freq_Value': 'pll1_vco_input_hz',
            'VCOInput2Freq_Value': 'pll2_vco_input_hz',
            'VCOInput3Freq_Value': 'pll3_vco_input_hz'
        }
        for key, attr in vco_input_keys.items():
            if f'RCC.{key}' in rcc_data:
                try:
                    clock_config['pll'][attr] = int(rcc_data[f'RCC.{key}'])
                except ValueError:
                    pass

        vco_output_keys = {
            'VCO1OutputFreq_Value': 'pll1_vco_output_hz',
            'VCO2OutputFreq_Value': 'pll2_vco_output_hz',
            'VCO3OutputFreq_Value': 'pll3_vco_output_hz'
        }
        for key, attr in vco_output_keys.items():
            if f'RCC.{key}' in rcc_data:
                try:
                    clock_config['pll'][attr] = int(rcc_data[f'RCC.{key}'])
                except ValueError:
                    pass

        pll_mnp_keys = {
            'DIVM1': ('pll1', 'm'),
            'DIVN1': ('pll1', 'n'),
            'DIVP1': ('pll1', 'p'),
            'DIVQ1': ('pll1', 'q'),
            'DIVR1': ('pll1', 'r'),
            'DIVM2': ('pll2', 'm'),
            'DIVN2': ('pll2', 'n'),
            'DIVP2': ('pll2', 'p'),
            'DIVQ2': ('pll2', 'q'),
            'DIVR2': ('pll2', 'r')
        }
        for key, (pll_name, param) in pll_mnp_keys.items():
            if f'RCC.{key}' in rcc_data:
                if pll_name not in clock_config['pll']:
                    clock_config['pll'][pll_name] = {}
                try:
                    clock_config['pll'][pll_name][param] = int(rcc_data[f'RCC.{key}'])
                except ValueError:
                    clock_config['pll'][pll_name][param] = rcc_data[f'RCC.{key}']

        pll_freq_keys = {
            'DIVP1Freq_Value': ('pll1', 'p_freq_hz'),
            'DIVQ1Freq_Value': ('pll1', 'q_freq_hz'),
            'DIVR1Freq_Value': ('pll1', 'r_freq_hz'),
            'DIVP2Freq_Value': ('pll2', 'p_freq_hz'),
            'DIVQ2Freq_Value': ('pll2', 'q_freq_hz'),
            'DIVR2Freq_Value': ('pll2', 'r_freq_hz'),
            'DIVP3Freq_Value': ('pll3', 'p_freq_hz'),
            'DIVQ3Freq_Value': ('pll3', 'q_freq_hz'),
            'DIVR3Freq_Value': ('pll3', 'r_freq_hz')
        }
        for key, (pll_name, attr) in pll_freq_keys.items():
            if f'RCC.{key}' in rcc_data:
                if pll_name not in clock_config['pll']:
                    clock_config['pll'][pll_name] = {}
                try:
                    clock_config['pll'][pll_name][attr] = int(rcc_data[f'RCC.{key}'])
                except ValueError:
                    pass

        bus_prescaler_keys = {
            'HPRE': 'hpre_prescaler',
            'D1PPRE': 'd1ppre_prescaler',
            'D2PPRE1': 'd2ppre1_prescaler',
            'D2PPRE2': 'd2ppre2_prescaler',
            'D3PPRE': 'd3ppre_prescaler'
        }
        for key, attr in bus_prescaler_keys.items():
            if f'RCC.{key}' in rcc_data:
                clock_config['bus_clocks'][attr] = rcc_data[f'RCC.{key}']

        bus_freq_keys = {
            'HCLKFreq_Value': 'hclk_hz',
            'AXIClockFreq_Value': 'axi_hz',
            'CortexFreq_Value': 'cortex_hz',
            'CpuClockFreq_Value': 'cpu_hz',
            'D1CPREFreq_Value': 'd1cpre_hz',
            'AHB4Freq_Value': 'ahb4_hz',
            'AHB12Freq_Value': 'ahb12_hz',
            'APB1Freq_Value': 'apb1_hz',
            'APB2Freq_Value': 'apb2_hz',
            'APB3Freq_Value': 'apb3_hz',
            'APB4Freq_Value': 'apb4_hz',
            'APB1TimFreq_Value': 'apb1_timer_hz',
            'APB2TimFreq_Value': 'apb2_timer_hz'
        }
        for key, attr in bus_freq_keys.items():
            if f'RCC.{key}' in rcc_data:
                try:
                    clock_config['bus_clocks'][attr] = int(rcc_data[f'RCC.{key}'])
                except ValueError:
                    pass

        peripheral_freq_keys = {
            'ADCFreq_Value': 'adc_hz',
            'FDCANFreq_Value': 'fdcan_hz',
            'I2C123Freq_Value': 'i2c123_hz',
            'I2C4Freq_Value': 'i2c4_hz',
            'LPTIM1Freq_Value': 'lptim1_hz',
            'LPTIM2Freq_Value': 'lptim2_hz',
            'LPTIM345Freq_Value': 'lptim345_hz',
            'LPUART1Freq_Value': 'lpuart1_hz',
            'LTDCFreq_Value': 'ltdc_hz',
            'RNGFreq_Value': 'rng_hz',
            'RTCFreq_Value': 'rtc_hz',
            'SAI1Freq_Value': 'sai1_hz',
            'SAI4AFreq_Value': 'sai4a_hz',
            'SAI4BFreq_Value': 'sai4b_hz',
            'SDMMCFreq_Value': 'sdmmc_hz',
            'SPI123Freq_Value': 'spi123_hz',
            'SPI45Freq_Value': 'spi45_hz',
            'SPI6Freq_Value': 'spi6_hz',
            'SWPMI1Freq_Value': 'swpmi1_hz',
            'USART16Freq_Value': 'usart16_hz',
            'USART234578Freq_Value': 'usart234578_hz',
            'USBFreq_Value': 'usb_hz',
            'QSPIFreq_Value': 'qspi_hz',
            'FMCFreq_Value': 'fmc_hz',
            'CKPERFreq_Value': 'ckper_hz',
            'CECFreq_Value': 'cec_hz',
            'MCO1PinFreq_Value': 'mco1_hz',
            'MCO2PinFreq_Value': 'mco2_hz',
            'TraceFreq_Value': 'trace_hz',
            'Tim1OutputFreq_Value': 'tim1_output_hz',
            'Tim2OutputFreq_Value': 'tim2_output_hz',
            'DFSDMACLkFreq_Value': 'dfsdma_hz',
            'DFSDMFreq_Value': 'dfsdm_hz',
            'SPDIFRXFreq_Value': 'spdifrx_hz'
        }
        for key, attr in peripheral_freq_keys.items():
            if f'RCC.{key}' in rcc_data:
                try:
                    clock_config['peripheral_clocks'][attr] = int(rcc_data[f'RCC.{key}'])
                except ValueError:
                    pass

        clock_config['bus_clocks']['hclk_mhz'] = clock_config['bus_clocks'].get('hclk_hz', 0) / 1_000_000
        clock_config['bus_clocks']['apb1_mhz'] = clock_config['bus_clocks'].get('apb1_hz', 0) / 1_000_000
        clock_config['bus_clocks']['apb2_mhz'] = clock_config['bus_clocks'].get('apb2_hz', 0) / 1_000_000

        return clock_config

    def _generate_usart_config(self) -> Dict[str, Any]:
        """生成USART/UART配置JSON"""
        usart_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'USART/UART串口配置汇总'
            },
            'instances': {}
        }

        usart_instances = set()
        for key in self.config.keys():
            if key.startswith('USART') or key.startswith('UART'):
                match = re.match(r'(USART\d+|UART\d+)\.', key)
                if match:
                    usart_instances.add(match.group(1))

        for instance in sorted(usart_instances):
            instance_config = {
                'name': instance,
                'mode': 'Unknown',
                'pins': {},
                'dma': {},
                'interrupt': False,
                'parameters': {}
            }

            for key, value in self.config.items():
                if key.startswith(f'{instance}.'):
                    param = key.split('.', 1)[1]
                    if param == 'VirtualMode':
                        instance_config['mode'] = 'Asynchronous'
                    else:
                        instance_config['parameters'][param] = value

            for key, value in self.config.items():
                if key.endswith('.Signal') and instance in value:
                    pin = key.rsplit('.', 1)[0]
                    signal = value
                    instance_config['pins'][pin] = signal

            for key, value in self.config.items():
                if key.startswith('Dma.') and instance in key:
                    dma_match = re.match(rf'Dma\.{instance}_(RX|TX)\.(\d+)\.', key)
                    if dma_match:
                        direction = dma_match.group(1).lower()
                        if direction not in instance_config['dma']:
                            instance_config['dma'][direction] = {}
                        param = key.split('.', 3)[-1]
                        instance_config['dma'][direction][param] = value

            if f'NVIC.{instance}_IRQn' in self.config:
                instance_config['interrupt'] = True

            usart_config['instances'][instance] = instance_config

        return usart_config

    def _generate_can_config(self) -> Dict[str, Any]:
        """生成CAN配置JSON"""
        can_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'CAN控制器配置'
            },
            'instances': {}
        }

        can_instances = set()
        for key in self.config.keys():
            if key.startswith('CAN') or key.startswith('FDCAN'):
                match = re.match(r'(FDCAN\d+|CAN\d+)\.', key)
                if match:
                    can_instances.add(match.group(1))

        for instance in sorted(can_instances):
            instance_config = {
                'name': instance,
                'baud_rate': 0,
                'time_quantum_ns': 0,
                'bit_time_ns': 0,
                'prescaler': 0,
                'bs1': 'Unknown',
                'bs2': 'Unknown',
                'pins': {},
                'interrupts': [],
                'parameters': {}
            }

            for key, value in self.config.items():
                if key.startswith(f'{instance}.'):
                    param = key.split('.', 1)[1]
                    if param == 'CalculateBaudRate':
                        instance_config['baud_rate'] = int(value)
                    elif param == 'CalculateTimeQuantum':
                        instance_config['time_quantum_ns'] = float(value)
                    elif param == 'CalculateTimeBit':
                        instance_config['bit_time_ns'] = int(value)
                    elif param == 'Prescaler':
                        instance_config['prescaler'] = int(value)
                    elif param == 'BS1':
                        instance_config['bs1'] = value
                    elif param == 'BS2':
                        instance_config['bs2'] = value
                    else:
                        instance_config['parameters'][param] = value

            for key, value in self.config.items():
                if key.endswith('.Signal') and instance in value:
                    pin = key.rsplit('.', 1)[0]
                    instance_config['pins'][pin] = value

            for key in self.config.keys():
                if f'NVIC.{instance}_RX' in key or f'NVIC.{instance}_TX' in key:
                    irq_name = key.split('.', 1)[1]
                    if irq_name not in instance_config['interrupts']:
                        instance_config['interrupts'].append(irq_name)

            can_config['instances'][instance] = instance_config

        return can_config

    def _generate_spi_config(self) -> Dict[str, Any]:
        """生成SPI配置JSON"""
        spi_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'SPI配置'
            },
            'instances': {}
        }

        spi_instances = set()
        for key in self.config.keys():
            if key.startswith('SPI'):
                match = re.match(r'(SPI\d+)\.', key)
                if match:
                    spi_instances.add(match.group(1))

        for instance in sorted(spi_instances):
            instance_config = {
                'name': instance,
                'mode': 'Unknown',
                'direction': 'Unknown',
                'baud_rate': 'Unknown',
                'clock_polarity': 'Unknown',
                'clock_phase': 'Unknown',
                'pins': {},
                'parameters': {}
            }

            for key, value in self.config.items():
                if key.startswith(f'{instance}.'):
                    param = key.split('.', 1)[1]
                    if param == 'Mode':
                        instance_config['mode'] = value
                    elif param == 'Direction':
                        instance_config['direction'] = value
                    elif param == 'CalculateBaudRate':
                        instance_config['baud_rate'] = value
                    elif param == 'CLKPolarity':
                        instance_config['clock_polarity'] = value
                    elif param == 'CLKPhase':
                        instance_config['clock_phase'] = value
                    else:
                        instance_config['parameters'][param] = value

            for key, value in self.config.items():
                if key.endswith('.Signal') and instance in value:
                    pin = key.rsplit('.', 1)[0]
                    instance_config['pins'][pin] = value

            spi_config['instances'][instance] = instance_config

        return spi_config

    def _generate_tim_config(self) -> Dict[str, Any]:
        """生成定时器配置JSON"""
        tim_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': '定时器配置'
            },
            'instances': {}
        }

        tim_instances = set()
        for key in self.config.keys():
            if key.startswith('TIM') and '.' in key:
                match = re.match(r'(TIM\d+)\.', key)
                if match:
                    tim_instances.add(match.group(1))

        for instance in sorted(tim_instances):
            instance_config = {
                'name': instance,
                'type': 'Unknown',
                'prescaler': 0,
                'period': 0,
                'channels': {},
                'pins': {},
                'parameters': {}
            }

            for key, value in self.config.items():
                if key.startswith(f'{instance}.'):
                    param = key.split('.', 1)[1]
                    if param == 'Prescaler':
                        try:
                            instance_config['prescaler'] = int(value)
                        except ValueError:
                            instance_config['prescaler'] = value  # 保留原始值（可能是表达式）
                    elif param == 'Period':
                        try:
                            instance_config['period'] = int(value)
                        except ValueError:
                            instance_config['period'] = value  # 保留原始值（可能是表达式，如"2000-1"）
                    elif 'Channel' in param:
                        instance_config['channels'][param] = value
                    else:
                        instance_config['parameters'][param] = value

            for key, value in self.config.items():
                if key.startswith('SH.S_') and instance in value:
                    pin_signal = key.split('.', 1)[0]
                    pin_match = re.match(r'SH\.(S_TIM\d+_CH\d+)', pin_signal)
                    if pin_match:
                        for pin_key, pin_value in self.config.items():
                            if pin_key.startswith(f'{pin_signal}.'):
                                pin_num = pin_key.split('.')[-1]
                                if pin_value.startswith('TIM'):
                                    for p_key, p_val in self.config.items():
                                        if p_key.endswith('.Signal') and instance in p_val:
                                            pin = p_key.rsplit('.', 1)[0]
                                            instance_config['pins'][pin] = p_val

            tim_config['instances'][instance] = instance_config

        return tim_config

    def _generate_dma_config(self) -> Dict[str, Any]:
        """生成DMA配置JSON"""
        dma_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'DMA配置'
            },
            'requests': [],
            'streams': {}
        }

        requests_nb = int(self.config.get('Dma.RequestsNb', 0))
        for i in range(requests_nb):
            request = self.config.get(f'Dma.Request{i}', '')
            if request:
                dma_config['requests'].append(request)

        for key, value in self.config.items():
            if key.startswith('Dma.') and '.' in key:
                parts = key.split('.')
                if len(parts) >= 3:
                    stream_name = f"{parts[1]}.{parts[2]}"
                    if stream_name not in dma_config['streams']:
                        dma_config['streams'][stream_name] = {
                            'request': parts[1],
                            'stream_id': parts[2],
                            'parameters': {}
                        }

                    if len(parts) > 3:
                        param = parts[3]
                        dma_config['streams'][stream_name]['parameters'][param] = value

        return dma_config

    def _generate_gpio_config(self) -> Dict[str, Any]:
        """生成GPIO配置JSON"""
        gpio_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'GPIO引脚配置'
            },
            'pins': {},
            'groups': {
                'output': [],
                'input': [],
                'alternate': [],
                'analog': []
            }
        }

        for key, value in self.config.items():
            if key.endswith('.Signal'):
                pin = key.rsplit('.', 1)[0]
                signal = value

                pin_config = {
                    'name': pin,
                    'signal': signal,
                    'mode': 'Unknown',
                    'label': '',
                    'locked': False
                }

                label_key = f'{pin}.GPIO_Label'
                if label_key in self.config:
                    pin_config['label'] = self.config[label_key]

                locked_key = f'{pin}.Locked'
                if locked_key in self.config:
                    pin_config['locked'] = self.config[locked_key] == 'true'

                pinstate_key = f'{pin}.PinState'
                if pinstate_key in self.config:
                    pin_config['initial_state'] = self.config[pinstate_key]

                gpio_config['pins'][pin] = pin_config

                if 'Output' in signal:
                    gpio_config['groups']['output'].append(pin)
                elif 'Input' in signal:
                    gpio_config['groups']['input'].append(pin)
                elif signal.startswith('GPIO_'):
                    pass
                else:
                    gpio_config['groups']['alternate'].append(pin)

        return gpio_config

    def _generate_nvic_config(self) -> Dict[str, Any]:
        """生成NVIC中断配置JSON"""
        nvic_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'NVIC中断配置'
            },
            'priority_group': 'Unknown',
            'interrupts': {}
        }

        for key, value in self.config.items():
            if key.startswith('NVIC.'):
                param = key.split('.', 1)[1]

                if param == 'PriorityGroup':
                    nvic_config['priority_group'] = value
                elif param.endswith('_IRQn'):
                    parts = value.replace('\\:', ':').split(':')
                    if len(parts) >= 3:
                        try:
                            nvic_config['interrupts'][param] = {
                                'enabled': parts[0] == 'true',
                                'preemption_priority': int(parts[1]) if parts[1].isdigit() else 0,
                                'sub_priority': int(parts[2]) if parts[2].isdigit() else 0
                            }
                        except (ValueError, IndexError):
                            nvic_config['interrupts'][param] = {
                                'enabled': parts[0] == 'true',
                                'preemption_priority': 0,
                                'sub_priority': 0,
                                'raw_value': value
                            }

        return nvic_config

    def _generate_rtos_config(self) -> Dict[str, Any]:
        """生成FreeRTOS配置JSON"""
        rtos_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'FreeRTOS配置'
            },
            'enabled': False,
            'heap_size': 0,
            'tasks': [],
            'parameters': {}
        }

        if 'FREERTOS.configTOTAL_HEAP_SIZE' in self.config:
            rtos_config['enabled'] = True
            rtos_config['heap_size'] = int(self.config['FREERTOS.configTOTAL_HEAP_SIZE'])

        tasks_str = self.config.get('FREERTOS.Tasks01', '')
        if tasks_str:
            for task_def in tasks_str.split(','):
                if task_def.startswith('defaultTask'):
                    rtos_config['tasks'].append({
                        'name': 'defaultTask',
                        'definition': tasks_str
                    })
                    break

        for key, value in self.config.items():
            if key.startswith('FREERTOS.') and key != 'FREERTOS.Tasks01':
                param = key.split('.', 1)[1]
                rtos_config['parameters'][param] = value

        return rtos_config

    def _generate_usb_config(self) -> Dict[str, Any]:
        """生成USB配置JSON"""
        usb_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'USB配置'
            },
            'enabled': False,
            'class_type': 'Unknown',
            'device_info': {},
            'pins': {},
            'instances': {}
        }

        # 检测USB设备使能状态 - 支持多种命名模式
        usb_enabled = False
        for key in self.config.keys():
            if key.startswith('USB_DEVICE.CLASS_NAME') or key.startswith('USB_OTG'):
                usb_enabled = True
                break
            # 检查VP信号（虚拟引脚）
            if key.startswith('VP_USB') and 'Signal' in key:
                usb_enabled = True
                break

        usb_config['enabled'] = usb_enabled

        # 获取USB设备类类型
        for key, value in self.config.items():
            if 'CLASS_NAME' in key:
                usb_config['class_type'] = value
                break

        # 获取USB设备信息 - 支持多种命名模式
        usb_config['device_info'] = {
            'manufacturer': self.config.get('USB_DEVICE.MANUFACTURER_STRING-CDC_FS',
                              self.config.get('USB_DEVICE.MANUFACTURER_STRING-CDC_HS', 'Unknown')),
            'product': self.config.get('USB_DEVICE.PRODUCT_STRING_CDC_FS',
                          self.config.get('USB_DEVICE.PRODUCT_STRING_CDC_HS', 'Unknown')),
            'pid': self.config.get('USB_DEVICE.PID_CDC_FS',
                    self.config.get('USB_DEVICE.PID_CDC_HS', 'Unknown'))
        }

        # 收集所有USB相关引脚
        for key, value in self.config.items():
            if key.endswith('.Signal') and 'USB' in value:
                pin = key.rsplit('.', 1)[0]
                usb_config['pins'][pin] = value

        # 收集USB_OTG_HS配置
        usb_otg_keys = [k for k in self.config.keys() if k.startswith('USB_OTG_HS')]
        if usb_otg_keys:
            usb_config['instances']['USB_OTG_HS'] = {}
            for key in usb_otg_keys:
                param = key.split('.', 1)[1] if '.' in key else key
                usb_config['instances']['USB_OTG_HS'][param] = self.config[key]

        return usb_config

    def _generate_i2c_config(self) -> Dict[str, Any]:
        """生成I2C配置JSON"""
        i2c_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'I2C配置'
            },
            'instances': {}
        }

        i2c_instances = set()
        for key in self.config.keys():
            if key.startswith('I2C'):
                match = re.match(r'(I2C\d+)\.', key)
                if match:
                    i2c_instances.add(match.group(1))

        for instance in sorted(i2c_instances):
            instance_config = {
                'name': instance,
                'mode': 'Unknown',
                'pins': {},
                'dma': {},
                'parameters': {}
            }

            for key, value in self.config.items():
                if key.startswith(f'{instance}.'):
                    param = key.split('.', 1)[1]
                    if param == 'I2C_Mode':
                        instance_config['mode'] = value
                    else:
                        instance_config['parameters'][param] = value

            for key, value in self.config.items():
                if key.endswith('.Signal') and instance in value:
                    pin = key.rsplit('.', 1)[0]
                    instance_config['pins'][pin] = value

            i2c_config['instances'][instance] = instance_config

        return i2c_config

    def _generate_rtc_config(self) -> Dict[str, Any]:
        """生成RTC配置JSON"""
        rtc_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'RTC实时时钟配置'
            },
            'enabled': False,
            'parameters': {}
        }

        if 'VP_RTC_VS_RTC_Activate.Signal' in self.config:
            rtc_config['enabled'] = True

        for key, value in self.config.items():
            if key.startswith('RTC.'):
                param = key.split('.', 1)[1]
                rtc_config['parameters'][param] = value

        return rtc_config

    def _generate_adc_config(self) -> Dict[str, Any]:
        """生成ADC配置JSON"""
        adc_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'ADC模数转换器配置'
            },
            'instances': {}
        }

        adc_instances = set()
        for key in self.config.keys():
            if key.startswith('ADC'):
                match = re.match(r'(ADC\d+)\.', key)
                if match:
                    adc_instances.add(match.group(1))

        for instance in sorted(adc_instances):
            instance_config = {
                'name': instance,
                'enabled': True,
                'resolution': 'Unknown',
                'scan_mode': False,
                'continuous_mode': False,
                'channels': {},
                'dma': {},
                'trigger_source': 'Unknown',
                'pins': {},
                'parameters': {}
            }

            for key, value in self.config.items():
                if key.startswith(f'{instance}.'):
                    param = key.split('.', 1)[1]
                    if param == 'Resolution':
                        instance_config['resolution'] = value
                    elif param == 'ScanConvMode':
                        instance_config['scan_mode'] = value == 'ENABLE'
                    elif param == 'ContinuousConvMode':
                        instance_config['continuous_mode'] = value == 'ENABLE'
                    elif param == 'ExternalTrigConv':
                        instance_config['trigger_source'] = value
                    elif 'Channel' in param or param.startswith('Rank'):
                        instance_config['channels'][param] = value
                    else:
                        instance_config['parameters'][param] = value

            for key, value in self.config.items():
                if key.endswith('.Signal') and instance in value:
                    pin = key.rsplit('.', 1)[0]
                    instance_config['pins'][pin] = value

            for key, value in self.config.items():
                if key.startswith('Dma.') and instance in key:
                    dma_match = re.match(rf'Dma\.{instance}_(.+?)\.(\d+)\.', key)
                    if dma_match:
                        channel = dma_match.group(1)
                        if channel not in instance_config['dma']:
                            instance_config['dma'][channel] = {}
                        param = key.split('.', 3)[-1]
                        instance_config['dma'][channel][param] = value

            adc_config['instances'][instance] = instance_config

        return adc_config

    def _generate_memory_config(self) -> Dict[str, Any]:
        """生成内存配置JSON"""
        memory_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': '芯片内存分配配置'
            },
            'mcu_info': {
                'name': self.config.get('Mcu.Name', 'Unknown'),
                'family': self.config.get('Mcu.Family', 'Unknown'),
                'package': self.config.get('Mcu.Package', 'Unknown')
            },
            'flash': {
                'total_size': 'Unknown',
                'start_address': '0x08000000',
                'regions': []
            },
            'ram': {
                'total_size': 'Unknown',
                'regions': []
            },
            'heap': {
                'size': self.config.get('ProjectManager.HeapSize', '0'),
                'size_bytes': 0
            },
            'stack': {
                'size': self.config.get('ProjectManager.StackSize', '0'),
                'size_bytes': 0
            },
            'memory_map': {}
        }

        heap_size_str = memory_config['heap']['size']
        stack_size_str = memory_config['stack']['size']

        try:
            if heap_size_str.startswith('0x'):
                memory_config['heap']['size_bytes'] = int(heap_size_str, 16)
            else:
                memory_config['heap']['size_bytes'] = int(heap_size_str)
        except ValueError:
            pass

        try:
            if stack_size_str.startswith('0x'):
                memory_config['stack']['size_bytes'] = int(stack_size_str, 16)
            else:
                memory_config['stack']['size_bytes'] = int(stack_size_str)
        except ValueError:
            pass

        mcu_family = memory_config['mcu_family'] = memory_config['mcu_info']['family']

        linker_paths = []
        ioc_dir = self.ioc_path.parent

        for pattern in ['*.ld', '*.sct']:
            for f in ioc_dir.rglob(pattern):
                if 'STM32H7' in f.name or 'h7' in f.name.lower() or 'RSCF' in f.name:
                    linker_paths.append(str(f))

        if not linker_paths:
            for f in ioc_dir.glob('*.ld'):
                linker_paths.append(str(f))
            for f in ioc_dir.glob('*.sct'):
                linker_paths.append(str(f))

        if linker_paths:
            try:
                analyzer = StartupAnalyzer(linker_paths=linker_paths)
                analyzer.load_files()
                linker_result = analyzer.generate_memory_map()

                if 'chip_memory' in linker_result:
                    chip_mem = linker_result['chip_memory']

                    for name, region in chip_mem.items():
                        memory_config['memory_map'][name] = {
                            'start': region.get('start', 'Unknown'),
                            'end': region.get('end', 'Unknown'),
                            'size': region.get('size', 'Unknown'),
                            'size_bytes': region.get('size_bytes', 0)
                        }

                    total_flash = sum(r.get('size_bytes', 0) for r in chip_mem.get('flash', {}).get('regions', []))
                    if total_flash > 0:
                        memory_config['flash']['total_size'] = f"{total_flash // (1024*1024)}MB" if total_flash >= 1024*1024 else f"{total_flash // 1024}KB"
                        memory_config['flash']['regions'] = chip_mem.get('flash', {}).get('regions', [])

                    ram_regions = []
                    total_ram = 0
                    for name, region in chip_mem.items():
                        if name != 'flash' and 'regions' in region:
                            for r in region['regions']:
                                ram_regions.append({
                                    'name': r.get('name', name),
                                    'start': r.get('start', 'Unknown'),
                                    'size': r.get('size', 'Unknown'),
                                    'purpose': r.get('type', name)
                                })
                                total_ram += r.get('size_bytes', 0)

                    if ram_regions:
                        memory_config['ram']['regions'] = ram_regions
                        memory_config['ram']['total_size'] = f"{total_ram // (1024*1024)}MB" if total_ram >= 1024*1024 else f"{total_ram // 1024}KB"

            except Exception as e:
                print(f"Warning: Failed to analyze linker scripts: {e}")

        if not memory_config['memory_map']:
            if 'STM32H7' in mcu_family:
                memory_config['flash']['total_size'] = '1MB'
                memory_config['flash']['regions'] = [
                    {'name': 'Flash Bank 1', 'start': '0x08000000', 'size': '512KB'},
                    {'name': 'Flash Bank 2', 'start': '0x08100000', 'size': '512KB'}
                ]
                memory_config['ram']['total_size'] = '864KB'
                memory_config['ram']['regions'] = [
                    {'name': 'DTCM', 'start': '0x20000000', 'size': '128KB', 'purpose': 'Data TCM'},
                    {'name': 'ITCM', 'start': '0x00000000', 'size': '64KB', 'purpose': 'Instruction TCM'},
                    {'name': 'AXI SRAM', 'start': '0x24000000', 'size': '512KB', 'purpose': 'Main SRAM'},
                    {'name': 'AHB SRAM1', 'start': '0x30000000', 'size': '128KB', 'purpose': 'AHB SRAM'},
                    {'name': 'AHB SRAM2', 'start': '0x30020000', 'size': '128KB', 'purpose': 'AHB SRAM'},
                    {'name': 'AHB SRAM3', 'start': '0x30040000', 'size': '32KB', 'purpose': 'AHB SRAM'},
                    {'name': 'AHB SRAM4', 'start': '0x38000000', 'size': '64KB', 'purpose': 'Backup SRAM'}
                ]
                memory_config['memory_map'] = {
                    'flash': {'start': '0x08000000', 'end': '0x08200000', 'size': '2MB'},
                    'dtcm': {'start': '0x20000000', 'end': '0x20020000', 'size': '128KB'},
                    'itcm': {'start': '0x00000000', 'end': '0x00010000', 'size': '64KB'},
                    'axi_sram': {'start': '0x24000000', 'end': '0x24080000', 'size': '512KB'},
                    'ahb_sram': {'start': '0x30000000', 'end': '0x30048000', 'size': '288KB'}
                }
            elif 'STM32F4' in mcu_family:
                memory_config['flash']['total_size'] = '1MB'
                memory_config['flash']['regions'] = [
                    {'name': 'Flash', 'start': '0x08000000', 'size': '1MB'}
                ]
                memory_config['ram']['total_size'] = '384KB'
                memory_config['ram']['regions'] = [
                    {'name': 'SRAM1', 'start': '0x20000000', 'size': '112KB'},
                    {'name': 'SRAM2', 'start': '0x2001C000', 'size': '16KB'},
                    {'name': 'SRAM3', 'start': '0x20020000', 'size': '64KB'},
                    {'name': 'CCM RAM', 'start': '0x10000000', 'size': '64KB'}
                ]

        return memory_config

    def _generate_freertos_detailed_config(self) -> Dict[str, Any]:
        """生成FreeRTOS详细配置JSON"""
        freertos_config = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'FreeRTOS详细配置'
            },
            'enabled': False,
            'kernel': {
                'version': 'Unknown',
                'tick_rate_hz': 1000,
                'max_priorities': 56,
                'heap_size': 0,
                'total_heap_size': 0,
                'use_preemption': True,
                'use_time_slicing': True,
                'use_tickless_idle': False,
                'cpu_clock_hz': 0,
                'max_task_name_len': 16
            },
            'tasks': [],
            'queues': [],
            'timers': [],
            'mutexes': [],
            'semaphores': [],
            'config': {}
        }

        # Check if FreeRTOS is enabled by looking for Tasks01 or any FREERTOS config
        if 'FREERTOS.Tasks01' in self.config or any(k.startswith('FREERTOS.') for k in self.config.keys()):
            freertos_config['enabled'] = True
            if 'FREERTOS.configTOTAL_HEAP_SIZE' in self.config:
                try:
                    freertos_config['kernel']['total_heap_size'] = int(self.config['FREERTOS.configTOTAL_HEAP_SIZE'])
                    freertos_config['kernel']['heap_size'] = freertos_config['kernel']['total_heap_size']
                except ValueError:
                    pass

        kernel_params = {
            'configTICK_RATE_HZ': 'tick_rate_hz',
            'configMAX_PRIORITIES': 'max_priorities',
            'configUSE_PREEMPTION': 'use_preemption',
            'configUSE_TIME_SLICING': 'use_time_slicing',
            'configUSE_TICKLESS_IDLE': 'use_tickless_idle',
            'configCPU_CLOCK_HZ': 'cpu_clock_hz',
            'configMAX_TASK_NAME_LEN': 'max_task_name_len',
            'configMINIMAL_STACK_SIZE': 'minimal_stack_size',
            'configMAX_SYSCALL_INTERRUPT_PRIORITY': 'max_syscall_interrupt_priority'
        }

        for config_key, json_key in kernel_params.items():
            full_key = f'FREERTOS.{config_key}'
            if full_key in self.config:
                value = self.config[full_key]
                try:
                    if value.lower() in ['true', 'false']:
                        freertos_config['kernel'][json_key] = value.lower() == 'true'
                    else:
                        freertos_config['kernel'][json_key] = int(value)
                except ValueError:
                    freertos_config['kernel'][json_key] = value

        tasks_str = self.config.get('FREERTOS.Tasks01', '')
        if tasks_str:
            # Tasks are separated by semicolon (;)
            for task_def in tasks_str.split(';'):
                if task_def.strip():
                    task_parts = task_def.strip().split(',')
                    if len(task_parts) >= 5:
                        # Format: name,priority,stack_size,entry_function,weakness,...
                        task_info = {
                            'name': task_parts[0],
                            'priority': int(task_parts[1]) if task_parts[1].isdigit() else 0,
                            'stack_size': int(task_parts[2]) if task_parts[2].isdigit() else 128,
                            'entry_function': task_parts[3] if len(task_parts) > 3 else 'Unknown',
                            'weakness': task_parts[4] if len(task_parts) > 4 else 'Unknown',
                            'allocation_type': task_parts[6] if len(task_parts) > 6 else 'Dynamic',
                            'raw_definition': task_def
                        }
                        freertos_config['tasks'].append(task_info)

        for key, value in self.config.items():
            if key.startswith('FREERTOS.'):
                param = key.split('.', 1)[1]
                if param.startswith('config'):
                    freertos_config['config'][param] = value

        queue_keys = [k for k in self.config.keys() if 'Queue' in k and k.startswith('FREERTOS.')]
        for key in queue_keys:
            queue_name = key.split('.')[-1]
            freertos_config['queues'].append({
                'name': queue_name,
                'definition': self.config[key]
            })

        timer_keys = [k for k in self.config.keys() if 'Timer' in k and k.startswith('FREERTOS.')]
        for key in timer_keys:
            timer_name = key.split('.')[-1]
            freertos_config['timers'].append({
                'name': timer_name,
                'definition': self.config[key]
            })

        return freertos_config

    def save_json(self, data: Dict[str, Any], filename: str, use_history: bool = True) -> str:
        """保存JSON文件"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if use_history:
            if self.current_backup_dir is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                self.current_backup_dir = self.history_dir / timestamp

            self.current_backup_dir.mkdir(parents=True, exist_ok=True)

            base_name = filename.replace('.json', '')
            backup_filename = f"{base_name}_backup.json"
            backup_path = self.current_backup_dir / backup_filename

            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        current_path = self.output_dir / filename
        with open(current_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return str(current_path)

    def _cleanup_old_versions(self):
        """清理旧版本目录，保留最近N个版本"""
        if not self.history_dir.exists():
            return

        version_dirs = sorted(
            [d for d in self.history_dir.iterdir() if d.is_dir()],
            key=lambda x: x.name,
            reverse=True
        )

        for old_dir in version_dirs[self.max_versions:]:
            shutil.rmtree(old_dir)

    def generate_all(self) -> Dict[str, str]:
        """生成所有JSON文件"""
        result = {}

        summary = self.generate_summary_json()
        result['summary'] = self.save_json(summary, 'summary.json')
        print(f"生成简略级别JSON: {result['summary']}")

        detailed = self.generate_detailed_json()
        for name, data in detailed.items():
            filename = f"{name}.json"
            result[name] = self.save_json(data, filename)
            print(f"生成详细级别JSON: {result[name]}")

        self._cleanup_old_versions()

        return result


def find_ioc_files(directory: str, recursive: bool = False) -> List[Path]:
    """
    扫描目录查找.ioc文件

    Args:
        directory: 要扫描的目录路径
        recursive: 是否递归扫描子目录

    Returns:
        找到的.ioc文件路径列表
    """
    search_path = Path(directory)
    if not search_path.exists():
        print(f"错误: 目录不存在 - {directory}")
        return []

    ioc_files = []

    if recursive:
        # 递归查找
        for ioc_file in search_path.rglob('*.ioc'):
            ioc_files.append(ioc_file)
    else:
        # 仅查找当前目录
        for ioc_file in search_path.glob('*.ioc'):
            ioc_files.append(ioc_file)

    return sorted(ioc_files)


def process_ioc_file(ioc_path: Path, output_dir: str = None, history_dir: str = None,
                     max_versions: int = 5, no_history: bool = False) -> bool:
    """
    处理单个IOC文件

    Args:
        ioc_path: IOC文件路径
        output_dir: 输出目录（可选，默认在ioc文件所在目录创建docs/ioc_json）
        history_dir: 历史目录（可选）
        max_versions: 保留的最大版本数
        no_history: 是否不保存历史版本

    Returns:
        处理是否成功
    """
    print(f"\n{'='*60}")
    print(f"处理IOC文件: {ioc_path}")
    print(f"{'='*60}")

    # 如果没有指定输出目录，使用ioc文件所在目录
    if output_dir is None:
        output_dir = ioc_path.parent / 'docs' / 'ioc_json'
    else:
        output_dir = Path(output_dir)

    # 如果没有指定历史目录，使用输出目录下的history
    if history_dir is None:
        history_dir = output_dir / 'history'
    else:
        history_dir = Path(history_dir)

    ioc_parser = IOCParser(
        ioc_path=str(ioc_path),
        output_dir=str(output_dir),
        history_dir=str(history_dir),
        max_versions=max_versions
    )

    if not ioc_parser.parse():
        print(f"解析失败: {ioc_path}")
        return False

    print(f"MCU: {ioc_parser.config.get('Mcu.UserName', 'Unknown')}")
    print(f"项目: {ioc_parser.config.get('ProjectManager.ProjectName', 'Unknown')}")
    print()

    results = ioc_parser.generate_all()

    print()
    print("生成的文件:")
    for name, path in results.items():
        print(f"  - {name}: {path}")

    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='STM32CubeMX IOC配置解析器 - 支持扫描目录和任意名称的ioc文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 扫描当前目录查找ioc文件
  python parse_ioc.py --scan .

  # 扫描指定目录（递归）
  python parse_ioc.py --scan f:\\RC2026_STM\\h7 --recursive

  # 处理单个ioc文件
  python parse_ioc.py --ioc f:\\RC2026_STM\\h7\\RC2026_h7\\RSCF_H7.ioc

  # 指定输出目录
  python parse_ioc.py --ioc RSCF_H7.ioc --output ./my_output

  # 不保存历史版本
  python parse_ioc.py --scan . --no-history
        """
    )

    # 输入参数组
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--ioc', '-i',
                            help='指定单个IOC文件路径')
    input_group.add_argument('--scan', '-s',
                            help='扫描指定目录查找.ioc文件')

    # 其他参数
    parser.add_argument('--recursive', '-r',
                        action='store_true',
                        help='递归扫描子目录（与--scan一起使用）')
    parser.add_argument('--output', '-o',
                        help='输出目录（默认在ioc文件所在目录创建docs/ioc_json）')
    parser.add_argument('--history',
                        help='历史版本目录（默认在输出目录下创建history）')
    parser.add_argument('--max-versions', '-m',
                        type=int, default=5,
                        help='保留的最大版本数（默认5）')
    parser.add_argument('--no-history',
                        action='store_true',
                        help='不保存历史版本')

    args = parser.parse_args()

    success_count = 0
    fail_count = 0

    if args.ioc:
        # 处理单个IOC文件
        ioc_path = Path(args.ioc)
        if not ioc_path.exists():
            print(f"错误: IOC文件不存在 - {args.ioc}")
            return 1

        if process_ioc_file(
            ioc_path=ioc_path,
            output_dir=args.output,
            history_dir=args.history,
            max_versions=args.max_versions,
            no_history=args.no_history
        ):
            success_count += 1
        else:
            fail_count += 1

    elif args.scan:
        # 扫描目录
        ioc_files = find_ioc_files(args.scan, recursive=args.recursive)

        if not ioc_files:
            print(f"在目录 '{args.scan}' 中未找到.ioc文件")
            return 1

        print(f"找到 {len(ioc_files)} 个.ioc文件:")
        for i, ioc_file in enumerate(ioc_files, 1):
            print(f"  {i}. {ioc_file}")
        print()

        # 处理每个找到的ioc文件
        for ioc_file in ioc_files:
            if process_ioc_file(
                ioc_path=ioc_file,
                output_dir=args.output,
                history_dir=args.history,
                max_versions=args.max_versions,
                no_history=args.no_history
            ):
                success_count += 1
            else:
                fail_count += 1

    print(f"\n{'='*60}")
    print(f"处理完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    print(f"{'='*60}")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    exit(main())
