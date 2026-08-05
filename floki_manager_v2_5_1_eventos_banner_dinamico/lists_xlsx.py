"""Exportación XLSX de listas con buscador rápido compatible con Excel/WPS."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime
from typing import Iterable, Mapping
from xml.sax.saxutils import escape


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(ref: str, value=None, style: int = 0, formula: str | None = None) -> str:
    style_attr = f' s="{style}"' if style else ""
    if formula is not None:
        cached = "" if value is None else f"<v>{escape(str(value))}</v>"
        return f'<c r="{ref}"{style_attr}><f>{escape(formula)}</f>{cached}</c>'
    if value is None or value == "":
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(str(value))}</t></is></c>'


def _row(
    row_index: int,
    values: list,
    styles: list[int] | None = None,
    formulas: list[str | None] | None = None,
    height: float | None = None,
) -> str:
    styles = styles or [0] * len(values)
    formulas = formulas or [None] * len(values)
    cells = []
    for col_index, value in enumerate(values, 1):
        cells.append(_cell(f"{_column_name(col_index)}{row_index}", value, styles[col_index - 1], formulas[col_index - 1]))
    height_attr = f' ht="{height}" customHeight="1"' if height else ""
    return f'<row r="{row_index}"{height_attr}>{"".join(cells)}</row>'


def _list_type(row: Mapping) -> str:
    if row.get("is_common"):
        return "Lista común"
    if row.get("is_promo"):
        return "PROMOS"
    if row.get("is_birthday"):
        return "Cumpleaños"
    return "Promotor"


def _sort_key(row: Mapping):
    priority = 3 if row.get("is_common") else (2 if row.get("is_promo") else (1 if row.get("is_birthday") else 0))
    return (
        priority,
        str(row.get("promoter_name") or "").casefold(),
        str(row.get("guest_name") or "").casefold(),
    )


def build_lists_workbook(event: Mapping, rows: Iterable[Mapping]) -> bytes:
    records = [dict(row) for row in rows]
    records.sort(key=_sort_key)
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    event_name = str(event.get("event_name") or "Evento Floki")
    event_date = str(event.get("event_date") or "")

    # Hoja Personas
    people_rows: list[str] = []
    headers = ["Nombre completo", "Lista / promotor", "Tipo de lista", "Estado", "Hora de ingreso", "Fecha de nacimiento", "Detalle", "Búsqueda"]
    people_rows.append(_row(1, headers, [2] * len(headers)))
    for idx, item in enumerate(records, start=2):
        status = "Ingresó" if item.get("checkin_id") else "Pendiente"
        checked_at = str(item.get("checked_in_at") or "")
        if checked_at:
            try:
                checked_at = datetime.fromisoformat(checked_at).strftime("%H:%M")
            except ValueError:
                checked_at = checked_at[-8:-3] if len(checked_at) >= 8 else checked_at
        is_birthday_person = bool(item.get("is_birthday_person"))
        dob = str(item.get("birthday_date_of_birth") or "") if is_birthday_person else ""
        if item.get("is_birthday"):
            detail = "Cumpleañero/a" if is_birthday_person else "Invitado/a de cumpleaños"
        elif item.get("is_promo"):
            detail = "Lista automática PROMOS"
        elif item.get("is_common"):
            detail = "Lista común"
        else:
            detail = "Lista de promotor"
        list_type = _list_type(item)
        search_key = f"{item.get('guest_name','')} {item.get('promoter_name','')} {list_type}".strip()
        people_rows.append(_row(idx, [
            item.get("guest_name", ""), item.get("promoter_name", ""), list_type,
            status, checked_at, dob, detail, search_key,
        ], [1, 1, 1, 3 if status == "Ingresó" else 4, 1, 1, 1, 1]))
    people_last = max(2, len(records) + 1)

    people_cols = "".join([
        '<col min="1" max="1" width="30" customWidth="1"/>',
        '<col min="2" max="2" width="34" customWidth="1"/>',
        '<col min="3" max="3" width="18" customWidth="1"/>',
        '<col min="4" max="4" width="14" customWidth="1"/>',
        '<col min="5" max="5" width="16" customWidth="1"/>',
        '<col min="6" max="6" width="20" customWidth="1"/>',
        '<col min="7" max="7" width="28" customWidth="1"/>',
        '<col min="8" max="8" width="2" hidden="1" customWidth="1"/>',
    ])
    people_sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <cols>{people_cols}</cols>
  <sheetData>{''.join(people_rows)}</sheetData>
  <autoFilter ref="A1:G{people_last}"/>
</worksheet>'''

    # Hoja Buscador de personas. H es auxiliar y queda oculta.
    search_rows: list[str] = []
    search_rows.append(_row(1, ["FLOKI · BUSCADOR DE PERSONAS"], [5], height=32))
    search_rows.append(_row(2, [f"Evento: {event_name}", f"Fecha: {event_date}", f"Generado: {generated}"], [6, 6, 6], height=24))
    search_rows.append(_row(3, ["ESCRIBÍ EL NOMBRE DE LA PERSONA", "", "", "", "", "", ""], [7] * 7, height=28))
    search_rows.append(_row(4, ["", "", "", "", "", "", ""], [8] * 7, height=30))
    search_rows.append(_row(5, ["", "", "", "", "", "", ""], [8] * 7, height=30))
    search_rows.append(_row(6, ["Escribí una parte del nombre. El archivo busca en promotores, cumpleaños, PROMOS y Lista común."], [6], height=24))
    search_rows.append(_row(8, ["Nombre", "Lista / promotor", "Tipo", "Estado", "Ingreso", "Nacimiento", "Detalle", "#"], [2] * 8, height=28))

    max_results = 60
    source_end = max(1001, people_last)
    for output_row in range(9, 9 + max_results):
        ordinal = output_row - 8
        helper_formula = (
            f'IF($A$4="","",IFERROR(AGGREGATE(15,6,(ROW(Personas!$H$2:$H${source_end})-ROW(Personas!$H$2)+1)/'
            f'(ISNUMBER(SEARCH($A$4,Personas!$H$2:$H${source_end}))),{ordinal}),""))'
        )
        formulas = []
        for col in "ABCDEFG":
            formulas.append(f'IF($H{output_row}="","",IFERROR(INDEX(Personas!${col}$2:${col}${source_end},$H{output_row}),""))')
        formulas.append(helper_formula)
        search_rows.append(_row(output_row, ["", "", "", "", "", "", "", ""], [1] * 8, formulas, height=22))

    search_cols = "".join([
        '<col min="1" max="1" width="30" customWidth="1"/>',
        '<col min="2" max="2" width="34" customWidth="1"/>',
        '<col min="3" max="3" width="18" customWidth="1"/>',
        '<col min="4" max="4" width="14" customWidth="1"/>',
        '<col min="5" max="5" width="14" customWidth="1"/>',
        '<col min="6" max="6" width="19" customWidth="1"/>',
        '<col min="7" max="7" width="28" customWidth="1"/>',
        '<col min="8" max="8" width="2" hidden="1" customWidth="1"/>',
    ])
    search_sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="8" topLeftCell="A9" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="22"/>
  <cols>{search_cols}</cols>
  <sheetData>{''.join(search_rows)}</sheetData>
  <mergeCells count="4"><mergeCell ref="A1:G1"/><mergeCell ref="A3:G3"/><mergeCell ref="A4:G5"/><mergeCell ref="A6:G6"/></mergeCells>
</worksheet>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="6">
    <font><sz val="11"/><color rgb="FF241B2F"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><b/><sz val="18"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FF176B43"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FF8A5A00"/><name val="Calibri"/></font>
    <font><b/><sz val="16"/><color rgb="FF3F176D"/><name val="Calibri"/></font>
  </fonts>
  <fills count="9">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFFFFF"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF7C3AED"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF7F3FF"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFDDF8E8"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF1CC"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF5B21B6"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF4B8"/></patternFill></fill>
  </fills>
  <borders count="3">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFD8C7F2"/></left><right style="thin"><color rgb="FFD8C7F2"/></right><top style="thin"><color rgb="FFD8C7F2"/></top><bottom style="thin"><color rgb="FFD8C7F2"/></bottom><diagonal/></border>
    <border><left style="medium"><color rgb="FF7C3AED"/></left><right style="medium"><color rgb="FF7C3AED"/></right><top style="medium"><color rgb="FF7C3AED"/></top><bottom style="medium"><color rgb="FF7C3AED"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="2" borderId="0"/></cellStyleXfs>
  <cellXfs count="9">
    <xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="0" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center"/></xf>
    <xf numFmtId="0" fontId="4" fillId="6" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="7" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="5" fillId="8" borderId="2" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" indent="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Buscador de personas" sheetId="1" r:id="rId1"/>
    <sheet name="Personas" sheetId="2" r:id="rId2"/>
  </sheets>
  <calcPr calcId="191029" calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    files = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "xl/workbook.xml": workbook_xml,
        "xl/_rels/workbook.xml.rels": workbook_rels,
        "xl/worksheets/sheet1.xml": search_sheet,
        "xl/worksheets/sheet2.xml": people_sheet,
        "xl/styles.xml": styles_xml,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()
