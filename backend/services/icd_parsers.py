"""
ICD-10-CM parsing utilities (no DB logic).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Iterable, Optional


_ORDER_LINE_RE = re.compile(r"^\d{5}\s")


@dataclass
class IcdTxtRow:
    code: str
    code_raw: str
    description: str
    is_billable: bool


@dataclass
class IcdHierarchyRow:
    code: str
    parent_code: Optional[str]
    level: int
    chapter: Optional[str]
    section: Optional[str]
    full_path: Optional[str]


@dataclass
class IcdMetadataRow:
    code: str
    inclusion_terms: list[str]
    excludes1: list[str]
    excludes2: list[str]
    notes: list[str]


@dataclass
class IcdIndexRow:
    term: str
    normalized_term: str
    code: Optional[str]
    parent_term: Optional[str]
    level: Optional[int]
    is_redirect: bool
    redirect_to: Optional[str]


def _strip_dot(code: str) -> str:
    return code.replace(".", "") if code else code


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_term(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return _clean_text(text)


def _element_text(elem: ET.Element) -> str:
    return _clean_text("".join(elem.itertext()))


def parse_icd_txt(file_path: str) -> list[IcdTxtRow]:
    """
    Parse fixed-width ICD TXT files (codes or order file).

    Returns rows with dotted code, dotless code_raw, description, is_billable.
    NOTE: is_billable is intentionally set to False for all rows here.
    Final billable determination happens later via hierarchy leaf detection.
    """
    path = Path(file_path)
    rows: list[IcdTxtRow] = []

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip():
                continue

            # Order file format detection
            if _ORDER_LINE_RE.match(line) and len(line) >= 16 and line[14] in {"0", "1"}:
                code_raw = _clean_text(line[6:13])
                long_desc = _clean_text(line[77:]) if len(line) >= 78 else _clean_text(line[16:])
                description = long_desc
                code = _insert_dot(code_raw)
            else:
                # Codes file format
                code_raw = _clean_text(line[:7])
                description = _clean_text(line[8:]) if len(line) > 8 else ""
                code = _insert_dot(code_raw)

            if code_raw and description:
                rows.append(
                    IcdTxtRow(
                        code=code,
                        code_raw=code_raw,
                        description=description,
                        is_billable=False,
                    )
                )

    return rows


def _insert_dot(code_raw: str) -> str:
    """
    Convert dotless ICD code to dotted representation.
    Rules: insert dot after 3rd character when length > 3.
    """
    code_raw = _clean_text(code_raw)
    if not code_raw:
        return code_raw
    if len(code_raw) <= 3:
        return code_raw
    return f"{code_raw[:3]}.{code_raw[3:]}"


def parse_tabular_xml(file_path: str) -> tuple[list[IcdHierarchyRow], list[IcdMetadataRow]]:
    """
    Parse ICD-10-CM tabular XML using recursive <diag> traversal.

    Returns:
      - hierarchy_data
      - metadata_data
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    hierarchy_data: list[IcdHierarchyRow] = []
    metadata_data: list[IcdMetadataRow] = []

    for chapter_elem in root.findall("chapter"):
        chapter_desc = _element_text(chapter_elem.find("desc")) if chapter_elem.find("desc") is not None else None

        # sectionIndex contains references but actual data is in <section>
        for section_elem in chapter_elem.findall("section"):
            section_desc = _element_text(section_elem.find("desc")) if section_elem.find("desc") is not None else None
            for diag_elem in section_elem.findall("diag"):
                _walk_diag(
                    diag_elem,
                    hierarchy_data,
                    metadata_data,
                    parent_code=None,
                    level=0,
                    chapter=chapter_desc,
                    section=section_desc,
                    path_stack=[],
                )

    return hierarchy_data, metadata_data


