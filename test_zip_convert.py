import os, struct, tempfile, threading, unittest, zipfile
from pathlib import Path
import zip_convert as zc

def make_game(root, tid=0x0400111122220000):
    (root / 'exefs').mkdir(parents=True); (root / 'romfs' / 'd').mkdir(parents=True)
    npdm = bytearray(0x100); npdm[:4] = b'META'; struct.pack_into('<II', npdm, 0x70, 0x80, 0x80)
    npdm[0x80:0x84] = b'ACI0'; struct.pack_into('<Q', npdm, 0x90, tid)
    (root / 'exefs/main.npdm').write_bytes(npdm); (root / 'exefs/main').write_bytes(b'NSO0' + bytes(256))
    (root / 'romfs/d/a.bin').write_bytes(bytes(range(256)) * 2000 + os.urandom(50000))

def zip_dir(src, zpath, prefix=''):
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(Path(src).rglob('*')):
            if p.is_file():
                z.write(p, prefix + str(p.relative_to(src)))

class ZipConvertTests(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp()); self.out = self.t / 'out'

    def _game_zip(self, prefix=''):
        g = self.t / 'game'; make_game(g); z = self.t / 'My Game.zip'; zip_dir(g, z, prefix); return z

    def test_game_folder_at_zip_root(self):
        r = zc.convert_zip(self._game_zip(), self.out)
        self.assertEqual(r['kind'], 'folder'); self.assertEqual(Path(r['outputs'][0]).name, 'My Game.nup')
        self.assertTrue(Path(r['outputs'][0]).stat().st_size > 0)
        self.assertEqual([p.name for p in self.out.iterdir()], ['My Game.nup'])   # temp dir cleaned up

    def test_game_folder_inside_subfolders(self):
        r = zc.convert_zip(self._game_zip('Some Game [0400111122220000]/extracted/'), self.out)
        self.assertEqual(r['kind'], 'folder')

    def test_nsp_inside_zip(self):
        import engine
        g = self.t / 'game'; make_game(g)
        snap = engine.find_snapshots(str(g))[0][0]
        nsp = self.t / 'x' / 'Inner.nsp'; nsp.parent.mkdir()
        engine.build(snap, nsp, 'T', 'v1', None, True)
        z = self.t / 'wrapped.zip'; zip_dir(nsp.parent, z)
        r = zc.convert_zip(z, self.out)
        self.assertEqual(r['kind'], 'nsp'); self.assertEqual(Path(r['outputs'][0]).name, 'wrapped.nup')

    def test_unique_name_when_output_exists(self):
        z = self._game_zip(); zc.convert_zip(z, self.out); r = zc.convert_zip(z, self.out)
        self.assertEqual(Path(r['outputs'][0]).name, 'My Game (2).nup')

    def test_rejects_path_traversal(self):
        z = self.t / 'evil.zip'
        with zipfile.ZipFile(z, 'w') as zf: zf.writestr('../escape.txt', 'x'); zf.writestr('a.txt', 'y')
        with self.assertRaises(zc.ConvertError): zc.convert_zip(z, self.out)
        self.assertFalse((self.t / 'escape.txt').exists()); self.assertFalse((self.out / 'escape.txt').exists())

    def test_not_a_zip_and_empty_and_unrelated(self):
        bad = self.t / 'bad.zip'; bad.write_bytes(b'not a zip')
        with self.assertRaises(zc.ConvertError): zc.convert_zip(bad, self.out)
        z = self.t / 'docs.zip'
        with zipfile.ZipFile(z, 'w') as zf: zf.writestr('readme.txt', 'hello')
        with self.assertRaises(zc.ConvertError) as cm: zc.convert_zip(z, self.out)
        self.assertIn("Couldn't find", str(cm.exception))
        self.assertEqual([p.name for p in self.out.iterdir()], [])                 # nothing left behind

    def test_cancel_cleans_up(self):
        ev = threading.Event(); ev.set()
        with self.assertRaises(InterruptedError): zc.convert_zip(self._game_zip(), self.out, cancel=ev)
        self.assertEqual([p.name for p in self.out.iterdir()], [])

    def test_not_enough_space_message(self):
        with self.assertRaises(zc.ConvertError) as cm:
            zc.safe_extract(self._game_zip(), self.t / 'dest' if (self.t / 'dest').mkdir() is None else None,
                            free_factor=10 ** 12)
        self.assertIn('free space', str(cm.exception))

if __name__ == '__main__':
    unittest.main()
