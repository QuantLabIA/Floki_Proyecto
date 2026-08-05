import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from master_list_parser import parse_master_file, parse_master_lines


class MemoryUpload(io.BytesIO):
    def __init__(self, content: bytes, filename: str):
        super().__init__(content)
        self.filename = filename


class MasterListParserTestCase(unittest.TestCase):
    def test_whatsapp_wps_format_assigns_promoters_and_common(self):
        sample = """[30/7/26, 12:43:26\u202fp.\u202fm.] Pablo: CINTIA DÍAZ

Pilar tutti
Ingrid becerra
[30/7/26, 1:29:04 p. m.] Pablo: JAZ BARROSO

Jazmín peralta
Luz avila
[30/7/26, 2:36:27 p. m.] Pablo: Micaela Suárez
Nicolás Becerra
"""
        groups, metadata = parse_master_lines(sample.splitlines())
        self.assertTrue(metadata["whatsapp_format"])
        self.assertEqual(metadata["promoter_count"], 2)
        self.assertEqual(metadata["common_count"], 2)
        by_name = {group["promoter_name"]: group for group in groups}
        self.assertEqual(
            by_name["CINTIA DÍAZ"]["guests"],
            [("Pilar tutti", "pilar tutti"), ("Ingrid becerra", "ingrid becerra")],
        )
        self.assertEqual(
            by_name[None]["guests"],
            [("Micaela Suárez", "micaela suarez"), ("Nicolás Becerra", "nicolas becerra")],
        )

    def test_duplicate_inside_same_promoter_is_removed(self):
        sample = """[30/7/26, 12:43:26 p. m.] Pablo: CINTIA DÍAZ
Ana Gómez
ANA GOMEZ
"""
        upload = MemoryUpload(sample.encode("utf-8"), "lista.txt")
        filename, groups, metadata = parse_master_file(upload)
        self.assertEqual(filename, "lista.txt")
        self.assertEqual(metadata["guest_count"], 1)
        self.assertEqual(groups[0]["guests"], [("Ana Gómez", "ana gomez")])

    def test_promo_and_promos_headers_create_special_promo_list(self):
        sample = """[30/7/26, 12:43:26 p. m.] Pablo: PROMOS
Ana Gómez
Juan Pérez
[30/7/26, 1:10:00 p. m.] Pablo: PROMO
Lucía Díaz
"""
        groups, metadata = parse_master_lines(sample.splitlines())
        self.assertEqual(metadata["promoter_count"], 0)
        self.assertEqual(metadata["promo_count"], 3)
        self.assertEqual(metadata["common_count"], 0)
        self.assertEqual(groups[0]["promoter_name"], "PROMOS")
        self.assertTrue(groups[0]["is_promo"])
        self.assertFalse(groups[0]["is_common"])
        self.assertEqual([guest[0] for guest in groups[0]["guests"]], ["Ana Gómez", "Juan Pérez", "Lucía Díaz"])

    def test_message_without_uppercase_header_is_common(self):
        sample = """[30/7/26, 12:43:26 p. m.] Pablo: Ana Gómez
Juan Pérez
"""
        groups, metadata = parse_master_lines(sample.splitlines())
        self.assertEqual(metadata["promoter_count"], 0)
        self.assertEqual(metadata["common_count"], 2)
        self.assertIsNone(groups[0]["promoter_name"])

    def test_pdf_master_file_is_supported(self):
        from reportlab.pdfgen import canvas
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(60, 780, "CINTIA DÍAZ")
        pdf.drawString(60, 760, "Pilar Tutti")
        pdf.drawString(60, 740, "Ingrid Becerra")
        pdf.save()
        upload = MemoryUpload(buffer.getvalue(), "listas.pdf")
        _filename, groups, metadata = parse_master_file(upload)
        self.assertEqual(metadata["promoter_count"], 1)
        self.assertEqual(metadata["guest_count"], 2)
        self.assertEqual(groups[0]["promoter_name"], "CINTIA DÍAZ")


if __name__ == "__main__":
    unittest.main()
