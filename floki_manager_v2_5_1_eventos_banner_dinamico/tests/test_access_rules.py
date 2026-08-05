import unittest
from datetime import datetime

from access_rules import birthday_discount_available, free_entry_available


class AccessRulesTestCase(unittest.TestCase):
    def test_common_list_is_available_before_three_thirty(self):
        self.assertTrue(free_entry_available(datetime(2026, 7, 31, 3, 29)))

    def test_common_list_expires_at_exactly_three_thirty(self):
        self.assertFalse(free_entry_available(datetime(2026, 7, 31, 3, 30)))

    def test_common_list_is_available_during_evening(self):
        self.assertTrue(free_entry_available(datetime(2026, 7, 30, 23, 30)))

    def test_common_list_stays_closed_during_morning_after_event(self):
        self.assertFalse(free_entry_available(datetime(2026, 7, 31, 8, 0)))

    def test_birthday_discount_is_available_before_three(self):
        self.assertTrue(birthday_discount_available(datetime(2026, 7, 31, 2, 59)))

    def test_birthday_discount_expires_at_three(self):
        self.assertFalse(birthday_discount_available(datetime(2026, 7, 31, 3, 0)))


if __name__ == '__main__':
    unittest.main()
