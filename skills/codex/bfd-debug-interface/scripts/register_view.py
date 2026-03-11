#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STM32 Register Viewer
外设寄存器查看与修改工具

功能:
1. 外设寄存器实时查看
2. 寄存器位域解析
3. 寄存器值修改
4. 寄存器历史记录
5. 与SVD文件集成

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
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET


@dataclass
class BitField:
    name: str
    description: str
    bit_offset: int
    bit_width: int
    access: str
    enumerated_values: Dict[int, str] = field(default_factory=dict)
    
    def get_mask(self) -> int:
        return ((1 << self.bit_width) - 1) << self.bit_offset
    
    def extract_value(self, register_value: int) -> int:
        return (register_value >> self.bit_offset) & ((1 << self.bit_width) - 1)
    
    def set_value(self, register_value: int, field_value: int) -> int:
        mask = self.get_mask()
        cleared = register_value & ~mask
        return cleared | ((field_value & ((1 << self.bit_width) - 1)) << self.bit_offset)


@dataclass
class Register:
    name: str
    description: str
    address_offset: int
    size: int
    access: str
    reset_value: int
    bit_fields: Dict[str, BitField] = field(default_factory=dict)
    current_value: Optional[int] = None
    previous_value: Optional[int] = None
    
    def get_bit_field_value(self, field_name: str) -> Optional[int]:
        if field_name not in self.bit_fields or self.current_value is None:
            return None
        return self.bit_fields[field_name].extract_value(self.current_value)
    
    def set_bit_field_value(self, field_name: str, value: int) -> bool:
        if field_name not in self.bit_fields or self.current_value is None:
            return False
        self.previous_value = self.current_value
        self.current_value = self.bit_fields[field_name].set_value(self.current_value, value)
        return True
    
    def decode(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "address_offset": f"0x{self.address_offset:04X}",
            "value": f"0x{self.current_value:08X}" if self.current_value else "N/A",
            "binary": f"{self.current_value:032b}" if self.current_value else "N/A",
            "bit_fields": {}
        }
        
        for name, field in self.bit_fields.items():
            field_value = field.extract_value(self.current_value) if self.current_value else 0
            field_info = {
                "value": field_value,
                "binary": f"{field_value:0{field.bit_width}b}",
                "description": field.description
            }
            
            if field.enumerated_values and field_value in field.enumerated_values:
                field_info["enumerated"] = field.enumerated_values[field_value]
            
            result["bit_fields"][name] = field_info
        
        return result


@dataclass
class Peripheral:
    name: str
    description: str
    base_address: int
    registers: Dict[str, Register] = field(default_factory=dict)
    
    def get_register(self, reg_name: str) -> Optional[Register]:
        return self.registers.get(reg_name)
    
    def get_register_by_address(self, offset: int) -> Optional[Register]:
        for reg in self.registers.values():
            if reg.address_offset == offset:
                return reg
        return None


