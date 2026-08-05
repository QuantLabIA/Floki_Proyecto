"""Parser de listas maestras exportadas desde WPS/WhatsApp.

No depende de Flask: solo requiere que el objeto recibido exponga .filename y .read().
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from pypdf import PdfReader

ALLOWED_MASTER_EXTENSIONS = {".txt", ".csv", ".xlsx", ".docx", ".pdf"}
COMMON_LIST_LABEL = "LISTA COMÚN"
PROMO_LIST_LABEL = "PROMOS"
COMMON_LIST_KEYS = {"lista comun", "lista general", "comun"}
PROMO_LIST_KEYS = {"promo", "promos"}

WHATSAPP_PREFIX_RE = re.compile(r"^\s*\[[^\]]+\]\s*[^:]{1,120}:\s*(.*)$")
SKIP_PHRASES = {
    "se edito este mensaje",
    "mensaje eliminado",
    "imagen omitida",
    "video omitido",
    "sticker omitido",
    "audio omitido",
    "archivo adjunto",
    "documento omitido",
    "gif omitido",
}
HEADER_WORDS = {
    "nombre",
    "nombres",
    "persona",
    "personas",
    "invitado",
    "invitados",
    "lista",
    "guest",
    "guests",
}


def _clean_unicode(value: object) -> str:
    text = str(value or "")
    replacements = {
        "\ufeff": "",
        "\u200e": "",
        "\u200f": "",
        "\u202a": "",
        "\u202c": "",
        "\u00a0": " ",
        "\u202f": " ",
        "\u2009": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def clean_line(value: object) -> str:
    text = _clean_unicode(value).strip()
    text = re.sub(r"^\s*[•·▪◦*-]+\s*", "", text)
    text = re.sub(r"^\s*\d+\s*[.)-]+\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_text_key(value: object) -> str:
    text = clean_line(value)
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9 ]+", "", folded.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_guest(value: object) -> tuple[str, str]:
    display = clean_line(value)[:120]
    return display, normalize_text_key(display)[:140]


def normalize_promoter_name(value: object) -> tuple[str, str]:
    display = clean_line(value).upper()[:80]
    return display, normalize_text_key(display)[:100]


def decode_text_file(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo leer la codificación del archivo")


def xlsx_first_values(raw: bytes) -> list[str]:
    values: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for item in root.findall("m:si", namespace):
                    shared.append("".join(node.text or "" for node in item.findall(".//m:t", namespace)))

            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
            ns = {
                "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
                "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            }
            sheet = workbook.find("m:sheets/m:sheet", ns)
            if sheet is None:
                return []
            target = rel_map[sheet.attrib[f"{{{ns['r']}}}id"]]
            clean_target = target.lstrip("/")
            sheet_path = clean_target if clean_target.startswith("xl/") else "xl/" + clean_target
            root = ET.fromstring(archive.read(sheet_path))
            for row in root.findall(".//m:sheetData/m:row", ns):
                row_values: list[str] = []
                for cell in row.findall("m:c", ns):
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("m:v", ns)
                    inline_nodes = cell.findall("m:is/m:t", ns)
                    value = ""
                    if inline_nodes:
                        value = "".join(node.text or "" for node in inline_nodes)
                    elif value_node is not None:
                        value = value_node.text or ""
                        if cell_type == "s" and value.isdigit():
                            index = int(value)
                            value = shared[index] if index < len(shared) else ""
                    if str(value).strip():
                        row_values.append(str(value))
                values.append(row_values[0] if row_values else "")
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError("El archivo XLSX no es válido o está dañado") from exc
    return values


def docx_text_lines(raw: bytes) -> list[str]:
    lines: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml = archive.read("word/document.xml")
            root = ET.fromstring(xml)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            for paragraph in root.findall(".//w:p", ns):
                pieces: list[str] = []
                for node in paragraph.iter():
                    if node.tag == f"{{{ns['w']}}}t":
                        pieces.append(node.text or "")
                    elif node.tag == f"{{{ns['w']}}}tab":
                        pieces.append(" ")
                    elif node.tag == f"{{{ns['w']}}}br":
                        pieces.append("\n")
                paragraph_text = "".join(pieces)
                lines.extend(paragraph_text.splitlines() or [""])
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError("El archivo DOCX no es válido o está dañado") from exc
    return lines



def pdf_text_lines(raw: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(raw))
        lines: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())
        if not any(line.strip() for line in lines):
            raise ValueError("El PDF no contiene texto seleccionable")
        return lines
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("El archivo PDF no es válido o está dañado") from exc

def extract_source_lines(filename: str, raw: bytes) -> list[str]:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_MASTER_EXTENSIONS:
        raise ValueError("Usá un archivo PDF, DOCX, TXT, CSV o XLSX exportado desde WPS")
    if extension == ".xlsx":
        return xlsx_first_values(raw)
    if extension == ".docx":
        return docx_text_lines(raw)
    if extension == ".pdf":
        return pdf_text_lines(raw)

    text = decode_text_file(raw)
    if extension == ".txt":
        return text.splitlines()
    # Algunos CSV exportados desde WPS conservan cada mensaje completo, pero las
    # comas de la fecha harían que un lector CSV normal lo corte en varias celdas.
    if any(WHATSAPP_PREFIX_RE.match(_clean_unicode(line)) for line in text.splitlines()):
        return text.splitlines()

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    lines: list[str] = []
    for row in csv.reader(io.StringIO(text), dialect):
        first = next((cell for cell in row if str(cell).strip()), "")
        lines.append(first)
    return lines


def _is_skip_line(value: str) -> bool:
    key = normalize_text_key(value)
    if not key or key in HEADER_WORDS:
        return True
    if any(phrase in key for phrase in SKIP_PHRASES):
        return True
    lowered = value.casefold()
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    return False


def looks_like_person_name(value: str) -> bool:
    text = clean_line(value)
    if _is_skip_line(text):
        return False
    if ":" in text and len(text.split(":", 1)[0]) < 20:
        return False
    if sum(char.isalpha() for char in text) < 2:
        return False
    if sum(char.isdigit() for char in text) > 1:
        return False
    words = text.split()
    return 1 <= len(words) <= 8 and len(text) <= 120


def is_uppercase_promoter(value: str) -> bool:
    text = clean_line(value)
    key = normalize_text_key(text)
    if key in COMMON_LIST_KEYS:
        return True
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 3 or len(text) > 80 or any(char.isdigit() for char in text):
        return False
    return all(not char.islower() for char in letters) and len(text.split()) <= 6


def split_messages(lines: Iterable[str]) -> tuple[list[list[str]], bool]:
    messages: list[list[str]] = []
    current: list[str] | None = None
    saw_whatsapp = False

    for raw_line in lines:
        line = _clean_unicode(raw_line)
        match = WHATSAPP_PREFIX_RE.match(line)
        if match:
            saw_whatsapp = True
            if current is not None:
                messages.append(current)
            current = [match.group(1)]
        elif saw_whatsapp:
            if current is None:
                current = []
            current.append(line)

    if saw_whatsapp:
        if current is not None:
            messages.append(current)
        return messages, True

    # Para documentos sin marcas de WhatsApp, los bloques separados por una línea
    # vacía se consideran mensajes. Esto conserva el formato típico de WPS.
    current = []
    for raw_line in lines:
        line = _clean_unicode(raw_line)
        if not line.strip():
            if current:
                messages.append(current)
                current = []
        else:
            current.append(line)
    if current:
        messages.append(current)
    return messages, False


def _add_guest(
    groups: OrderedDict[str, dict],
    group_key: str,
    promoter_name: str | None,
    value: str,
    *,
    is_common: bool | None = None,
    is_promo: bool = False,
) -> None:
    display, normalized = normalize_guest(value)
    if not normalized or not looks_like_person_name(display):
        return
    common_flag = promoter_name is None if is_common is None else bool(is_common)
    group = groups.setdefault(
        group_key,
        {
            "promoter_name": promoter_name,
            "is_common": common_flag,
            "is_promo": bool(is_promo),
            "guests": OrderedDict(),
        },
    )
    group["guests"].setdefault(normalized, display)


def parse_master_lines(lines: Iterable[str]) -> tuple[list[dict], dict]:
    messages, whatsapp_format = split_messages(lines)
    groups: OrderedDict[str, dict] = OrderedDict()
    common_key = "__common__"
    promo_key = "__promo__"

    for message in messages:
        cleaned = [clean_line(line) for line in message]
        cleaned = [line for line in cleaned if line and not _is_skip_line(line)]
        if not cleaned:
            continue

        if whatsapp_format:
            first = cleaned[0]
            if is_uppercase_promoter(first):
                promoter_display, normalized_header = normalize_promoter_name(first)
                if normalized_header in COMMON_LIST_KEYS:
                    group_key = common_key
                    promoter_display = None
                    is_common = True
                    is_promo = False
                elif normalized_header in PROMO_LIST_KEYS:
                    group_key = promo_key
                    promoter_display = PROMO_LIST_LABEL
                    is_common = False
                    is_promo = True
                else:
                    group_key = normalized_header
                    is_common = False
                    is_promo = False
                for guest_line in cleaned[1:]:
                    _add_guest(
                        groups,
                        group_key,
                        promoter_display,
                        guest_line,
                        is_common=is_common,
                        is_promo=is_promo,
                    )
            else:
                for guest_line in cleaned:
                    _add_guest(groups, common_key, None, guest_line, is_common=True)
            continue

        current_key = common_key
        current_promoter: str | None = None
        current_is_common = True
        current_is_promo = False
        for line in cleaned:
            if is_uppercase_promoter(line):
                promoter_display, normalized_header = normalize_promoter_name(line)
                if normalized_header in COMMON_LIST_KEYS:
                    current_key, current_promoter = common_key, None
                    current_is_common, current_is_promo = True, False
                elif normalized_header in PROMO_LIST_KEYS:
                    current_key, current_promoter = promo_key, PROMO_LIST_LABEL
                    current_is_common, current_is_promo = False, True
                else:
                    current_key, current_promoter = normalized_header, promoter_display
                    current_is_common, current_is_promo = False, False
                groups.setdefault(
                    current_key,
                    {
                        "promoter_name": current_promoter,
                        "is_common": current_is_common,
                        "is_promo": current_is_promo,
                        "guests": OrderedDict(),
                    },
                )
            else:
                _add_guest(
                    groups,
                    current_key,
                    current_promoter,
                    line,
                    is_common=current_is_common,
                    is_promo=current_is_promo,
                )

    result: list[dict] = []
    total_guests = 0
    promoter_count = 0
    promo_count = 0
    common_count = 0
    for group in groups.values():
        guests = [(display, normalized) for normalized, display in group["guests"].items()]
        if not guests:
            continue
        item = {
            "promoter_name": group["promoter_name"],
            "is_common": bool(group.get("is_common")),
            "is_promo": bool(group.get("is_promo")),
            "guests": guests,
        }
        result.append(item)
        total_guests += len(guests)
        if item["is_common"]:
            common_count += len(guests)
        elif item["is_promo"]:
            promo_count += len(guests)
        else:
            promoter_count += 1

    return result, {
        "whatsapp_format": whatsapp_format,
        "message_count": len(messages),
        "promoter_count": promoter_count,
        "promo_count": promo_count,
        "common_count": common_count,
        "guest_count": total_guests,
    }


def parse_master_file(file_storage) -> tuple[str, list[dict], dict]:
    filename = Path(getattr(file_storage, "filename", "") or "").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_MASTER_EXTENSIONS:
        raise ValueError("Usá un archivo PDF, DOCX, TXT, CSV o XLSX exportado desde WPS")
    raw = file_storage.read()
    if not raw:
        raise ValueError("El archivo está vacío")
    lines = extract_source_lines(filename, raw)
    groups, metadata = parse_master_lines(lines)
    if not groups or metadata["guest_count"] == 0:
        raise ValueError("No se encontraron nombres válidos en el archivo")
    return filename[:180], groups, metadata
