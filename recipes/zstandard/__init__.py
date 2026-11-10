"""python-for-android recipe for python-zstandard (C backend only, vendored zstd sources).

python-for-android has no zstandard recipe, so this one lives in the app's own recipes folder.
Two small fixes let the 0.25 sdist build with the older host toolchain:
  * setup.py imports the 'packaging' module, which the host Python may not have, so it falls
    back to the copy vendored inside setuptools;
  * pyproject.toml is removed, because its SPDX license string needs a very new setuptools and
    setup.py already supplies all metadata.
The optional cffi backend is switched off (the C backend is what gets imported).
"""
from pathlib import Path

from pythonforandroid.recipe import CompiledComponentsPythonRecipe


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
        build_dir = Path(self.get_build_dir(arch.arch))
        setup_py = build_dir / 'setup.py'
        text = setup_py.read_text()
        old = 'from packaging.version import Version'
        if old in text and 'setuptools._vendor' not in text:
            setup_py.write_text(text.replace(
                old,
                'try:\n    from packaging.version import Version\n'
                'except ImportError:\n    from setuptools._vendor.packaging.version import Version'))
        pyproject = build_dir / 'pyproject.toml'
        if pyproject.exists():
            pyproject.unlink()


recipe = ZstandardRecipe()
