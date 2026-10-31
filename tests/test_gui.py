import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from shodan_export import ShodanError
from shodan_gui import run_export, validate


class GuiTests(unittest.TestCase):
    def test_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / 'report.xlsx')
            args = validate(' key ', '192.0.2.3/24', '2', output)
            self.assertEqual(args[:3], ('key', '192.0.2.0/24', 2))
            for key, network, pages, target in [('', '192.0.2.1', '1', output),
                    ('key', 'bad', '1', output), ('key', '192.0.2.1', '0', output),
                    ('key', '192.0.2.1', 'x', output), ('key', '192.0.2.1', '1', ''),
                    ('key', '192.0.2.1', '1', output + '.csv')]:
                with self.assertRaises(ValueError):
                    validate(key, network, pages, target)
            Path(output).touch()
            with self.assertRaises(ValueError):
                validate('key', '192.0.2.1', '1', output)

    @patch('shodan_gui.collect')
    def test_worker_exports_and_signals_partial(self, collect):
        collect.return_value = ([{'ip_str': '192.0.2.1', 'port': 443}], 200)
        events = queue.Queue()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.xlsx'
            run_export(events, 'key', '192.0.2.0/24', 1, output)
            self.assertEqual(events.get()[0], 'progress')
            kind, message = events.get()
            self.assertEqual(kind, 'done')
            self.assertIn('일부 결과', message)
            book = load_workbook(output)
            self.assertEqual(book['Services']['A2'].value, '192.0.2.1')
            book.close()

    @patch('shodan_gui.collect')
    def test_worker_reports_error_without_key(self, collect):
        for exception, expected in [(ShodanError('권한 부족'), '권한 부족'),
                                    (RuntimeError('secret-key'), '처리 중 오류')]:
            collect.side_effect = exception
            events = queue.Queue()
            run_export(events, 'secret-key', '192.0.2.0/24', 1, 'unused.xlsx')
            kind, message = events.get()
            self.assertEqual(kind, 'error')
            self.assertIn(expected, message)
            self.assertNotIn('secret-key', message)
