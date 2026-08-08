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


def _package_xlsx(data, widths, header_row, title_merge_end, freeze_row=None, autofilter_end=None, note_rows=None):
    note_rows = set(note_rows or [])
    sheet_rows = []
    for row_index, row in enumerate(data, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            style = 1 if row_index == 1 else 2 if row_index == header_row else 0
            if row_index in note_rows:
                style = 4 if col_index == 1 else 0
            cells.append(_cell(f"{_column_name(col_index)}{row_index}", value, style))
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    cols = "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths, 1))
    pane = ""
    if freeze_row:
        pane = f'<pane ySplit="{freeze_row}" topLeftCell="A{freeze_row + 1}" activePane="bottomLeft" state="frozen"/>'
    autofilter = f'<autoFilter ref="A{header_row}:{_column_name(autofilter_end[0])}{autofilter_end[1]}"/>' if autofilter_end else ""
    merges = f'<mergeCells count="1"><mergeCell ref="A1:{_column_name(title_merge_end)}1"/></mergeCells>'
    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0">{pane}</sheetView></sheetViews><cols>{cols}</cols><sheetData>{''.join(sheet_rows)}</sheetData>{autofilter}{merges}</worksheet>'''
    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="4"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="18"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FF4C1D73"/><name val="Calibri"/></font></fonts><fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF7C3AED"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFA855F7"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF3E8FF"/></patternFill></fill></fills><borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFE5D7F2"/></left><right style="thin"><color rgb="FFE5D7F2"/></right><top style="thin"><color rgb="FFE5D7F2"/></top><bottom style="thin"><color rgb="FFE5D7F2"/></bottom><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center"/></xf><xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"/><xf numFmtId="0" fontId="3" fillId="4" borderId="0" xfId="0"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    files = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Stock del evento" sheetId="1" r:id="rId1"/></sheets></workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''',
        "xl/worksheets/sheet1.xml": sheet_xml,
        "xl/styles.xml": styles_xml,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def build_stock_template_workbook(event_name, event_date, rows):
    """Planilla simple para descargar, completar y volver a importar."""
    headers = ["Bebida", "Unidad de stock", "Cantidad inicial", "Cantidad final"]
    data = [
        ["FLOKI · PLANILLA DE CONTEO DE STOCK"],
        ["Evento", event_name],
        ["Fecha", event_date],
        ["Completá las cantidades y volvé a cargar este mismo archivo en Carga inteligente de stock."],
        headers,
    ]
    for row in rows:
        data.append([
            row["beverage_name"],
            row["stock_unit"],
            float(row["initial_quantity"] or 0),
            "" if row["final_quantity"] is None else float(row["final_quantity"]),
        ])
    last_row = len(data)
    return _package_xlsx(
        data,
        widths=[34, 20, 20, 20],
        header_row=5,
        title_merge_end=4,
        freeze_row=5,
        autofilter_end=(4, last_row),
        note_rows={4},
    )


def build_stock_workbook(event_name, event_date, rows):
    headers = [
        "Bebida", "Cantidad inicial", "Vendido", "Rendimiento aprox.",
        "Consumo aprox.", "Cantidad final", "Stock utilizado", "Rendimiento real",
    ]
    data = [
        ["FLOKI · RESUMEN DE STOCK DEL EVENTO"],
        ["Evento", event_name],
        ["Fecha", event_date],
        [],
        headers,
    ]
    for row in rows:
        approx_yield = float(row.get("approx_yield") or 0)
        approx_consumed = row.get("approx_consumed")
        data.append([
            row["beverage_name"],
            float(row["initial_quantity"] or 0),
            int(row["sold_quantity"] or 0),
            "" if approx_yield <= 0 else approx_yield,
            "" if approx_consumed is None else float(approx_consumed),
            "" if row["final_quantity"] is None else float(row["final_quantity"]),
            "" if row.get("consumed_stock") is None else float(row["consumed_stock"]),
            "" if row.get("observed_yield") is None else float(row["observed_yield"]),
        ])
    data.extend([
        [],
        ["Nota", "Rendimiento aprox. es solo una referencia configurable. El rendimiento real usa stock inicial, final y unidades vendidas."],
        ["Generado", datetime.now().strftime("%d/%m/%Y %H:%M")],
    ])
    last_data_row = 5 + len(rows)
    return _package_xlsx(
        data,
        widths=[34, 18, 16, 20, 18, 18, 18, 18],
        header_row=5,
        title_merge_end=8,
        freeze_row=5,
        autofilter_end=(8, last_data_row),
        note_rows={last_data_row + 2},
    )
