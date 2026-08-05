import unittest

from stock_logic import calculate_event_yield


class StockLogicTestCase(unittest.TestCase):
    def test_calculates_only_from_current_event(self):
        used, observed, status = calculate_event_yield(10, 7, 24)
        self.assertEqual(used, 3)
        self.assertEqual(observed, 8)
        self.assertEqual(status, "Calculado")

    def test_waits_for_final_stock(self):
        self.assertEqual(
            calculate_event_yield(10, None, 24),
            (None, None, "Pendiente de stock final"),
        )

    def test_flags_inconsistent_count(self):
        self.assertEqual(
            calculate_event_yield(10, 10, 4),
            (0, None, "Revisar conteo"),
        )

    def test_zero_activity_is_not_a_yield(self):
        self.assertEqual(
            calculate_event_yield(10, 10, 0),
            (0, None, "Sin consumo"),
        )


if __name__ == "__main__":
    unittest.main()
