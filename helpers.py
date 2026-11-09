"""UI-independent helpers for the Android front end (testable without Kivy)."""
from pathlib import Path
import os, re

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff')


def safe_filename(title: str) -> str:
    """Turn a game title into a filename that is safe on Android/FAT/exFAT storage."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title).strip().rstrip('.')
    name = re.sub(r'\s+', ' ', name)
    return name[:120] or 'Game'


def default_version(snapshot) -> str:
    """Mirror the desktop app: use the NACP display version if present."""
    if snapshot.nacp:
        raw = snapshot.nacp.read_bytes()[0x3060:0x3070]
        text = raw.split(b'\0')[0].decode('utf-8', 'replace')
        if text:
            return text
    return f'dump-{snapshot.version}' if snapshot.version else 'Snapshot'


def default_output_dir() -> str:
    """Shared storage root on Android, home folder elsewhere."""
    for candidate in ('/storage/emulated/0', os.path.expanduser('~')):
        if os.path.isdir(candidate):
            return str(Path(candidate) / 'NSPBox')
    return str(Path.cwd() / 'NSPBox')


def list_directory(path, want_files=False):
    """Return (folders, files) sorted case-insensitively; never raises on bad entries."""
    folders, files = [], []
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.name.startswith('.'):
                        continue
                    if entry.is_dir():
                        folders.append(entry.name)
                    elif want_files and entry.name.lower().endswith(IMAGE_EXTS):
                        files.append(entry.name)
                except OSError:
                    continue
    except OSError:
        return None, None
    folders.sort(key=str.lower)
    files.sort(key=str.lower)
    return folders, files


def human_size(n: int) -> str:
    for unit in ('B', 'KiB', 'MiB', 'GiB'):
        if n < 1024 or unit == 'GiB':
            return f'{n:.1f} {unit}' if unit != 'B' else f'{n} B'
        n /= 1024


def unique_output(out_dir, stem, package_folder=False):
    """Pick an output path that does not exist yet: 'Game.nsp', 'Game (2).nsp', ..."""
    out_dir = Path(out_dir)
    for n in range(1, 1000):
        name = stem if n == 1 else f'{stem} ({n})'
        taken = (out_dir / (name + '.nsp')).exists()
        if package_folder:
            taken = taken or (out_dir / name).exists()
        if not taken:
            return out_dir / (name + '.nsp')
    raise ValueError('Too many existing outputs with this name. Choose another folder.')
