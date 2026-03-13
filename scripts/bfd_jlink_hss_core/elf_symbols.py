"""DWARF-backed fixed-address symbol resolution for native HSS sampling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
import re
from typing import Optional

from elftools.elf.elffile import ELFFile


SEGMENT_PATTERN = re.compile(r"(?P<field>[A-Za-z_]\w*)|\[(?P<index>\d+)\]")
ROOT_PATTERN = re.compile(r"^(?P<root>[A-Za-z_]\w*)(?P<rest>(?:\.[A-Za-z_]\w*|\[\d+\])*)$")
TYPE_ID_MAP = {
    "float": 1,
}


class SymbolResolutionError(RuntimeError):
    """Raised when a symbol path cannot be resolved against DWARF."""


@dataclass
class Segment:
    kind: str
    value: str | int


@dataclass
class ResolvedSymbolPath:
    expression: str
    root_symbol: str
    leaf_name: str
    final_type_tag: str
    final_type_name: Optional[str]
    final_type_display: str
    type_id: int
    offset: int
    root_address: int
    final_address: int
    byte_size: int
    source_file: Optional[str]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["root_address_hex"] = f"0x{self.root_address:08X}"
        payload["final_address_hex"] = f"0x{self.final_address:08X}"
        return payload


def _decode_name(die) -> str:
    attr = die.attributes.get("DW_AT_name")
    if not attr:
        return ""
    value = attr.value
    return value.decode(errors="ignore") if isinstance(value, bytes) else str(value)


def _load_elf(elf_path: str | Path) -> ELFFile:
    path = Path(elf_path)
    return ELFFile(BytesIO(path.read_bytes()))


def _parse_symbol_path(expression: str) -> tuple[str, list[Segment]]:
    match = ROOT_PATTERN.match(expression)
    if not match:
        raise SymbolResolutionError(f"unsupported symbol path syntax: {expression}")
    root_symbol = match.group("root")
    rest = match.group("rest")
    segments: list[Segment] = []
    cursor = 0
    while cursor < len(rest):
        if rest[cursor] == ".":
            cursor += 1
        segment_match = SEGMENT_PATTERN.match(rest, cursor)
        if not segment_match:
            raise SymbolResolutionError(f"invalid symbol path segment near: {rest[cursor:]}")
        if segment_match.group("field") is not None:
            segments.append(Segment("field", segment_match.group("field")))
        else:
            segments.append(Segment("index", int(segment_match.group("index"))))
        cursor = segment_match.end()
    return root_symbol, segments


def _find_symbol_address(elffile: ELFFile, symbol_name: str) -> int:
    symtab = elffile.get_section_by_name(".symtab")
    if symtab is None:
        raise SymbolResolutionError("ELF has no .symtab section")
    symbols = symtab.get_symbol_by_name(symbol_name)
    if not symbols:
        raise SymbolResolutionError(f"symbol not found in ELF symbol table: {symbol_name}")
    return int(symbols[0]["st_value"])


def _find_variable_die(dwarf_info, symbol_name: str):
    for cu in dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            if die.tag == "DW_TAG_variable" and _decode_name(die) == symbol_name:
                return cu, die
    raise SymbolResolutionError(f"symbol not found in DWARF variable entries: {symbol_name}")


def _normalize_type_die(die):
    current = die
    while current.tag in {
        "DW_TAG_typedef",
        "DW_TAG_const_type",
        "DW_TAG_volatile_type",
        "DW_TAG_restrict_type",
    }:
        type_attr = current.attributes.get("DW_AT_type")
        if type_attr is None:
            raise SymbolResolutionError(f"type DIE at offset {current.offset} has no DW_AT_type")
        current = current.get_DIE_from_attribute("DW_AT_type")
    return current


def _array_length(die) -> int:
    for child in die.iter_children():
        if child.tag != "DW_TAG_subrange_type":
            continue
        if "DW_AT_count" in child.attributes:
            return int(child.attributes["DW_AT_count"].value)
        if "DW_AT_upper_bound" in child.attributes:
            return int(child.attributes["DW_AT_upper_bound"].value) + 1
    raise SymbolResolutionError(f"array type at DIE offset {die.offset} has no bound metadata")


def _byte_size(die) -> int:
    current = _normalize_type_die(die)
    attr = current.attributes.get("DW_AT_byte_size")
    if attr is None:
        raise SymbolResolutionError(f"type {current.tag} at DIE offset {current.offset} has no byte size")
    return int(attr.value)


def _field_member(struct_die, name: str):
    for child in struct_die.iter_children():
        if child.tag == "DW_TAG_member" and _decode_name(child) == name:
            return child
    raise SymbolResolutionError(f"struct member not found: {name}")


def _describe_type(die) -> str:
    current = _normalize_type_die(die)
    if current.tag == "DW_TAG_base_type":
        return _decode_name(current) or "scalar"
    if current.tag == "DW_TAG_pointer_type":
        target_attr = current.attributes.get("DW_AT_type")
        if target_attr is None:
            return "void*"
        return f"{_describe_type(current.get_DIE_from_attribute('DW_AT_type'))}*"
    if current.tag == "DW_TAG_enumeration_type":
        return _decode_name(current) or "enum"
    if current.tag == "DW_TAG_structure_type":
        name = _decode_name(current) or "anonymous_struct"
        return f"struct {name}"
    if current.tag == "DW_TAG_array_type":
        return f"{_describe_type(current.get_DIE_from_attribute('DW_AT_type'))}[]"
    return _decode_name(current) or current.tag


def _resolve_decl_file(dwarf_info, cu, die) -> Optional[str]:
    decl_attr = die.attributes.get("DW_AT_decl_file")
    if decl_attr is None:
        return None
    try:
        line_program = dwarf_info.line_program_for_CU(cu)
    except Exception:
        return None
    if line_program is None:
        return None

    file_entries = line_program.header.file_entry
    index = int(decl_attr.value) - 1
    if index < 0 or index >= len(file_entries):
        return None

    file_entry = file_entries[index]
    file_name = file_entry.name.decode(errors="ignore") if isinstance(file_entry.name, bytes) else str(file_entry.name)

    directories = line_program.header.include_directory
    dir_name = ""
    dir_index = int(file_entry.dir_index)
    if dir_index > 0 and dir_index - 1 < len(directories):
        raw_dir = directories[dir_index - 1]
        dir_name = raw_dir.decode(errors="ignore") if isinstance(raw_dir, bytes) else str(raw_dir)

    top_die = cu.get_top_DIE()
    comp_dir_attr = top_die.attributes.get("DW_AT_comp_dir")
    comp_dir = ""
    if comp_dir_attr is not None:
        comp_dir = comp_dir_attr.value.decode(errors="ignore") if isinstance(comp_dir_attr.value, bytes) else str(comp_dir_attr.value)

    if dir_name:
        candidate = Path(dir_name)
        if not candidate.is_absolute() and comp_dir:
            candidate = Path(comp_dir) / candidate
        return str((candidate / file_name).resolve())

    if comp_dir:
        return str((Path(comp_dir) / file_name).resolve())
    return file_name


def resolve_symbol_path(elf_path: str | Path, expression: str) -> ResolvedSymbolPath:
    elffile = _load_elf(elf_path)
    if not elffile.has_dwarf_info():
        raise SymbolResolutionError(f"ELF has no DWARF info: {elf_path}")

    root_symbol, segments = _parse_symbol_path(expression)
    dwarf_info = elffile.get_dwarf_info()
    cu, variable_die = _find_variable_die(dwarf_info, root_symbol)
    root_address = _find_symbol_address(elffile, root_symbol)

    type_attr = variable_die.attributes.get("DW_AT_type")
    if type_attr is None:
        raise SymbolResolutionError(f"DWARF variable has no type: {root_symbol}")

    current_die = variable_die.get_DIE_from_attribute("DW_AT_type")
    total_offset = 0
    leaf_name = root_symbol

    for segment in segments:
        current_die = _normalize_type_die(current_die)
        if segment.kind == "field":
            if current_die.tag != "DW_TAG_structure_type":
                raise SymbolResolutionError(f"{segment.value} is not a struct field on type {current_die.tag}")
            member_die = _field_member(current_die, str(segment.value))
            member_location = member_die.attributes.get("DW_AT_data_member_location")
            if member_location is None or not isinstance(member_location.value, int):
                raise SymbolResolutionError(f"unsupported member location for field {segment.value}")
            total_offset += int(member_location.value)
            current_die = member_die.get_DIE_from_attribute("DW_AT_type")
            leaf_name = str(segment.value)
            continue

        if current_die.tag != "DW_TAG_array_type":
            raise SymbolResolutionError(f"index access is not valid on type {current_die.tag}")
        element_die = current_die.get_DIE_from_attribute("DW_AT_type")
        index = int(segment.value)
        length = _array_length(current_die)
        if index < 0 or index >= length:
            raise SymbolResolutionError(f"array index out of range: {index} >= {length}")
        total_offset += _byte_size(element_die) * index
        current_die = element_die

    final_die = _normalize_type_die(current_die)
    final_type_display = _describe_type(final_die)
    source_file = _resolve_decl_file(dwarf_info, cu, variable_die)
    byte_size = _byte_size(final_die)
    type_id = 8 if final_die.tag == "DW_TAG_pointer_type" else TYPE_ID_MAP.get(final_type_display, 0)

    return ResolvedSymbolPath(
        expression=expression,
        root_symbol=root_symbol,
        leaf_name=leaf_name,
        final_type_tag=final_die.tag,
        final_type_name=_decode_name(final_die) or None,
        final_type_display=final_type_display,
        type_id=type_id,
        offset=total_offset,
        root_address=root_address,
        final_address=root_address + total_offset,
        byte_size=byte_size,
        source_file=source_file,
    )
