import tempfile, unittest
from pathlib import Path
import helpers

class HelperTests(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(helpers.safe_filename('Game: The "Best"? / Ever.'), 'Game The Best  Ever'.replace('  ', ' '))
        self.assertEqual(helpers.safe_filename('???'), 'Game')

    def test_unique_output(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertEqual(helpers.unique_output(d, 'G').name, 'G.nsp')
            (d / 'G.nsp').write_bytes(b'x')
            self.assertEqual(helpers.unique_output(d, 'G').name, 'G (2).nsp')
            (d / 'G (2)').mkdir()
            self.assertEqual(helpers.unique_output(d, 'G', True).name, 'G (3).nsp')

    def test_list_directory(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / 'b').mkdir(); (d / 'A').mkdir(); (d / '.hid').mkdir()
            (d / 'x.png').write_bytes(b''); (d / 'y.txt').write_bytes(b'')
            self.assertEqual(helpers.list_directory(d, True), (['A', 'b'], ['x.png']))
            self.assertEqual(helpers.list_directory(d / 'nope'), (None, None))

if __name__ == '__main__':
    unittest.main()
