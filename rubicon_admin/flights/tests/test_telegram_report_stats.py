from django.test import SimpleTestCase

from flights.utils.telegram_report_stats import (
    is_report_defeated,
    is_report_not_defeated,
)


class TelegramReportResultClassificationTests(SimpleTestCase):
    def test_porazheno(self):
        self.assertTrue(is_report_defeated('поражено'))
        self.assertTrue(is_report_defeated('Поражен'))
        self.assertFalse(is_report_not_defeated('поражено'))

    def test_not_defeated(self):
        self.assertTrue(is_report_not_defeated('не поражено'))
        self.assertTrue(is_report_not_defeated('Не  поражено'))
        self.assertTrue(is_report_not_defeated('непоражено'))
        self.assertFalse(is_report_defeated('не поражено'))
        self.assertFalse(is_report_defeated('не\u00a0поражено'))

    def test_unichtozheno(self):
        self.assertTrue(is_report_defeated('уничтожено'))

    def test_uspeh_not_defeated_kpi(self):
        self.assertFalse(is_report_defeated('успешно'))
        self.assertFalse(is_report_not_defeated('успешно'))
