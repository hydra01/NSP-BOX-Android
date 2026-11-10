"""ZIP -> NUP: safely extract a ZIP, find the content inside, and convert it to a .nup.

The ZIP may contain either
  * an unencrypted .nsp file (or several), or
  * a game folder with exefs + romfs (optionally inside one or more sub-folders).
Nothing is decrypted and no keys are used.
"""
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from helpers import safe_filename, unique_output

MIB = 1024 * 1024


class ConvertError(Exception):
    """A problem the user can understand and fix."""


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise InterruptedError('Cancelled.')


def safe_extract(zip_path, dest, notify=lambda *a: None, cancel=None, free_factor=2.1):
    """Extract zip_path into dest. Rejects unsafe paths, skips symlinks, checks free space."""
    dest = Path(dest).resolve()
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise ConvertError('This is not a valid ZIP file (it may be damaged or incomplete).')
    with zf:
        infos = zf.infolist()
        if any(i.flag_bits & 0x1 for i in infos):
            raise ConvertError('This ZIP is password protected. Remove the password and try again.')
        total = sum(i.file_size for i in infos if not i.is_dir())
        if not total:
            raise ConvertError('This ZIP is empty.')
        free = shutil.disk_usage(dest).free
        need = int(total * free_factor) + 64 * MIB
        if free < need:
            raise ConvertError(
                'Not enough free space. Need about %.1f GiB (extracted files plus the NUP), '
                'but only %.1f GiB is free.' % (need / 1024 ** 3, free / 1024 ** 3))
        done = 0
        for info in infos:
            _check(cancel)
            parts = PurePosixPath(info.filename.replace('\\', '/')).parts
            if (info.filename.startswith(('/', '\\')) or '..' in parts
                    or (parts and len(parts[0]) > 1 and parts[0][1] == ':')):
                raise ConvertError('This ZIP contains an unsafe file path, so it was not extracted.')
            if stat.S_ISLNK(info.external_attr >> 16):
                continue                                   # never create links from a ZIP
            target = dest.joinpath(*parts)
            if dest not in target.resolve().parents and target.resolve() != dest:
                raise ConvertError('This ZIP contains an unsafe file path, so it was not extracted.')
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, 'xb') as out:
                while True:
                    chunk = src.read(4 * MIB)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    notify('Extracting ZIP', 100 * done / total)
    return total


def find_nsps(root):
    return sorted(p for p in Path(root).rglob('*') if p.is_file() and p.suffix.lower() == '.nsp')


def game_root(root):
    """Closest common folder above every exefs+romfs pair found anywhere under root (or None)."""
    import os
    parents = []
    for d in Path(root).rglob('*'):
        if d.is_dir() and d.name.lower() == 'exefs':
            if any(s.is_dir() and s.name.lower() == 'romfs' for s in d.parent.iterdir()):
                parents.append(str(d.parent))
    if not parents:
        return None
    return Path(os.path.commonpath(parents))


def convert_zip(zip_path, out_dir, level=3, large_raw=True, verify=True,
                notify=lambda *a: None, cancel=None):
    """Extract and convert. Returns {'outputs': [paths], 'size': bytes, 'kind': 'nsp'|'folder'}."""
    import nup_tools as tools

    zip_path, out_dir = Path(zip_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='.nspbox-work-', dir=out_dir))
    outputs = []

    def stage(lo, hi):
        return lambda label, pct: notify(label, lo + (hi - lo) * max(0, min(pct, 100)) / 100)

    try:
        extracted = work / 'content'
        extracted.mkdir()
        safe_extract(zip_path, extracted, stage(0, 35), cancel)
        _check(cancel)
        notify('Looking for content', 35)

        stem = safe_filename(zip_path.stem)
        nsps = find_nsps(extracted)
        common = dict(level=level, large_raw=large_raw, verify=verify, cancel=cancel)
        if nsps:
            kind = 'nsp'
            for i, nsp in enumerate(nsps):
                name = safe_filename(nsp.stem) if len(nsps) > 1 else stem
                output = unique_output(out_dir, name, ext='.nup')
                lo = 35 + 65 * i / len(nsps)
                hi = 35 + 65 * (i + 1) / len(nsps)
                tools.nsp_to_nup(nsp, output, notify=stage(lo, hi), **common)
                outputs.append(output)
        else:
            kind = 'folder'
            output = unique_output(out_dir, stem, ext='.nup')
            candidates = [extracted]
            nested = game_root(extracted)
            if nested is not None and nested != extracted:
                candidates.append(nested)
            last_error = None
            for folder in candidates:
                try:
                    tools.pack_folder(folder, output, latest_snapshot=True,
                                      notify=stage(35, 100), **common)
                    break
                except ValueError as e:
                    last_error = e
            else:
                raise ConvertError(
                    "Couldn't find an NSP file or a game folder (exefs + romfs) in this ZIP. (%s)" % last_error)
            outputs.append(output)
        notify('Done', 100)
        return {'outputs': [str(p) for p in outputs], 'kind': kind,
                'size': sum(p.stat().st_size for p in outputs)}
    except BaseException:
        for p in outputs:                                  # keep nothing half-finished
            if isinstance(p, Path) and p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