class SVDLoader:
    SVD_PATH = r"D:\STM32CubeCLT\STMicroelectronics_CMSIS_SVD"
    
    def __init__(self, svd_file: Optional[str] = None):
        self.svd_file = svd_file
        self.peripherals: Dict[str, Peripheral] = {}
        self.device_name = ""
        self.cpu_name = ""
    
    def load(self, svd_file: Optional[str] = None) -> bool:
        if svd_file:
            self.svd_file = svd_file
        
        if not self.svd_file:
            return False
        
        try:
            tree = ET.parse(self.svd_file)
            root = tree.getroot()
            
            self.device_name = root.findtext("name", "Unknown")
            self.cpu_name = root.findtext("cpu/name", "Unknown")
            
            for peri_elem in root.findall(".//peripheral"):
                peripheral = self._parse_peripheral(peri_elem)
                if peripheral:
                    self.peripherals[peripheral.name] = peripheral
            
            return True
        except Exception as e:
            print(f"Failed to load SVD file: {e}")
            return False
    
    def _parse_peripheral(self, elem: ET.Element) -> Optional[Peripheral]:
        name = elem.findtext("name", "")
        description = elem.findtext("description", "")
        
        base_addr_str = elem.findtext("baseAddress", "0")
        base_address = int(base_addr_str, 16) if base_addr_str.startswith("0x") else int(base_addr_str)
        
        peripheral = Peripheral(
            name=name,
            description=description,
            base_address=base_address
        )
        
        registers_elem = elem.find("registers")
        if registers_elem is None:
            derived = elem.get("derivedFrom")
            if derived and derived in self.peripherals:
                peripheral.registers = self.peripherals[derived].registers.copy()
            return peripheral
        
        for reg_elem in registers_elem.findall("register"):
            register = self._parse_register(reg_elem)
            if register:
                peripheral.registers[register.name] = register
        
        return peripheral
    
    def _parse_register(self, elem: ET.Element) -> Optional[Register]:
        name = elem.findtext("name", "")
        description = elem.findtext("description", "")
        
        offset_str = elem.findtext("addressOffset", "0")
        address_offset = int(offset_str, 16) if offset_str.startswith("0x") else int(offset_str)
        
        size_str = elem.findtext("size", "32")
        size = int(size_str)
        
        access = elem.findtext("access", "read-write")
        
        reset_str = elem.findtext("resetValue", "0")
        reset_value = int(reset_str, 16) if reset_str.startswith("0x") else int(reset_str)
        
        register = Register(
            name=name,
            description=description,
            address_offset=address_offset,
            size=size,
            access=access,
            reset_value=reset_value
        )
        
        fields_elem = elem.find("fields")
        if fields_elem is not None:
            for field_elem in fields_elem.findall("field"):
                bit_field = self._parse_bit_field(field_elem)
                if bit_field:
                    register.bit_fields[bit_field.name] = bit_field
        
        return register
    
    def _parse_bit_field(self, elem: ET.Element) -> Optional[BitField]:
        name = elem.findtext("name", "")
        description = elem.findtext("description", "")
        
        bit_offset = int(elem.findtext("bitOffset", "0"))
        bit_width = int(elem.findtext("bitWidth", "1"))
        
        access = elem.findtext("access", "read-write")
        
        bit_field = BitField(
            name=name,
            description=description,
            bit_offset=bit_offset,
            bit_width=bit_width,
            access=access
        )
        
        enum_elem = elem.find("enumeratedValues")
        if enum_elem is not None:
            for value_elem in enum_elem.findall("enumeratedValue"):
                value_name = value_elem.findtext("name", "")
                value_str = value_elem.findtext("value", "0")
                value = int(value_str, 16) if value_str.startswith("0x") else int(value_str)
                bit_field.enumerated_values[value] = value_name
        
        return bit_field
    
    def get_peripheral(self, name: str) -> Optional[Peripheral]:
        return self.peripherals.get(name.upper())
    
    def list_peripherals(self) -> List[str]:
        return sorted(self.peripherals.keys())
    
    def find_register_by_address(self, address: int) -> Tuple[Optional[Peripheral], Optional[Register]]:
        for peri in self.peripherals.values():
            for reg in peri.registers.values():
                if peri.base_address + reg.address_offset == address:
                    return peri, reg
        return None, None


