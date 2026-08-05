import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.pdfgen import canvas
from stock_import_parser import parse_stock_file


class MemoryUpload(io.BytesIO):
    def __init__(self, content: bytes, filename: str):
        super().__init__(content)
        self.filename = filename


BRANDS = ("Sin marca", "Quilmes", "Branca", "Speed", "Chandon")


class StockImportParserTestCase(unittest.TestCase):
    def test_pdf_extracts_and_classifies_products(self):
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(60, 780, "Cerveza Quilmes lata 473 ml 48")
        pdf.drawString(60, 760, "Fernet Branca botella 8")
        pdf.drawString(60, 740, "Speed lata 24")
        pdf.save()
        upload = MemoryUpload(buffer.getvalue(), "stock.pdf")
        filename, items = parse_stock_file(upload, BRANDS)
        self.assertEqual(filename, "stock.pdf")
        self.assertEqual(len(items), 3)
        by_raw = {item["raw_name"]: item for item in items}
        beer = by_raw["Cerveza Quilmes lata 473 ml"]
        self.assertEqual(beer["quantity"], 48)
        self.assertEqual(beer["beverage_type"], "Cerveza")
        self.assertEqual(beer["brand"], "Quilmes")
        self.assertEqual(beer["presentation"], "lata 473 ml")

    def test_xlsx_extracts_columns(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Bebida", "Cantidad inicial"])
        ws.append(["Champagne Chandon botella 750 ml", 6])
        ws.append(["Speed lata", 18])
        data = io.BytesIO()
        wb.save(data)
        upload = MemoryUpload(data.getvalue(), "stock.xlsx")
        _filename, items = parse_stock_file(upload, BRANDS)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["quantity"], 6)
        self.assertEqual(items[0]["beverage_type"], "Espumante")
        self.assertEqual(items[0]["brand"], "Chandon")


if __name__ == "__main__":
    unittest.main()
