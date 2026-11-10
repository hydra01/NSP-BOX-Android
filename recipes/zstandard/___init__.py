"""python-for-android recipe for python-zstandard (C backend only, vendored zstd sources).

python-for-android has no zstandard recipe, so this one lives in the app's own recipes folder.
The 0.25 sdist assumes a modern build machine, so its sources are patched before building:
  * setup.py, setup_zstd.py and make_cffi.py import the 'packaging' module, which the host Python
    used by python-for-android does not have. It is only used for the optional cffi version check
    and to spot musl-libc Linux (irrelevant on Android), so safe fallbacks are used instead;
  * pyproject.toml is removed, because its SPDX license string needs a very new setuptools and
    setup.py already supplies all metadata.
The optional cffi backend is switched off (the C backend is what gets imported).
"""
from pathlib import Path

from pythonforandroid.recipe import CompiledComponentsPythonRecipe

VERSION_IMPORT = 'from packaging.version import Version'
VERSION_FALLBACK = (
    'try:\n    from packaging.version import Version\n'
    'except ImportError:\n'
    '    try:\n        from setuptools._vendor.packaging.version import Version\n'
    '    except ImportError:\n        Version = None')
TAGS_IMPORT = 'import packaging.tags'
TAGS_FALLBACK = (
    'try:\n    import packaging.tags\n'
    'except ImportError:\n'
    '    import types\n'
    '    packaging = types.SimpleNamespace(tags=types.SimpleNamespace(platform_tags=lambda: []))')


def patch_sources(build_dir):
    """Apply the source fixes described above (safe to run more than once)."""
    build_dir = Path(build_dir)
    for name, old, new in (('setup.py', VERSION_IMPORT, VERSION_FALLBACK),
                           ('setup_zstd.py', TAGS_IMPORT, TAGS_FALLBACK),
                           ('make_cffi.py', TAGS_IMPORT, TAGS_FALLBACK)):
        path = build_dir / name
        if path.exists():
            text = path.read_text()
            if old in text and new not in text:
                path.write_text(text.replace(old, new))
    pyproject = build_dir / 'pyproject.toml'
    if pyproject.exists():
        pyproject.unlink()


class ZstandardRecipe(CompiledComponentsPythonRecipe):
    name = 'zstandard'
    version = '0.25.0'
    url = 'https://files.pythonhosted.org/packages/source/z/zstandard/zstandard-{version}.tar.gz'
    site_packages_name = 'zstandard'
    depends = ['setuptools']
    call_hostpython_via_targetpython = False
    setup_extra_args = ['--no-cffi-backend']

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        patch_sources(self.get_build_dir(arch.arch))


recipe = ZstandardRecipe()
