import io
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape


def _column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(ref, value, style=0):
    style_attr = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(str(value))}</t></is></c>'


def build_stock_workbook(event_name, event_date, rows):
    headers = [
        "Bebida", "Unidad de stock", "Unidad de venta", "Cantidad inicial",
        "Venta normal", "Venta especial", "Beneficio RRPP", "Total vendido",
        "Cantidad final", "Stock utilizado", "Rendimiento real",
    ]
    data = [
        ["FLOKI · STOCK Y RENDIMIENTO DEL EVENTO"],
        ["Evento", event_name],
        ["Fecha", event_date],
        [],
        headers,
    ]
    for row in rows:
        data.append([
            row["beverage_name"], row["stock_unit"], row["sale_unit"],
            float(row["initial_quantity"] or 0), int(row["regular_quantity"] or 0),
            int(row["special_quantity"] or 0), int(row["benefit_quantity"] or 0),
            int(row["sold_quantity"] or 0),
            "" if row["final_quantity"] is None else float(row["final_quantity"]),
            "" if row.get("consumed_stock") is None else float(row["consumed_stock"]),
            "" if row.get("observed_yield") is None else float(row["observed_yield"]),
        ])

    last_data_row = max(5, len(data))
    data += [
        [], ["GUÍA DE COLUMNAS"],
        ["Bebida", "Solo aparecen productos creados y activos en el sector Bebidas."],
        ["Unidad de stock", "Forma física de conteo: botella, lata, caja, etc."],
        ["Unidad de venta", "Presentación entregada: vaso, lata, botella, etc."],
        ["Cantidad inicial", "Existencia física al comenzar el evento."],
        ["Venta normal", "Unidades registradas con el botón habitual."],
        ["Venta especial", "Unidades con precio especial y comentario."],
        ["Beneficio RRPP", "Unidades entregadas sin cobro mediante voucher."],
        ["Total vendido", "Suma de normal, especial y beneficio."],
        ["Cantidad final", "Conteo físico manual al terminar."],
        ["Stock utilizado", "Cantidad inicial menos cantidad final."],
        ["Rendimiento real", "Total vendido dividido por stock utilizado. No genera promedio histórico."],
        [], ["Generado", datetime.now().strftime("%d/%m/%Y %H:%M")],
    ]

    guide_title_row = last_data_row + 2
    sheet_rows = []
    for row_index, row in enumerate(data, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            style = 1 if row_index == 1 else 2 if row_index == 5 else 0
            if row_index in {2, 3, len(data)} and col_index == 1: style = 3
            if row_index == guide_title_row: style = 4
            elif guide_title_row < row_index < len(data) and col_index == 1: style = 5
            cells.append(_cell(f"{_column_name(col_index)}{row_index}", value, style))
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    widths = [28, 18, 18, 17, 15, 15, 17, 15, 17, 17, 18]
    cols = "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths, 1))
    end_col = _column_name(len(headers))
    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="5" topLeftCell="A6" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>{''.join(sheet_rows)}</sheetData><autoFilter ref="A5:{end_col}{last_data_row}"/><mergeCells count="2"><mergeCell ref="A1:{end_col}1"/><mergeCell ref="A{guide_title_row}:{end_col}{guide_title_row}"/></mergeCells></worksheet>'''
    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="4"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="18"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="12"/><color rgb="FF111111"/><name val="Calibri"/></font></fonts><fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF111814"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF168A4A"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8F5ED"/></patternFill></fill></fills><borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFD8E1DC"/></left><right style="thin"><color rgb="FFD8E1DC"/></right><top style="thin"><color rgb="FFD8E1DC"/></top><bottom style="thin"><color rgb="FFD8E1DC"/></bottom><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center"/></xf><xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0"/><xf numFmtId="0" fontId="3" fillId="4" borderId="0" xfId="0"/><xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    files = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Stock del evento" sheetId="1" r:id="rId1"/></sheets></workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''',
        "xl/worksheets/sheet1.xml": sheet_xml, "xl/styles.xml": styles_xml,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items(): archive.writestr(name, content)
    return output.getvalue()
