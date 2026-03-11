#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STM32 SVD Parser
SVD文件解析器，提取外设寄存器定义信息

功能:
1. 解析SVD XML文件
2. 提取外设和寄存器信息
3. 生成寄存器定义头文件
4. 导出JSON格式寄存器信息
5. 搜索寄存器和位域

作者: RSCF_A Project
日期: 2026-02-21
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Iterator
from dataclasses import dataclass, field, asdict
from xml.etree import ElementTree as ET


@dataclass
class EnumeratedValue:
    name: str
    description: str
    value: int


@dataclass
class BitField:
    name: str
    description: str
    bit_offset: int
    bit_width: int
    access: str
    reset_value: Optional[int] = None
    enumerated_values: List[EnumeratedValue] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "bit_offset": self.bit_offset,
            "bit_width": self.bit_width,
            "access": self.access,
            "reset_value": self.reset_value,
            "enumerated_values": [
                {"name": e.name, "description": e.description, "value": e.value}
                for e in self.enumerated_values
            ]
        }
    
    def get_mask(self) -> int:
        return ((1 << self.bit_width) - 1) << self.bit_offset
    
    def get_c_define(self, reg_name: str) -> str:
        lines = []
        mask = self.get_mask()
        shift = self.bit_offset
        
        lines.append(f"#define {reg_name}_{self.name}_Pos    ({shift}U)")
        lines.append(f"#define {reg_name}_{self.name}_Msk    (0x{mask:08X}U)")
        lines.append(f"#define {reg_name}_{self.name}        {reg_name}_{self.name}_Msk")
        
        if self.enumerated_values:
            lines.append("")
            for enum in self.enumerated_values:
                val_shifted = enum.value << shift
                lines.append(f"#define {reg_name}_{self.name}_{enum.name}    (0x{val_shifted:08X}U)")
        
        return "\n".join(lines)


@dataclass
class Register:
    name: str
    display_name: str
    description: str
    address_offset: int
    size: int
    access: str
    reset_value: int
    reset_mask: int
    bit_fields: List[BitField] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "address_offset": f"0x{self.address_offset:04X}",
            "size": self.size,
            "access": self.access,
            "reset_value": f"0x{self.reset_value:08X}",
            "reset_mask": f"0x{self.reset_mask:08X}",
            "bit_fields": [bf.to_dict() for bf in self.bit_fields]
        }
    
    def get_c_define(self) -> str:
        lines = []
        lines.append(f"/* {self.name} - {self.description} */")
        lines.append(f"#define {self.name}_OFFSET    (0x{self.address_offset:04X}U)")
        
        for bf in self.bit_fields:
            lines.append("")
            lines.append(bf.get_c_define(self.name))
        
        return "\n".join(lines)


@dataclass
class Cluster:
    name: str
    description: str
    address_offset: int
    registers: List[Register] = field(default_factory=list)


@dataclass
class Peripheral:
    name: str
    display_name: str
    description: str
    base_address: int
    group_name: str
    registers: List[Register] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "base_address": f"0x{self.base_address:08X}",
            "group_name": self.group_name,
            "registers": [r.to_dict() for r in self.registers],
            "clusters": [
                {
                    "name": c.name,
                    "description": c.description,
                    "address_offset": f"0x{c.address_offset:04X}",
                    "registers": [r.to_dict() for r in c.registers]
                }
                for c in self.clusters
            ]
        }
    
    def get_all_registers(self) -> Iterator[Register]:
        for reg in self.registers:
            yield reg
        for cluster in self.clusters:
            for reg in cluster.registers:
                yield reg
    
    def get_c_header(self) -> str:
        lines = []
        lines.append(f"/*")
        lines.append(f" * {self.name} - {self.description}")
        lines.append(f" * Base Address: 0x{self.base_address:08X}")
        lines.append(f" */")
        lines.append(f"#define {self.name}_BASE    (0x{self.base_address:08X}UL)")
        lines.append("")
        
        for reg in self.registers:
            lines.append(reg.get_c_define())
            lines.append("")
        
        for cluster in self.clusters:
            lines.append(f"/* Cluster: {cluster.name} - {cluster.description} */")
            for reg in cluster.registers:
                lines.append(reg.get_c_define())
                lines.append("")
        
        return "\n".join(lines)


