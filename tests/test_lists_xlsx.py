import io
import unittest
import zipfile

from lists_xlsx import build_lists_workbook


class ListsWorkbookTestCase(unittest.TestCase):
    def test_contains_search_sheet_and_all_list_types(self):
        rows = [
            {"guest_name": "Ana Gómez", "promoter_name": "CINTIA DÍAZ", "is_common": 0, "is_promo": 0, "is_birthday": 0, "checkin_id": None, "checked_in_at": None},
            {"guest_name": "Sofía Martínez", "promoter_name": "CUMPLEAÑOS - Sofía Martínez", "is_common": 0, "is_promo": 0, "is_birthday": 1, "checkin_id": 1, "checked_in_at": "2026-07-31 01:20:00", "birthday_person_name": "Sofía Martínez", "birthday_date_of_birth": "2000-07-31"},
            {"guest_name": "Juan Pérez", "promoter_name": "PROMOS", "is_common": 0, "is_promo": 1, "is_birthday": 0, "checkin_id": None, "checked_in_at": None},
            {"guest_name": "Lucía Díaz", "promoter_name": "LISTA COMÚN", "is_common": 1, "is_promo": 0, "is_birthday": 0, "checkin_id": None, "checked_in_at": None},
        ]
        payload = build_lists_workbook({"event_name": "Noche Floki", "event_date": "2026-07-31"}, rows)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
            sheets = "".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
        self.assertIn("Buscador de personas", workbook_xml)
        self.assertIn("Personas", workbook_xml)
        self.assertIn("AGGREGATE", sheets)
        self.assertIn("Sofía Martínez", sheets)
        self.assertIn("LISTA COMÚN", sheets)


if __name__ == "__main__":
    unittest.main()