def _walk_diag(
    node: ET.Element,
    hierarchy_data: list[IcdHierarchyRow],
    metadata_data: list[IcdMetadataRow],
    parent_code: Optional[str],
    level: int,
    chapter: Optional[str],
    section: Optional[str],
    path_stack: list[str],
) -> None:
    name_elem = node.find("name")
    desc_elem = node.find("desc")
    if name_elem is None or desc_elem is None:
        return

    code = _element_text(name_elem)
    _ = _element_text(desc_elem)  # description not stored here; description lives in icd_codes

    # Build path
    current_path = path_stack + [code]
    full_path = " > ".join(current_path)

    hierarchy_data.append(
        IcdHierarchyRow(
            code=code,
            parent_code=parent_code,
            level=level,
            chapter=chapter,
            section=section,
            full_path=full_path,
        )
    )

    inclusion_terms = _collect_notes(node, "inclusionTerm")
    excludes1 = _collect_notes(node, "excludes1")
    excludes2 = _collect_notes(node, "excludes2")
    notes: list[str] = []
    notes.extend(_collect_notes(node, "includes"))
    notes.extend(_collect_notes(node, "useAdditionalCode"))
    notes.extend(_collect_notes(node, "codeFirst"))
    notes.extend(_collect_notes(node, "codeAlso"))
    notes.extend(_collect_notes(node, "sevenChrNote"))

    seven_chr_defs = node.findall("sevenChrDef")
    for seven_def in seven_chr_defs:
        for ext in seven_def.findall("extension"):
            char = ext.attrib.get("char")
            label = _element_text(ext)
            if char and label:
                notes.append(f"7th:{char}={label}")

    metadata_data.append(
        IcdMetadataRow(
            code=code,
            inclusion_terms=inclusion_terms,
            excludes1=excludes1,
            excludes2=excludes2,
            notes=notes,
        )
    )

    for child in node.findall("diag"):
        _walk_diag(
            child,
            hierarchy_data,
            metadata_data,
            parent_code=code,
            level=level + 1,
            chapter=chapter,
            section=section,
            path_stack=current_path,
        )


def _collect_notes(node: ET.Element, tag: str) -> list[str]:
    notes: list[str] = []
    for container in node.findall(tag):
        for note in container.findall("note"):
            text = _element_text(note)
            if text:
                notes.append(text)
    return notes


def parse_index_xml(file_path: str) -> tuple[list[IcdIndexRow], int]:
    """
    Parse ICD-10-CM index XML and build semantic lookup rows.
    Handles <mainTerm>, nested <term>, <see>, and <seeAlso>.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    rows: list[IcdIndexRow] = []
    invalid_code_count = 0

    for letter in root.findall("letter"):
        for main_term in letter.findall("mainTerm"):
            invalid_code_count += _walk_index_term(
                main_term,
                rows,
                parent_phrase=None,
                level=0,
            )

    return rows, invalid_code_count


def _walk_index_term(
    node: ET.Element,
    rows: list[IcdIndexRow],
    parent_phrase: Optional[str],
    level: int,
) -> int:
    invalid_code_count = 0
    title_elem = node.find("title")
    if title_elem is None:
        return 0

    title = _element_text(title_elem)
    phrase = _clean_text(f"{parent_phrase} {title}" if parent_phrase else title)
    normalized = _normalize_term(phrase)

    code_elem = node.find("code")
    code = _element_text(code_elem) if code_elem is not None else None
    if code and code.endswith("-"):
        code = None
        invalid_code_count += 1

    see_elem = node.find("see")
    see_also_elem = node.find("seeAlso")

    if code:
        rows.append(
            IcdIndexRow(
                term=title,
                normalized_term=normalized,
                code=code,
                parent_term=parent_phrase,
                level=level,
                is_redirect=False,
                redirect_to=None,
            )
        )

    if see_elem is not None:
        rows.append(
            IcdIndexRow(
                term=title,
                normalized_term=normalized,
                code=None,
                parent_term=parent_phrase,
                level=level,
                is_redirect=True,
                redirect_to=_element_text(see_elem),
            )
        )

    if see_also_elem is not None:
        rows.append(
            IcdIndexRow(
                term=title,
                normalized_term=normalized,
                code=None,
                parent_term=parent_phrase,
                level=level,
                is_redirect=False,
                redirect_to=_element_text(see_also_elem),
            )
        )

    for child in node.findall("term"):
        child_level = level + 1
        level_attr = child.attrib.get("level")
        if level_attr and level_attr.isdigit():
            child_level = int(level_attr)

        invalid_code_count += _walk_index_term(
            child,
            rows,
            parent_phrase=phrase,
            level=child_level,
        )

    return invalid_code_count


# --- Sample runner (for manual testing) ---
if __name__ == "__main__":
    # This block is intentionally minimal and local-only.
    # Use scripts/run_icd_ingestion.py for full ingestion.
    pass