@dataclass
class Interrupt:
    name: str
    description: str
    value: int


@dataclass
class CPU:
    name: str
    revision: str
    endian: str
    mpu_present: bool
    fpu_present: bool
    nvic_priority_bits: int
    vendor_systick_config: bool


@dataclass
class Device:
    name: str
    description: str
    cpu: Optional[CPU] = None
    peripherals: List[Peripheral] = field(default_factory=list)
    interrupts: List[Interrupt] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "cpu": asdict(self.cpu) if self.cpu else None,
            "peripherals": [p.to_dict() for p in self.peripherals],
            "interrupts": [
                {"name": i.name, "description": i.description, "value": i.value}
                for i in self.interrupts
            ]
        }


class SVDParser:
    SVD_PATH = r"D:\STM32CubeCLT\STMicroelectronics_CMSIS_SVD"
    
    def __init__(self, svd_file: Optional[str] = None):
        self.svd_file = svd_file
        self.device: Optional[Device] = None
        self._peripheral_cache: Dict[str, Peripheral] = {}
    
    def parse(self, svd_file: Optional[str] = None) -> bool:
        if svd_file:
            self.svd_file = svd_file
        
        if not self.svd_file:
            return False
        
        try:
            tree = ET.parse(self.svd_file)
            root = tree.getroot()
            
            self.device = self._parse_device(root)
            self._build_cache()
            return True
        except Exception as e:
            print(f"Failed to parse SVD file: {e}")
            return False
    
    def _parse_device(self, root: ET.Element) -> Device:
        name = root.findtext("name", "Unknown")
        description = root.findtext("description", "")
        
        cpu = None
        cpu_elem = root.find("cpu")
        if cpu_elem is not None:
            cpu = CPU(
                name=cpu_elem.findtext("name", ""),
                revision=cpu_elem.findtext("revision", ""),
                endian=cpu_elem.findtext("endian", "little"),
                mpu_present=cpu_elem.findtext("mpuPresent", "false").lower() == "true",
                fpu_present=cpu_elem.findtext("fpuPresent", "false").lower() == "true",
                nvic_priority_bits=int(cpu_elem.findtext("nvicPrioBits", "4")),
                vendor_systick_config=cpu_elem.findtext("vendorSystickConfig", "false").lower() == "true"
            )
        
        peripherals = []
        for peri_elem in root.findall(".//peripheral"):
            peripheral = self._parse_peripheral(peri_elem)
            if peripheral:
                peripherals.append(peripheral)
        
        interrupts = []
        for peri_elem in root.findall(".//peripheral"):
            for int_elem in peri_elem.findall("interrupt"):
                interrupt = Interrupt(
                    name=int_elem.findtext("name", ""),
                    description=int_elem.findtext("description", ""),
                    value=int(int_elem.findtext("value", "0"))
                )
                interrupts.append(interrupt)
        
        return Device(
            name=name,
            description=description,
            cpu=cpu,
            peripherals=peripherals,
            interrupts=sorted(interrupts, key=lambda x: x.value)
        )
    
    def _parse_peripheral(self, elem: ET.Element) -> Optional[Peripheral]:
        name = elem.findtext("name", "")
        display_name = elem.findtext("displayName", name)
        description = elem.findtext("description", "")
        
        base_addr_str = elem.findtext("baseAddress", "0")
        base_address = int(base_addr_str, 16) if base_addr_str.startswith("0x") else int(base_addr_str)
        
        group_name = elem.findtext("groupName", "")
        
        peripheral = Peripheral(
            name=name,
            display_name=display_name,
            description=description,
            base_address=base_address,
            group_name=group_name
        )
        
        derived = elem.get("derivedFrom")
        if derived:
            peripheral.registers = self._get_derived_registers(derived)
            return peripheral
        
        registers_elem = elem.find("registers")
        if registers_elem is not None:
            for reg_elem in registers_elem.findall("register"):
                register = self._parse_register(reg_elem)
                if register:
                    peripheral.registers.append(register)
            
            for cluster_elem in registers_elem.findall("cluster"):
                cluster = self._parse_cluster(cluster_elem)
                if cluster:
                    peripheral.clusters.append(cluster)
        
        return peripheral
    
    def _parse_register(self, elem: ET.Element) -> Optional[Register]:
        name = elem.findtext("name", "")
        display_name = elem.findtext("displayName", name)
        description = elem.findtext("description", "")
        
        offset_str = elem.findtext("addressOffset", "0")
        address_offset = int(offset_str, 16) if offset_str.startswith("0x") else int(offset_str)
        
        size_str = elem.findtext("size", "32")
        size = int(size_str)
        
        access = elem.findtext("access", "read-write")
        
        reset_str = elem.findtext("resetValue", "0")
        reset_value = int(reset_str, 16) if reset_str.startswith("0x") else int(reset_str)
        
        mask_str = elem.findtext("resetMask", "0xFFFFFFFF")
        reset_mask = int(mask_str, 16) if mask_str.startswith("0x") else int(mask_str)
        
        register = Register(
            name=name,
            display_name=display_name,
            description=description,
            address_offset=address_offset,
            size=size,
            access=access,
            reset_value=reset_value,
            reset_mask=reset_mask
        )
        
        fields_elem = elem.find("fields")
        if fields_elem is not None:
            for field_elem in fields_elem.findall("field"):
                bit_field = self._parse_bit_field(field_elem)
                if bit_field:
                    register.bit_fields.append(bit_field)
        
        return register
    
    def _parse_cluster(self, elem: ET.Element) -> Optional[Cluster]:
        name = elem.findtext("name", "")
        description = elem.findtext("description", "")
        
        offset_str = elem.findtext("addressOffset", "0")
        address_offset = int(offset_str, 16) if offset_str.startswith("0x") else int(offset_str)
        
        cluster = Cluster(
            name=name,
            description=description,
            address_offset=address_offset
        )
        
        for reg_elem in elem.findall("register"):
            register = self._parse_register(reg_elem)
            if register:
                cluster.registers.append(register)
        
        return cluster
    
    def _parse_bit_field(self, elem: ET.Element) -> Optional[BitField]:
        name = elem.findtext("name", "")
        description = elem.findtext("description", "")
        
        lsb_elem = elem.find("lsb")
        msb_elem = elem.find("msb")
        bit_offset_elem = elem.find("bitOffset")
        bit_width_elem = elem.find("bitWidth")
        
        if lsb_elem is not None and msb_elem is not None:
            lsb = int(lsb_elem.text)
            msb = int(msb_elem.text)
            bit_offset = lsb
            bit_width = msb - lsb + 1
        elif bit_offset_elem is not None and bit_width_elem is not None:
            bit_offset = int(bit_offset_elem.text)
            bit_width = int(bit_width_elem.text)
        else:
            bit_offset = 0
            bit_width = 1
        
        access = elem.findtext("access", "read-write")
        
        reset_value = None
        reset_elem = elem.find("resetValue")
        if reset_elem is not None:
            reset_value = int(reset_elem.text, 16) if reset_elem.text.startswith("0x") else int(reset_elem.text)
        
        bit_field = BitField(
            name=name,
            description=description,
            bit_offset=bit_offset,
            bit_width=bit_width,
            access=access,
            reset_value=reset_value
        )
        
        for enum_elem in elem.findall(".//enumeratedValue"):
            enum_name = enum_elem.findtext("name", "")
            enum_desc = enum_elem.findtext("description", "")
            enum_val_str = enum_elem.findtext("value", "0")
            enum_val = int(enum_val_str, 16) if enum_val_str.startswith("0x") else int(enum_val_str)
            
            bit_field.enumerated_values.append(EnumeratedValue(
                name=enum_name,
                description=enum_desc,
                value=enum_val
            ))
        
        return bit_field
    
    def _get_derived_registers(self, derived_name: str) -> List[Register]:
        if derived_name in self._peripheral_cache:
            return self._peripheral_cache[derived_name].registers.copy()
        return []
    
    def _build_cache(self):
        if self.device:
            for peri in self.device.peripherals:
                self._peripheral_cache[peri.name] = peri
    
    def get_peripheral(self, name: str) -> Optional[Peripheral]:
        return self._peripheral_cache.get(name.upper())
    
    def list_peripherals(self) -> List[str]:
        if not self.device:
            return []
        return sorted([p.name for p in self.device.peripherals])
    
    def search_registers(self, pattern: str) -> List[Tuple[Peripheral, Register]]:
        results = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        if not self.device:
            return results
        
        for peri in self.device.peripherals:
            for reg in peri.get_all_registers():
                if regex.search(reg.name) or regex.search(reg.description):
                    results.append((peri, reg))
        
        return results
    
    def search_bit_fields(self, pattern: str) -> List[Tuple[Peripheral, Register, BitField]]:
        results = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        if not self.device:
            return results
        
        for peri in self.device.peripherals:
            for reg in peri.get_all_registers():
                for bf in reg.bit_fields:
                    if regex.search(bf.name) or regex.search(bf.description):
                        results.append((peri, reg, bf))
        
        return results
    
    def export_json(self, output_file: str, peripheral: Optional[str] = None):
        if not self.device:
            return
        
        if peripheral:
            peri = self.get_peripheral(peripheral)
            if peri:
                data = peri.to_dict()
            else:
                print(f"Peripheral {peripheral} not found")
                return
        else:
            data = self.device.to_dict()
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def export_c_header(self, output_file: str, peripheral: str):
        peri = self.get_peripheral(peripheral)
        if not peri:
            print(f"Peripheral {peripheral} not found")
            return
        
        lines = [
            f"/**",
            f" * @file {peripheral.lower()}_regs.h",
            f" * @brief {peri.description}",
            f" * @auto-generated from SVD",
            f" */",
            "",
            f"#ifndef __{peripheral.upper()}_REGS_H",
            f"#define __{peripheral.upper()}_REGS_H",
            "",
            "#ifdef __cplusplus",
            'extern "C" {',
            "#endif",
            "",
            peri.get_c_header(),
            "",
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            f"#endif /* __{peripheral.upper()}_REGS_H */",
            ""
        ]
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def generate_summary(self) -> str:
        if not self.device:
            return "No device loaded"
        
        lines = [
            "=" * 70,
            f"Device: {self.device.name}",
            f"Description: {self.device.description}",
            "=" * 70,
            ""
        ]
        
        if self.device.cpu:
            lines.append("CPU Information:")
            lines.append(f"  Name: {self.device.cpu.name}")
            lines.append(f"  Revision: {self.device.cpu.revision}")
            lines.append(f"  FPU: {'Yes' if self.device.cpu.fpu_present else 'No'}")
            lines.append(f"  MPU: {'Yes' if self.device.cpu.mpu_present else 'No'}")
            lines.append(f"  NVIC Priority Bits: {self.device.cpu.nvic_priority_bits}")
            lines.append("")
        
        lines.append(f"Peripherals ({len(self.device.peripherals)}):")
        for peri in sorted(self.device.peripherals, key=lambda x: x.base_address):
            reg_count = len(list(peri.get_all_registers()))
            lines.append(f"  {peri.name}: 0x{peri.base_address:08X} ({reg_count} registers)")
        
        return "\n".join(lines)


