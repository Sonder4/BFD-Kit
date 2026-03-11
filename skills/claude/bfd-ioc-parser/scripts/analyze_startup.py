#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STM32H7 启动文件和链接器脚本分析器
分析 startup_stm32h723xx.s 和链接器脚本(.sct/.ld)，提取内存配置信息

功能:
1. 分析启动文件 - 获取向量表、堆栈配置
2. 分析链接器脚本 - 获取Flash/RAM区域分配
   - 支持 Keil (.sct) 格式
   - 支持 GCC (.ld) 格式
3. 生成完整的内存映射JSON

作者: RSCF_A Project
日期: 2026-02-19
"""

import os
import re
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class StartupAnalyzer:
    """STM32启动文件和链接器脚本分析器"""

    def __init__(self, startup_path: str = None, linker_paths: List[str] = None):
        self.startup_path = Path(startup_path) if startup_path else None
        self.linker_paths = [Path(p) for p in linker_paths] if linker_paths else []
        self.startup_content = ""
        self.linker_contents: Dict[str, str] = {}
        self.analysis_result: Dict[str, Any] = {}

    def load_files(self):
        """加载需要分析的文件"""
        if self.startup_path and self.startup_path.exists():
            with open(self.startup_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.startup_content = f.read()

        for linker_path in self.linker_paths:
            if linker_path.exists():
                with open(linker_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.linker_contents[linker_path.name] = f.read()

    def analyze_startup(self) -> Dict[str, Any]:
        """分析启动文件"""
        result = {
            'file': str(self.startup_path.name) if self.startup_path else None,
            'mcu_series': None,
            'vector_table': {},
            'stack': {},
            'heap': {},
            'symbols': {}
        }

        match = re.search(r'startup_stm32h(\w+)\.s', self.startup_content)
        if match:
            result['mcu_series'] = f"STM32H{match.group(1).upper()}"

        for line in self.startup_content.split('\n'):
            line = line.strip()

            stack_match = re.search(r'Stack_Size\s+EQU\s+(0x[0-9A-Fa-f]+|0x[0-9A-Fa-f]+)', line, re.IGNORECASE)
            if not stack_match:
                stack_match = re.search(r'Stack_Size\s+EQU\s+(\d+)', line)
            if stack_match:
                size_str = stack_match.group(1)
                if size_str.startswith('0x'):
                    result['stack']['size_hex'] = size_str
                    result['stack']['size_bytes'] = int(size_str, 16)
                else:
                    result['stack']['size_dec'] = size_str
                    result['stack']['size_bytes'] = int(size_str)

            heap_match = re.search(r'Heap_Size\s+EQU\s+(0x[0-9A-Fa-f]+)', line, re.IGNORECASE)
            if not heap_match:
                heap_match = re.search(r'Heap_Size\s+EQU\s+(\d+)', line)
            if heap_match:
                size_str = heap_match.group(1)
                if size_str.startswith('0x'):
                    result['heap']['size_hex'] = size_str
                    result['heap']['size_bytes'] = int(size_str, 16)
                else:
                    result['heap']['size_dec'] = size_str
                    result['heap']['size_bytes'] = int(size_str)

            estack_match = re.search(r'_estack\s*=\s*(0x[0-9A-Fa-f]+)', line)
            if estack_match:
                result['stack']['start_hex'] = estack_match.group(1)
                result['stack']['start_address'] = int(estack_match.group(1), 16)

            symbol_match = re.search(r'(\w+)\s+.*\b_sidata\b', line)
            if symbol_match:
                result['symbols']['_sidata'] = True

            if 'g_pfnVectors' in line and '.word' in line:
                result['vector_table']['label'] = 'g_pfnVectors'
                result['vector_table']['location'] = '.isr_vector section'

        return result

    def analyze_sct(self, sct_name: str) -> Dict[str, Any]:
        """分析链接器脚本"""
        content = self.linker_contents.get(sct_name, "")
        result = {
            'file': sct_name,
            'flash_regions': [],
            'ram_regions': [],
            'heap_config': {},
            'stack_config': {}
        }

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith(';'):
                continue

            lr_match = re.search(r'(LR_\w+)\s+(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)', line)
            if lr_match:
                region_type = 'flash' if 'IROM' in lr_match.group(1) else 'ram'
                if region_type == 'flash':
                    result['flash_regions'].append({
                        'name': lr_match.group(1),
                        'start': lr_match.group(2),
                        'size': lr_match.group(3),
                        'size_bytes': int(lr_match.group(3), 16)
                    })

            erom_match = re.search(r'(ER_\w+)\s+(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)', line)
            if erom_match:
                existing = [r for r in result['flash_regions'] if r['name'] == erom_match.group(1)]
                if not existing:
                    result['flash_regions'].append({
                        'name': erom_match.group(1),
                        'start': erom_match.group(2),
                        'size': erom_match.group(3),
                        'size_bytes': int(erom_match.group(3), 16)
                    })

            iram_match = re.search(r'(RW_\w+)\s+(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)', line)
            if iram_match and 'ARM_LIB' not in line:
                ram_addr = int(iram_match.group(2), 16)
                ram_size = int(iram_match.group(3), 16)
                ram_name = iram_match.group(1)

                if ram_addr >= 0x24000000 and ram_addr < 0x30000000:
                    ram_type = 'AXI SRAM'
                elif ram_addr >= 0x30000000:
                    ram_type = 'AHB SRAM'
                elif ram_addr >= 0x20000000 and ram_addr < 0x24000000:
                    ram_type = 'DTCM'
                elif ram_addr >= 0x10000000 and ram_addr < 0x20000000:
                    ram_type = 'ITCM'
                else:
                    ram_type = 'Unknown'

                result['ram_regions'].append({
                    'name': ram_name,
                    'start': iram_match.group(2),
                    'size': iram_match.group(3),
                    'size_bytes': ram_size,
                    'type': ram_type,
                    'end': hex(ram_addr + ram_size)
                })

            stack_match = re.search(r'(ARM_LIB_STACK)\s+(0x[0-9A-Fa-f]+)\s+EMPTY\s+(-0x[0-9A-Fa-f]+)', line)
            if stack_match:
                result['stack_config'] = {
                    'region': stack_match.group(1),
                    'start': stack_match.group(2),
                    'size': stack_match.group(3),
                    'size_bytes': abs(int(stack_match.group(3), 16))
                }

            heap_match = re.search(r'(ARM_LIB_HEAP)\s+(0x[0-9A-Fa-f]+)\s+EMPTY\s+(-0x[0-9A-Fa-f]+)', line)
            if heap_match:
                result['heap_config'] = {
                    'region': heap_match.group(1),
                    'start': heap_match.group(2),
                    'size': heap_match.group(3),
                    'size_bytes': abs(int(heap_match.group(3), 16))
                }

        return result

    def analyze_ld(self, ld_name: str) -> Dict[str, Any]:
        """分析 GCC 链接器脚本 (.ld)"""
        content = self.linker_contents.get(ld_name, "")
        result = {
            'file': ld_name,
            'format': 'GCC',
            'flash_regions': [],
            'ram_regions': [],
            'heap_config': {},
            'stack_config': {}
        }

        in_memory_section = False
        memory_def = ""

        for line in content.split('\n'):
            stripped = line.strip()

            if 'MEMORY' in stripped.upper():
                in_memory_section = True
                continue

            if in_memory_section and '{' in stripped:
                memory_def += stripped + "\n"
                continue

            if in_memory_section and '}' in stripped:
                in_memory_section = False
                break

            if in_memory_section:
                memory_def += stripped + "\n"

        for mem_line in memory_def.split('\n'):
            mem_line = mem_line.strip()
            if not mem_line or mem_line.startswith('/*'):
                continue

            mem_match = re.match(r'(\w+)\s*\([^)]+\)\s*:\s*ORIGIN\s*=\s*(0x[0-9A-Fa-f]+)\s*,\s*LENGTH\s*=\s*(\d+)([KMG])', mem_line, re.IGNORECASE)
            if mem_match:
                region_name = mem_match.group(1)
                origin = mem_match.group(2)
                length_val = int(mem_match.group(3))
                length_unit = mem_match.group(4).upper()

                length_bytes = length_val * 1024 if length_unit == 'K' else length_val * 1024 * 1024 if length_unit == 'M' else length_val

                origin_int = int(origin, 16)

                if 'FLASH' in region_name.upper():
                    result['flash_regions'].append({
                        'name': region_name,
                        'start': origin,
                        'size': f"{length_val}{length_unit}",
                        'size_bytes': length_bytes,
                        'end': hex(origin_int + length_bytes)
                    })
                else:
                    if 'DTCM' in region_name.upper():
                        ram_type = 'DTCM'
                    elif 'AXI' in region_name.upper() or 'RAM_D1' in region_name.upper():
                        ram_type = 'AXI SRAM'
                    elif 'SRAM1' in region_name.upper() or 'SRAM2' in region_name.upper():
                        ram_type = 'AHB SRAM'
                    elif 'SRAM4' in region_name.upper() or 'D3' in region_name.upper():
                        ram_type = 'D3 SRAM'
                    elif 'BKUP' in region_name.upper() or 'BACKUP' in region_name.upper():
                        ram_type = 'Backup SRAM'
                    elif 'ITCM' in region_name.upper():
                        ram_type = 'ITCM'
                    else:
                        ram_type = region_name

                    result['ram_regions'].append({
                        'name': region_name,
                        'start': origin,
                        'size': f"{length_val}{length_unit}",
                        'size_bytes': length_bytes,
                        'type': ram_type,
                        'end': hex(origin_int + length_bytes)
                    })

        for line in content.split('\n'):
            stripped = line.strip()

            heap_match = re.search(r'_Heap\s*=\s*(0x[0-9A-Fa-f]+)', stripped, re.IGNORECASE)
            if heap_match:
                heap_start = heap_match.group(1)
                result['heap_config']['start'] = heap_start
                result['heap_config']['start_address'] = int(heap_start, 16)

            stack_match = re.search(r'_Stack\s*=\s*(0x[0-9A-Fa-f]+)', stripped, re.IGNORECASE)
            if stack_match:
                stack_start = stack_match.group(1)
                result['stack_config']['start'] = stack_start
                result['stack_config']['start_address'] = int(stack_start, 16)

        return result

    def generate_memory_map(self) -> Dict[str, Any]:
        """生成完整内存映射"""
        memory_map = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'STM32H7 内存映射完整分析（从链接器脚本动态提取）'
            },
            'chip_memory': {},
            'linker_config': {},
            'startup_config': {},
            'vector_table': {}
        }

        for linker_name, content in self.linker_contents.items():
            if linker_name.endswith('.sct'):
                analysis = self.analyze_sct(linker_name)
                analysis['format'] = 'Keil'
                memory_map['linker_config'][linker_name] = analysis
            elif linker_name.endswith('.ld'):
                analysis = self.analyze_ld(linker_name)
                memory_map['linker_config'][linker_name] = analysis

        if self.startup_content:
            startup_analysis = self.analyze_startup()
            memory_map['startup_config'] = startup_analysis

            if startup_analysis.get('vector_table'):
                memory_map['vector_table'] = startup_analysis['vector_table']

        if self.linker_contents:
            primary_linker = list(self.linker_contents.keys())[0]
            linker_data = memory_map['linker_config'].get(primary_linker, {})

            all_flash = linker_data.get('flash_regions', [])
            all_ram = linker_data.get('ram_regions', [])

            if all_flash:
                flash_start = int(all_flash[0]['start'], 16)
                max_addr = flash_start
                unique_regions = {}
                for region in all_flash:
                    region_key = region['start']
                    if region_key not in unique_regions:
                        unique_regions[region_key] = region
                    region_end = int(region['start'], 16) + region['size_bytes']
                    if region_end > max_addr:
                        max_addr = region_end
                unique_regions_list = list(unique_regions.values())
                memory_map['chip_memory']['flash'] = {
                    'start': unique_regions_list[0]['start'],
                    'end': hex(max_addr),
                    'size': self._format_size(max_addr - flash_start),
                    'size_bytes': max_addr - flash_start,
                    'description': f'Flash ({primary_linker})',
                    'regions': unique_regions_list,
                    'source_file': primary_linker
                }

            if all_ram:
                ram_by_type = {}
                for region in all_ram:
                    ram_type = region.get('type', 'Unknown')
                    if ram_type not in ram_by_type:
                        ram_by_type[ram_type] = []
                    ram_by_type[ram_type].append(region)

                for ram_type, regions in ram_by_type.items():
                    total_size = sum(r['size_bytes'] for r in regions)
                    key_name = ram_type.lower().replace(' ', '_')
                    memory_map['chip_memory'][key_name] = {
                        'start': regions[0]['start'],
                        'end': regions[-1]['end'],
                        'size': self._format_size(total_size),
                        'size_bytes': total_size,
                        'description': ram_type,
                        'regions': regions,
                        'source_file': primary_linker
                    }

        return memory_map

    def _format_size(self, size_bytes: int) -> str:
        """格式化大小为人类可读格式"""
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes // (1024 * 1024)}MB"
        elif size_bytes >= 1024:
            return f"{size_bytes // 1024}KB"
        else:
            return f"{size_bytes}B"

    def generate_all(self) -> Dict[str, Any]:
        """生成完整分析结果"""
        self.analysis_result = self.generate_memory_map()
        return self.analysis_result

    def save_json(self, output_path: str = None) -> str:
        """保存JSON文件"""
        if output_path is None:
            output_path = Path('startup_analysis.json')

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_result, f, indent=2, ensure_ascii=False)

        return str(output_path)


def find_files(directory: str) -> Dict[str, List[str]]:
    """查找启动文件和链接器脚本"""
    directory = Path(directory)
    result = {
        'startup': [],
        'linker': []
    }

    for f in directory.rglob('startup_stm32h*.s'):
        result['startup'].append(str(f))

    for f in directory.rglob('*.sct'):
        result['linker'].append(str(f))

    for f in directory.rglob('*.ld'):
        result['linker'].append(str(f))

    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='STM32H7 启动文件和链接器脚本分析器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分析指定文件 (Keil + GCC)
  python analyze_startup.py --startup startup_stm32h723xx.s --linker RC2026_h7.sct --linker STM32H723VGTx_FLASH.ld

  # 扫描目录自动查找文件
  python analyze_startup.py --scan f:\\RC2026_STM\\h7\\RC2026_h7

  # 指定输出文件
  python analyze_startup.py --scan . --output startup_analysis.json
        """
    )

    parser.add_argument('--startup', '-s', help='启动文件路径')
    parser.add_argument('--linker', '-l', action='append', help='链接器脚本路径(.sct/.ld)，可多次使用')
    parser.add_argument('--scan', help='扫描目录自动查找文件')
    parser.add_argument('--output', '-o', default='startup_analysis.json', help='输出JSON文件路径')

    args = parser.parse_args()

    if args.scan:
        files = find_files(args.scan)
        print(f"扫描目录: {args.scan}")
        print(f"找到启动文件: {len(files['startup'])}")
        print(f"找到链接器脚本: {len(files['linker'])}")

        analyzer = StartupAnalyzer(
            startup_path=files['startup'][0] if files['startup'] else None,
            linker_paths=files['linker'] if files['linker'] else []
        )
    elif args.startup or args.linker:
        analyzer = StartupAnalyzer(
            startup_path=args.startup,
            linker_paths=args.linker if args.linker else []
        )
    else:
        parser.print_help()
        return 1

    analyzer.load_files()
    analyzer.generate_all()

    output_path = analyzer.save_json(args.output)
    print(f"分析完成！")
    print(f"输出文件: {output_path}")

    print("\n=== 内存映射摘要 ===")
    if 'chip_memory' in analyzer.analysis_result:
        for name, info in analyzer.analysis_result['chip_memory'].items():
            print(f"  {name}: {info['start']} - {info['end']} ({info['size']})")

    return 0


if __name__ == '__main__':
    exit(main())