class RegisterViewer:
    JLINK_PATH = r"D:\STM32CubeCLT\Segger\JLink_V864a\JLink.exe"
    
    def __init__(self, svd_file: Optional[str] = None):
        self.svd = SVDLoader(svd_file)
        self.history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def load_svd(self, svd_file: str) -> bool:
        return self.svd.load(svd_file)
    
    def read_register_jlink(self, device: str, address: int) -> Optional[int]:
        if not Path(self.JLINK_PATH).exists():
            print(f"J-Link not found at {self.JLINK_PATH}")
            return None
        
        commands = f"""
device {device}
si SWD
speed 4000
connect
mem32 0x{address:08X} 1
exit
"""
        cmd_file = Path("reg_read.jlink")
        with open(cmd_file, "w") as f:
            f.write(commands)
        
        try:
            import subprocess
            result = subprocess.run(
                [self.JLINK_PATH, "-CommandFile", str(cmd_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            for line in result.stdout.split("\n"):
                match = re.search(r"= ([0-9A-Fa-f]+)", line)
                if match:
                    return int(match.group(1), 16)
            
            return None
        except Exception as e:
            print(f"Failed to read register: {e}")
            return None
        finally:
            if cmd_file.exists():
                cmd_file.unlink()
    
    def write_register_jlink(self, device: str, address: int, value: int) -> bool:
        if not Path(self.JLINK_PATH).exists():
            print(f"J-Link not found at {self.JLINK_PATH}")
            return False
        
        commands = f"""
device {device}
si SWD
speed 4000
connect
w4 0x{address:08X} 0x{value:08X}
exit
"""
        cmd_file = Path("reg_write.jlink")
        with open(cmd_file, "w") as f:
            f.write(commands)
        
        try:
            import subprocess
            result = subprocess.run(
                [self.JLINK_PATH, "-CommandFile", str(cmd_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            return "O.K." in result.stdout
        except Exception as e:
            print(f"Failed to write register: {e}")
            return False
        finally:
            if cmd_file.exists():
                cmd_file.unlink()
    
    def view_peripheral(self, peripheral_name: str, device: str = "STM32H743VI") -> Dict[str, Any]:
        peripheral = self.svd.get_peripheral(peripheral_name)
        if not peripheral:
            return {"error": f"Peripheral {peripheral_name} not found"}
        
        result = {
            "peripheral": peripheral_name,
            "base_address": f"0x{peripheral.base_address:08X}",
            "description": peripheral.description,
            "registers": {}
        }
        
        for reg_name, reg in peripheral.registers.items():
            address = peripheral.base_address + reg.address_offset
            value = self.read_register_jlink(device, address)
            reg.current_value = value
            
            result["registers"][reg_name] = reg.decode()
        
        self._add_history("view_peripheral", result)
        return result
    
    def view_register(self, peripheral_name: str, register_name: str, 
                      device: str = "STM32H743VI") -> Dict[str, Any]:
        peripheral = self.svd.get_peripheral(peripheral_name)
        if not peripheral:
            return {"error": f"Peripheral {peripheral_name} not found"}
        
        register = peripheral.get_register(register_name)
        if not register:
            return {"error": f"Register {register_name} not found in {peripheral_name}"}
        
        address = peripheral.base_address + register.address_offset
        value = self.read_register_jlink(device, address)
        register.current_value = value
        
        result = {
            "peripheral": peripheral_name,
            "register": register_name,
            "address": f"0x{address:08X}",
            "decode": register.decode()
        }
        
        self._add_history("view_register", result)
        return result
    
    def modify_register(self, peripheral_name: str, register_name: str, 
                        value: int, device: str = "STM32H743VI") -> Dict[str, Any]:
        peripheral = self.svd.get_peripheral(peripheral_name)
        if not peripheral:
            return {"error": f"Peripheral {peripheral_name} not found"}
        
        register = peripheral.get_register(register_name)
        if not register:
            return {"error": f"Register {register_name} not found in {peripheral_name}"}
        
        address = peripheral.base_address + register.address_offset
        
        old_value = self.read_register_jlink(device, address)
        register.previous_value = old_value
        
        success = self.write_register_jlink(device, address, value)
        if success:
            register.current_value = value
        
        result = {
            "peripheral": peripheral_name,
            "register": register_name,
            "address": f"0x{address:08X}",
            "old_value": f"0x{old_value:08X}" if old_value else "N/A",
            "new_value": f"0x{value:08X}",
            "success": success
        }
        
        self._add_history("modify_register", result)
        return result
    
    def modify_bit_field(self, peripheral_name: str, register_name: str,
                         field_name: str, value: int, 
                         device: str = "STM32H743VI") -> Dict[str, Any]:
        peripheral = self.svd.get_peripheral(peripheral_name)
        if not peripheral:
            return {"error": f"Peripheral {peripheral_name} not found"}
        
        register = peripheral.get_register(register_name)
        if not register:
            return {"error": f"Register {register_name} not found"}
        
        if field_name not in register.bit_fields:
            return {"error": f"Bit field {field_name} not found in {register_name}"}
        
        address = peripheral.base_address + register.address_offset
        old_value = self.read_register_jlink(device, address)
        
        if old_value is None:
            return {"error": "Failed to read current register value"}
        
        register.current_value = old_value
        register.set_bit_field_value(field_name, value)
        new_value = register.current_value
        
        success = self.write_register_jlink(device, address, new_value)
        
        result = {
            "peripheral": peripheral_name,
            "register": register_name,
            "bit_field": field_name,
            "address": f"0x{address:08X}",
            "old_register_value": f"0x{old_value:08X}",
            "new_register_value": f"0x{new_value:08X}",
            "field_old_value": register.bit_fields[field_name].extract_value(old_value),
            "field_new_value": value,
            "success": success
        }
        
        self._add_history("modify_bit_field", result)
        return result
    
    def _add_history(self, action: str, data: Dict[str, Any]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "data": data
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def export_history(self, output_file: str):
        with open(output_file, "w") as f:
            json.dump(self.history, f, indent=2)
    
    def generate_report(self, peripheral_name: str) -> str:
        peripheral = self.svd.get_peripheral(peripheral_name)
        if not peripheral:
            return f"Peripheral {peripheral_name} not found"
        
        lines = [
            "=" * 70,
            f"Peripheral: {peripheral_name}",
            f"Base Address: 0x{peripheral.base_address:08X}",
            f"Description: {peripheral.description}",
            "=" * 70,
            ""
        ]
        
        for reg_name, reg in sorted(peripheral.registers.items(), 
                                    key=lambda x: x[1].address_offset):
            lines.append(f"Register: {reg_name}")
            lines.append(f"  Offset: 0x{reg.address_offset:04X}")
            lines.append(f"  Size: {reg.size} bits")
            lines.append(f"  Access: {reg.access}")
            lines.append(f"  Reset: 0x{reg.reset_value:08X}")
            
            if reg.current_value is not None:
                lines.append(f"  Current: 0x{reg.current_value:08X}")
            
            if reg.bit_fields:
                lines.append("  Bit Fields:")
                for field_name, field in sorted(reg.bit_fields.items(),
                                                key=lambda x: x[1].bit_offset):
                    lines.append(f"    [{field.bit_offset}:{field.bit_offset + field.bit_width - 1}] {field_name}")
                    if reg.current_value is not None:
                        field_val = field.extract_value(reg.current_value)
                        lines.append(f"      Value: {field_val} (0b{field_val:0{field.bit_width}b})")
                        if field_val in field.enumerated_values:
                            lines.append(f"      Meaning: {field.enumerated_values[field_val]}")
            
            lines.append("")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="STM32 Register Viewer - Peripheral register inspection tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python register_view.py --svd STM32H743.svd --list
  python register_view.py --svd STM32H743.svd --peripheral GPIOA
  python register_view.py --svd STM32H743.svd --peripheral GPIOA --register MODER
  python register_view.py --svd STM32H743.svd --peripheral GPIOA --register MODER --modify 0x12345678
  python register_view.py --svd STM32H743.svd --peripheral GPIOA --register MODER --field MODE0 --value 1
        """
    )
    
    parser.add_argument("--svd", "-s", required=True, help="SVD file path")
    parser.add_argument("--device", "-d", default="STM32H743VI", help="Target device name")
    parser.add_argument("--list", "-l", action="store_true", help="List all peripherals")
    parser.add_argument("--peripheral", "-p", help="Peripheral name")
    parser.add_argument("--register", "-r", help="Register name")
    parser.add_argument("--field", "-f", help="Bit field name")
    parser.add_argument("--modify", "-m", type=lambda x: int(x, 0), help="New register value (hex or decimal)")
    parser.add_argument("--value", "-v", type=lambda x: int(x, 0), help="New bit field value")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    parser.add_argument("--export", "-x", help="Export history to file")
    
    args = parser.parse_args()
    
    viewer = RegisterViewer()
    
    svd_path = Path(args.svd)
    if not svd_path.is_absolute():
        svd_path = Path(SVDLoader.SVD_PATH) / args.svd
        if not svd_path.exists():
            svd_path = Path(args.svd)
    
    print(f"Loading SVD: {svd_path}")
    if not viewer.load_svd(str(svd_path)):
        print("Failed to load SVD file")
        return 1
    
    if args.list:
        print("\nAvailable Peripherals:")
        for name in viewer.svd.list_peripherals():
            peri = viewer.svd.get_peripheral(name)
            print(f"  {name}: 0x{peri.base_address:08X} ({len(peri.registers)} registers)")
        return 0
    
    if args.peripheral:
        if args.modify is not None and args.register:
            if args.field and args.value is not None:
                result = viewer.modify_bit_field(
                    args.peripheral, args.register, args.field, args.value, args.device
                )
            else:
                result = viewer.modify_register(
                    args.peripheral, args.register, args.modify, args.device
                )
            print(json.dumps(result, indent=2))
        elif args.register:
            result = viewer.view_register(args.peripheral, args.register, args.device)
            print(json.dumps(result, indent=2, default=str))
        else:
            if args.report:
                print(viewer.generate_report(args.peripheral))
            else:
                result = viewer.view_peripheral(args.peripheral, args.device)
                print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()
    
    if args.export:
        viewer.export_history(args.export)
        print(f"History exported to {args.export}")
    
    return 0


if __name__ == "__main__":
    exit(main())
