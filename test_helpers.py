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

class NupHelperTests(unittest.TestCase):
    def test_nup_output_names(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p = helpers.nup_output_path('NSP to NUP', '/x/My Game.nsp', d)
            self.assertEqual(p.name, 'My Game.nup')
            p.write_bytes(b'x')
            self.assertEqual(helpers.nup_output_path('NSP to NUP', '/x/My Game.nsp', d).name, 'My Game (2).nup')
            self.assertEqual(helpers.nup_output_path('NUP to NSP', '/x/A.nup', d).name, 'A.nsp')
            self.assertEqual(helpers.nup_output_path('NUP to folder', '/x/A.nup', d).name, 'A')
            self.assertEqual(helpers.nup_output_path('Game folder to NUP', '/x/Some Game [0400]', d).name,
                             'Some Game [0400].nup')
            self.assertIsNone(helpers.nup_output_path('Inspect / verify NUP', '/x/A.nup', d))

    def test_list_directory_extensions(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for n in ('a.nsp', 'b.nup', 'c.png'):
                (d / n).write_bytes(b'')
            self.assertEqual(helpers.list_directory(d, True, ('.nup',))[1], ['b.nup'])
            self.assertEqual(helpers.list_directory(d, True, ('.nsp', '.nup'))[1], ['a.nsp', 'b.nup'])

    def test_format_result(self):
        text = helpers.format_nup_result('NSP to NUP', {'output': '/o.nup', 'size': 2048, 'source_size': 4096,
                                                         'packages': 1, 'verified': True})
        self.assertIn('Size: 2.0 KiB', text)
        self.assertIn('Verified: yes', text)

if __name__ == '__main__':
    unittest.main()