def find_svd_files(directory: str = None) -> List[Path]:
    if directory is None:
        directory = SVDParser.SVD_PATH
    
    svd_dir = Path(directory)
    if not svd_dir.exists():
        return []
    
    return sorted(svd_dir.glob("*.svd"))


def main():
    parser = argparse.ArgumentParser(
        description="STM32 SVD Parser - Parse SVD files and extract register definitions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python svd_parser.py --list-svd
  python svd_parser.py --svd STM32H743.svd --summary
  python svd_parser.py --svd STM32H743.svd --list
  python svd_parser.py --svd STM32H743.svd --peripheral GPIOA
  python svd_parser.py --svd STM32H743.svd --peripheral GPIOA --export-json gpioa.json
  python svd_parser.py --svd STM32H743.svd --peripheral GPIOA --export-header gpioa_regs.h
  python svd_parser.py --svd STM32H743.svd --search-register "MODER"
  python svd_parser.py --svd STM32H743.svd --search-field "ENABLE"
        """
    )
    
    parser.add_argument("--svd", "-s", help="SVD file path or name")
    parser.add_argument("--list-svd", action="store_true", help="List available SVD files")
    parser.add_argument("--summary", action="store_true", help="Show device summary")
    parser.add_argument("--list", "-l", action="store_true", help="List all peripherals")
    parser.add_argument("--peripheral", "-p", help="Peripheral name to inspect")
    parser.add_argument("--register", "-r", help="Register name to show details")
    parser.add_argument("--search-register", help="Search registers by pattern")
    parser.add_argument("--search-field", help="Search bit fields by pattern")
    parser.add_argument("--export-json", "-j", help="Export to JSON file")
    parser.add_argument("--export-header", "-h", help="Export C header file")
    parser.add_argument("--all", "-a", action="store_true", help="Export all peripherals")
    
    args = parser.parse_args()
    
    if args.list_svd:
        print("Available SVD files:")
        for svd_file in find_svd_files():
            print(f"  {svd_file.name}")
        return 0
    
    if not args.svd:
        parser.print_help()
        return 1
    
    svd_parser = SVDParser()
    
    svd_path = Path(args.svd)
    if not svd_path.is_absolute():
        full_path = Path(SVDParser.SVD_PATH) / args.svd
        if full_path.exists():
            svd_path = full_path
        elif not svd_path.suffix:
            svd_path = Path(SVDParser.SVD_PATH) / f"{args.svd}.svd"
    
    print(f"Parsing SVD: {svd_path}")
    if not svd_parser.parse(str(svd_path)):
        print("Failed to parse SVD file")
        return 1
    
    if args.summary:
        print(svd_parser.generate_summary())
    
    if args.list:
        print("\nPeripherals:")
        for name in svd_parser.list_peripherals():
            peri = svd_parser.get_peripheral(name)
            print(f"  {name}: {peri.description}")
    
    if args.search_register:
        print(f"\nSearching registers matching '{args.search_register}':")
        results = svd_parser.search_registers(args.search_register)
        for peri, reg in results:
            print(f"  {peri.name}.{reg.name} (0x{peri.base_address + reg.address_offset:08X})")
            print(f"    {reg.description}")
    
    if args.search_field:
        print(f"\nSearching bit fields matching '{args.search_field}':")
        results = svd_parser.search_bit_fields(args.search_field)
        for peri, reg, bf in results:
            print(f"  {peri.name}.{reg.name}.{bf.name} [{bf.bit_offset}:{bf.bit_offset + bf.bit_width - 1}]")
            print(f"    {bf.description}")
    
    if args.peripheral:
        peri = svd_parser.get_peripheral(args.peripheral)
        if peri:
            print(f"\nPeripheral: {peri.name}")
            print(f"Base Address: 0x{peri.base_address:08X}")
            print(f"Description: {peri.description}")
            print("\nRegisters:")
            
            for reg in peri.get_all_registers():
                print(f"  {reg.name}: 0x{reg.address_offset:04X} ({reg.access})")
                if args.register and reg.name.upper() == args.register.upper():
                    print(f"    Description: {reg.description}")
                    print(f"    Reset Value: 0x{reg.reset_value:08X}")
                    print(f"    Bit Fields:")
                    for bf in reg.bit_fields:
                        print(f"      [{bf.bit_offset}:{bf.bit_offset + bf.bit_width - 1}] {bf.name}")
                        if bf.enumerated_values:
                            for enum in bf.enumerated_values:
                                print(f"        {enum.value}: {enum.name}")
        else:
            print(f"Peripheral {args.peripheral} not found")
    
    if args.export_json:
        if args.all:
            svd_parser.export_json(args.export_json)
            print(f"Exported all peripherals to {args.export_json}")
        elif args.peripheral:
            svd_parser.export_json(args.export_json, args.peripheral)
            print(f"Exported {args.peripheral} to {args.export_json}")
        else:
            svd_parser.export_json(args.export_json)
            print(f"Exported device to {args.export_json}")
    
    if args.export_header and args.peripheral:
        svd_parser.export_c_header(args.export_header, args.peripheral)
        print(f"Exported {args.peripheral} header to {args.export_header}")
    
    return 0


if __name__ == "__main__":
    exit(main())
