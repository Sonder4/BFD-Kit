#!/usr/bin/env python3
"""
STM32 J-Link Flash Programmer
使用 SEGGER J-Link 进行 Flash 编程
"""

import argparse
import subprocess
import sys
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List

DEFAULT_JLINK_EXE = os.environ.get("JLINK_EXE") or shutil.which("JLinkExe") or "JLinkExe"
DEFAULT_DEVICE = os.environ.get("STM32_DEVICE", "STM32F427II")
DEFAULT_INTERFACE = os.environ.get("STM32_IF", "SWD")
DEFAULT_SPEED = int(os.environ.get("STM32_SPEED_KHZ", "4000"))

class JLinkFlasher:
    def __init__(self, device: str = DEFAULT_DEVICE, interface: str = DEFAULT_INTERFACE,
                 speed: int = DEFAULT_SPEED, verbose: bool = False, jlink_path: str = DEFAULT_JLINK_EXE):
        self.device = device
        self.interface = interface.upper()
        self.speed = speed
        self.verbose = verbose
        self.jlink_path = jlink_path

        if os.path.isabs(self.jlink_path):
            if not os.path.exists(self.jlink_path):
                raise FileNotFoundError(f"J-Link not found: {self.jlink_path}")
        else:
            resolved = shutil.which(self.jlink_path)
            if not resolved:
                raise FileNotFoundError(f"J-Link executable not found in PATH: {self.jlink_path}")
            self.jlink_path = resolved
    
    def _create_script(self, commands: List[str]) -> str:
        script_content = "\n".join(commands)
        if self.verbose:
            print(f"J-Link Script:\n{script_content}\n")
        return script_content
    
    def _run_script(self, script_content: str) -> tuple:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jlink', 
                                         delete=False, encoding='utf-8') as f:
            f.write(script_content)
            script_path = f.name
        
        try:
            cmd = [
                self.jlink_path,
                "-device", self.device,
                "-if", self.interface,
                "-speed", str(self.speed),
                "-autoconnect", "1",
                "-CommandFile", script_path
            ]
            
            if self.verbose:
                print(f"Executing: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
        finally:
            if os.path.exists(script_path):
                os.unlink(script_path)
    
    def connect(self) -> bool:
        print(f"Connecting to {self.device} via {self.interface}...")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
            "r",  # Reset
            "h",  # Halt
            "g",  # Go
            "exit"
        ]
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0 and "Found" in stdout:
            print("Connected successfully")
            if self.verbose:
                print(stdout)
            return True
        else:
            print(f"Connection failed")
            if self.verbose:
                print(stdout)
                print(stderr)
            return False
    
    def detect_device(self) -> Optional[dict]:
        print("Detecting target device...")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
            "r",
            "h",
            "JTAG.DP.IDCODE",  # Read DP IDCODE
            "exit"
        ]
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0:
            device_info = {
                'device': self.device,
                'interface': self.interface,
                'speed': self.speed
            }
            
            lines = stdout.split('\n')
            for line in lines:
                if 'Found' in line or 'IDCODE' in line:
                    if self.verbose:
                        print(line.strip())
            
            print(f"Device: {self.device}")
            return device_info
        else:
            print(f"Device detection failed")
            return None
    
    def erase(self, erase_type: str = "all") -> bool:
        print(f"Erasing Flash (type: {erase_type})...")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
            "r",
            "h",
        ]
        
        if erase_type == "all":
            commands.append("erase")
        else:
            commands.append("erase sectors")
        
        commands.append("exit")
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0 and "Erasing done" in stdout:
            print("Erase completed successfully")
            return True
        else:
            print("Erase failed")
            if self.verbose:
                print(stdout)
                print(stderr)
            return False
    
    def flash(self, firmware_path: str, address: int = 0x08000000,
              erase: bool = True, verify: bool = True) -> bool:
        firmware_path = os.path.abspath(firmware_path)
        
        if not os.path.exists(firmware_path):
            print(f"Firmware file not found: {firmware_path}")
            return False
        
        file_size = os.path.getsize(firmware_path)
        print(f"Flashing firmware: {firmware_path}")
        print(f"File size: {file_size} bytes")
        print(f"Target address: 0x{address:08X}")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
            "r",
            "h",
        ]
        
        if erase:
            commands.append("erase")
        
        commands.append(f"loadfile {firmware_path} 0x{address:08X}")
        
        if verify:
            print("Verification step is skipped in flash command because J-Link Commander on this setup does not support verifyfile.")
        
        commands.append("exit")
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0 and ("O.K." in stdout or "Flash download:" in stdout):
            print("Flash programming completed successfully")
            if self.verbose:
                print(stdout)
            return True
        else:
            print("Flash programming failed")
            print(stdout)
            if stderr:
                print(stderr)
            return False
    
    def verify(self, firmware_path: str, address: int = 0x08000000) -> bool:
        firmware_path = os.path.abspath(firmware_path)

        if not os.path.exists(firmware_path):
            print(f"Firmware file not found: {firmware_path}")
            return False

        print("Standalone verify is not supported on this setup because J-Link Commander does not provide verifyfile.")
        print("Use flash output plus spot-check reads if explicit post-flash validation is required.")
        return False
    
    def reset(self, reset_type: str = "hardware") -> bool:
        print(f"Resetting target (type: {reset_type})...")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
        ]
        
        if reset_type == "hardware":
            commands.append("r")  # Hardware reset
        else:
            commands.append("rx")  # Reset and halt
        
        commands.append("g")  # Go
        commands.append("exit")
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0:
            print("Target reset successfully")
            return True
        else:
            print("Reset failed")
            return False
    
    def run(self) -> bool:
        print("Starting target execution...")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
            "r",
            "g",
            "exit"
        ]
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0:
            print("Target started successfully")
            return True
        else:
            print("Start failed")
            return False
    
    def read_memory(self, output_path: str, address: int, size: int) -> bool:
        print(f"Reading memory: 0x{address:08X}, size: {size} bytes")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
            "r",
            "h",
            f"savebin {output_path} 0x{address:08X} {size}",
            "exit"
        ]
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0:
            print(f"Memory read completed: {output_path}")
            return True
        else:
            print("Memory read failed")
            return False
    
    def unlock(self) -> bool:
        print("Unlock is not implemented for this project.")
        print("Please use the project-specific STM32 recovery flow if read protection must be cleared.")
        return False
    
    def get_cpu_info(self) -> Optional[str]:
        print("Reading CPU information...")
        
        commands = [
            "connect",
            f"device {self.device}",
            f"si {self.interface.lower()}",
            f"speed {self.speed}",
            "r",
            "h",
            "cpuid",
            "exit"
        ]
        
        script = self._create_script(commands)
        ret, stdout, stderr = self._run_script(script)
        
        if ret == 0:
            print("CPU Information:")
            print(stdout)
            return stdout
        else:
            print("Failed to read CPU information")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="STM32 J-Link Flash Programmer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --firmware build_gcc/RSCF_A.hex
  %(prog)s --firmware build_gcc/RSCF_A.hex --device STM32F427II --address 0x08000000
  %(prog)s --detect --device STM32F427II
  %(prog)s --read flash_dump.bin --address 0x08000000 --size 0x10000
  %(prog)s --reset
        """
    )
    
    parser.add_argument("--firmware", "-f", help="Firmware file path")
    parser.add_argument("--device", "-d", default=DEFAULT_DEVICE,
                       help=f"Target device (default: {DEFAULT_DEVICE})")
    parser.add_argument("--address", "-a", type=lambda x: int(x, 0),
                       default=0x08000000, help="Target address (default: 0x08000000)")
    parser.add_argument("--interface", "-i", choices=["SWD", "JTAG"], default=DEFAULT_INTERFACE,
                       help=f"Debug interface (default: {DEFAULT_INTERFACE})")
    parser.add_argument("--speed", "-s", type=int, default=DEFAULT_SPEED,
                       help=f"Connection speed in kHz (default: {DEFAULT_SPEED})")
    parser.add_argument("--erase", "-e", action="store_true", default=True,
                       help="Erase before flashing (default: True)")
    parser.add_argument("--no-erase", dest="erase", action="store_false",
                       help="Skip erase before flashing")
    parser.add_argument("--verify", "-v", action="store_true", default=True,
                       help="Verify after flashing (default: True)")
    parser.add_argument("--no-verify", dest="verify", action="store_false",
                       help="Skip verification")
    parser.add_argument("--reset", "-r", action="store_true", default=True,
                       help="Reset after flashing (default: True)")
    parser.add_argument("--no-reset", dest="reset", action="store_false",
                       help="Skip reset after flashing")
    parser.add_argument("--detect", action="store_true",
                       help="Detect target device")
    parser.add_argument("--unlock", "-u", action="store_true",
                       help="Unlock device")
    parser.add_argument("--read", help="Read flash to file")
    parser.add_argument("--size", type=lambda x: int(x, 0),
                       help="Size to read (required with --read)")
    parser.add_argument("--cpu-info", action="store_true",
                       help="Display CPU information")
    parser.add_argument("--verbose", "-V", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    try:
        flasher = JLinkFlasher(
            device=args.device,
            interface=args.interface,
            speed=args.speed,
            verbose=args.verbose
        )
        
        if args.detect:
            device = flasher.detect_device()
            if device:
                print(f"\nDevice Information:")
                for key, value in device.items():
                    print(f"  {key}: {value}")
            else:
                sys.exit(1)
        
        elif args.unlock:
            if flasher.unlock():
                print("Device unlocked. Note: Flash may have been erased.")
            else:
                sys.exit(1)
        
        elif args.read:
            if not args.size:
                print("Error: --size is required with --read")
                sys.exit(1)
            if not flasher.read_memory(args.read, args.address, args.size):
                sys.exit(1)
        
        elif args.cpu_info:
            if not flasher.get_cpu_info():
                sys.exit(1)
        
        elif args.firmware:
            if not flasher.flash(args.firmware, args.address,
                                args.erase, args.verify):
                sys.exit(1)
            
            if args.reset:
                if not flasher.reset():
                    sys.exit(1)
            
            print("\nFlash programming completed successfully!")
        
        else:
            parser.print_help()
            sys.exit(1)
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
