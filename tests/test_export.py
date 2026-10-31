import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from shodan_export import ShodanError, collect, export


class ExportTests(unittest.TestCase):
    @patch('shodan_export.time.sleep')
    def test_pagination_and_workbook(self, sleep):
        def fetch(key, network, page):
            return {'total': 2, 'matches': [
                {'ip_str': '192.0.2.1', 'port': 80 if page == 1 else 443,
                 'data': '=HYPERLINK("https://example.com")\x00',
                 'location': {'country_name': '대한민국'}, 'vulns': {'CVE-example': {}}}
            ]}
        rows, total = collect('fake', '192.0.2.0/24', 2, fetch)
        self.assertEqual(len(rows), 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.xlsx'
            export(rows, total, '192.0.2.0/24', path)
            book = load_workbook(path)
            self.assertEqual(book['Services'].max_row, 3)
            self.assertEqual(book['Services']['P2'].data_type, 's')
            self.assertNotIn('\x00', book['Services']['P2'].value)
            self.assertEqual(book['Summary']['B4'].value, 1)
            self.assertEqual(book['Summary']['B5'].value, 'Yes')
            book.close()
            with self.assertRaises(FileExistsError):
                export(rows, total, '192.0.2.0/24', path)

    def test_limit_and_empty_results(self):
        rows, total = collect('fake', '192.0.2.0/24', 1,
                              lambda *args: {'total': 200, 'matches': [{'ip_str': '192.0.2.1'}]})
        self.assertLess(len(rows), total)
        rows, total = collect('fake', '192.0.2.0/24', 1,
                              lambda *args: {'total': 0, 'matches': []})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'empty.xlsx'
            export(rows, total, '192.0.2.0/24', path)
            book = load_workbook(path)
            self.assertEqual(book['Services'].max_row, 1)
            self.assertEqual(book['Summary']['B5'].value, 'Yes')
            book.close()

    def test_invalid_api_responses(self):
        for result in [{'error': 'invalid key'}, {},
                       {'total': 1, 'matches': [{'ip_str': '198.51.100.1'}]}]:
            with self.subTest(result=result), self.assertRaises(ShodanError):
                collect('fake', '192.0.2.0/24', 1, lambda *args: result)


if __name__ == '__main__':
    unittest.main()
