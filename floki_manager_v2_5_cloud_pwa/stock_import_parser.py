"""Importador sencillo de stock para PDF y XLSX.

Lee archivos de inventario exportados desde WPS/Excel y devuelve filas con
producto, cantidad y una categorización sugerida. No usa OCR: los PDF deben
contener texto seleccionable.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pypdf import PdfReader

ALLOWED_STOCK_EXTENSIONS = {".pdf", ".xlsx"}

TYPE_KEYWORDS = (
    ("Cerveza", ("cerveza", "beer")),
    ("Fernet", ("fernet", "branca", "1882", "vittone")),
    ("Vodka", ("vodka", "smirnoff", "absolut", "skyy", "sernova")),
    ("Gin", ("gin", "gordon", "bombay", "beefeater", "tanqueray", "heraclito", "bosque")),
    ("Whisky", ("whisky", "whiskey", "johnnie", "chivas", "jack daniel", "jameson", "ballantine")),
    ("Ron", ("ron", "bacardi", "havana")),
    ("Gancia", ("gancia",)),
    ("Tequila", ("tequila",)),
    ("Espumante", ("champagne", "espumante", "chandon")),
    ("Vino", ("vino", "norton", "zuccardi")),
    ("Energizante", ("speed", "red bull", "monster", "energizante")),
    ("Agua", ("agua", "villavicencio", "eco de los andes", "kin")),
    ("Gaseosa", ("coca", "sprite", "fanta", "schweppes", "pepsi", "7up", "gaseosa")),
    ("Trago preparado", ("trago", "combo", "batido", "cocktail", "coctel")),
)

PRESENTATIONS = (
    ("lata 473 ml", ("473", "473ml")),
    ("lata 354 ml", ("354", "354ml")),
    ("lata 250 ml", ("250", "250ml")),
    ("botella 1 l", ("1 litro", "1l", "1000 ml", "1000ml")),
    ("botella 750 ml", ("750", "750ml")),
    ("botella 710 ml", ("710", "710ml")),
    ("botella 500 ml", ("500", "500ml")),
    ("botella 330 ml", ("330", "330ml")),
    ("vaso grande", ("vaso grande",)),
    ("vaso chico", ("vaso chico",)),
    ("lata", ("lata",)),
    ("botella", ("botella",)),
    ("vaso", ("vaso",)),
    ("copa", ("copa",)),
    ("shot", ("shot",)),
    ("jarra", ("jarra",)),
    ("balde", ("balde",)),
    ("pack", ("pack",)),
    ("caja", ("caja",)),
    ("unidad", ("unidad", "unidades")),
)


def normalize(value: object) -> str:
    text = str(value or "").strip().casefold()
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def _xlsx_rows(raw: bytes) -> list[list[str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for item in root.findall("m:si", ns):
                    shared.append("".join(node.text or "" for node in item.findall(".//m:t", ns)))

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
            rows: list[list[str]] = []
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
                    row_values.append(str(value).strip())
                if any(row_values):
                    rows.append(row_values)
            return rows
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError("El archivo Excel no es válido o está dañado") from exc


def _pdf_lines(raw: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(raw))
        lines: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            lines.extend(line.strip() for line in text.splitlines() if line.strip())
        if not lines:
            raise ValueError("El PDF no contiene texto seleccionable")
        return lines
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("No se pudo leer el PDF de stock") from exc


def _to_number(value: object) -> float | None:
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return None
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    if number < 0 or number > 100000:
        return None
    return round(number, 3)


def _rows_to_items(rows: list[list[str]]) -> list[tuple[str, float]]:
    if not rows:
        return []
    header_index = None
    name_col = 0
    qty_col = 1
    for index, row in enumerate(rows[:20]):
        keys = [normalize(cell) for cell in row]
        for pos, key in enumerate(keys):
            if any(word in key for word in ("bebida", "producto", "mercaderia", "descripcion", "articulo")):
                name_col = pos
                header_index = index
            if any(word in key for word in ("cantidad inicial", "stock inicial", "cantidad", "stock", "unidades")):
                qty_col = pos
                header_index = index
        if header_index is not None:
            break

    data_rows = rows[(header_index + 1) if header_index is not None else 0:]
    items: list[tuple[str, float]] = []
    for row in data_rows:
        if not row:
            continue
        name = row[name_col].strip() if name_col < len(row) else ""
        quantity = _to_number(row[qty_col]) if qty_col < len(row) else None
        if not name or quantity is None:
            # Fallback: primer texto y primer número distinto.
            name = next((cell.strip() for cell in row if cell.strip() and _to_number(cell) is None), "")
            quantity = next((_to_number(cell) for cell in row if _to_number(cell) is not None), None)
        if name and quantity is not None and normalize(name) not in {"total", "subtotal"}:
            items.append((name[:120], quantity))
    return items


def _lines_to_items(lines: list[str]) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    for line in lines:
        clean = re.sub(r"\s+", " ", line).strip()
        if not clean:
            continue
        match = re.match(r"^(.+?)\s+[|;:\-]?\s*(\d+(?:[.,]\d+)?)\s*$", clean)
        if not match:
            match_rev = re.match(r"^(\d+(?:[.,]\d+)?)\s+[|;:\-]?\s*(.+)$", clean)
            if match_rev:
                qty = _to_number(match_rev.group(1))
                name = match_rev.group(2).strip()
            else:
                continue
        else:
            name = match.group(1).strip(" -|;:")
            qty = _to_number(match.group(2))
        if qty is not None and name and normalize(name) not in {"total", "subtotal"}:
            items.append((name[:120], qty))
    return items


def classify_product(raw_name: str, brands: tuple[str, ...]) -> dict:
    key = normalize(raw_name)
    beverage_type = "Otro"
    for candidate, words in TYPE_KEYWORDS:
        if any(normalize(word) in key for word in words):
            beverage_type = candidate
            break

    brand = "Sin marca"
    brand_matches = sorted(
        (item for item in brands if item != "Sin marca" and normalize(item) in key),
        key=lambda item: len(normalize(item)),
        reverse=True,
    )
    if brand_matches:
        brand = brand_matches[0]

    presentation = "unidad"
    for candidate, words in PRESENTATIONS:
        if any(normalize(word) in key for word in words):
            presentation = candidate
            break
    if presentation == "unidad":
        if beverage_type in {"Cerveza", "Energizante", "Gaseosa"}:
            presentation = "lata"
        elif beverage_type in {"Fernet", "Vodka", "Gin", "Whisky", "Ron", "Gancia", "Tequila", "Vino", "Espumante", "Agua"}:
            presentation = "botella"

    if presentation.startswith("lata"):
        stock_unit = "lata"
    elif presentation.startswith("botella"):
        stock_unit = "botella"
    elif presentation == "pack":
        stock_unit = "pack"
    elif presentation == "caja":
        stock_unit = "caja"
    else:
        stock_unit = "unidad"

    return {
        "raw_name": raw_name,
        "beverage_type": beverage_type,
        "brand": brand,
        "presentation": presentation,
        "stock_unit": stock_unit,
    }


def parse_stock_file(file_storage, brands: tuple[str, ...]) -> tuple[str, list[dict]]:
    filename = Path(file_storage.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_STOCK_EXTENSIONS:
        raise ValueError("Usá un archivo PDF o Excel (.xlsx)")
    raw = file_storage.read()
    if not raw:
        raise ValueError("El archivo de stock está vacío")

    if extension == ".xlsx":
        parsed = _rows_to_items(_xlsx_rows(raw))
    else:
        parsed = _lines_to_items(_pdf_lines(raw))
    if not parsed:
        raise ValueError("No se encontraron filas con bebida y cantidad. Usá columnas o líneas con nombre y cantidad")

    merged: dict[str, dict] = {}
    for raw_name, quantity in parsed:
        item = classify_product(raw_name, brands)
        key = normalize(raw_name)
        if key in merged:
            merged[key]["quantity"] = round(merged[key]["quantity"] + quantity, 3)
        else:
            item["quantity"] = quantity
            merged[key] = item
    return filename[:180], list(merged.values())
