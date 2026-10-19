"""Pure lexical Batch A acceptance; no storage targets are opened."""
from dataclasses import FrozenInstanceError
from pathlib import PureWindowsPath, Path
import subprocess
import sys

import pytest

from paper.offline.journal_storage import _PathValidationError, _validate_windows_path


@pytest.mark.parametrize('path', [r'C:\journal.db', r'c:\data\journal.db',
    r'Z:\Paper Data\My Journal.sqlite', r'd:\MixedCase\café.db',
    r'D:\COM0\LPT10.db', r'C:\ data\file name.db'])
def test_valid_preserves_spelling(path):
    result = _validate_windows_path(path)
    assert result.original == path
    assert result.drive == path[:2]
    assert result.components == tuple(path[3:].split('\\'))
    assert result.drive + '\\' + '\\'.join(result.components) == path


class StringSubclass(str):
    pass


@pytest.mark.parametrize('value', [None, True, 1, b'C:\\a.db', [], {},
    PureWindowsPath(r'C:\a.db'), StringSubclass(r'C:\a.db')])
def test_invalid_types(value):
    with pytest.raises(_PathValidationError):
        _validate_windows_path(value)


INVALID = [
    '', 'C:', 'C:\\', 'C:a.db', 'a.db', '\\a.db', '/a.db',
    r'\\server\share\a.db', r'\\?\C:\a.db', r'\\.\C:\a.db',
    r'\??\C:\a.db', r'1:\a.db', r'CC:\a.db', r'é:\a.db',
    ' C:\\a.db', r'C::\a.db', r'C:\a:b.db', r'C:\a.db:stream',
    'C:\\a\x00.db', 'C:\\a\n.db', 'C:\\a\x1f.db', 'C:\\a\ud800.db',
    r'C:\*.db', r'C:\a?.db', r'C:\a<b.db', r'C:\a>b.db',
    r'C:\a"b.db', r'C:\a|b.db', r'C:/a.db', r'C:\dir/a.db',
    'C:\\a.\\b.db', 'C:\\a \\b.db', 'C:\\a.db.', 'C:\\a.db ',
    r'C:\.\a.db', r'C:\..\a.db', r'C:\dir\..\a.db',
    r'C:\dir\\a.db', 'C:\\dir\\', r'C:\\a.db',
    r'%TEMP%\a.db', r'C:\%TEMP%\a.db', r'C:\$HOME\a.db',
    r'C:\${HOME}\a.db', r'~\a.db', r'C:\~user\a.db',
    'file:C:/a.db', 'file:///C:/a.db', ':memory:', r'C:\a.db?mode=rw',
]


@pytest.mark.parametrize('path', INVALID)
def test_invalid_spellings(path):
    with pytest.raises(_PathValidationError):
        _validate_windows_path(path)


@pytest.mark.parametrize('name', ['CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
    *['COM' + n for n in '123456789¹²³'],
    *['LPT' + n for n in '123456789¹²³']])
@pytest.mark.parametrize('suffix', ['', '.db', '.many.extensions', ' .db'])
def test_reserved_components(name, suffix):
    for component in (name + suffix, name.lower() + suffix):
        for path in ('C:\\' + component, 'C:\\' + component + '\\journal.db'):
            with pytest.raises(_PathValidationError):
                _validate_windows_path(path)


def test_immutable_record():
    result = _validate_windows_path(r'C:\data\a.db')
    for field, value in [('original', 'other'), ('drive', 'D:'), ('components', ())]:
        with pytest.raises(FrozenInstanceError):
            setattr(result, field, value)
    with pytest.raises(TypeError):
        result.components[0] = 'other'
    assert not hasattr(result, '__dict__')


def test_import_and_validation_isolation():
    # Preload only test instrumentation; then execute the real module source in
    # a registered module with imports and all target access guarded. Loading
    # Python source itself is intentionally outside the no-filesystem boundary.
    source = Path(__file__).parents[1].joinpath('paper/offline/journal_storage.py').read_text(encoding='utf-8')
    code = r'''
import builtins, dataclasses, io, os, pathlib, sqlite3, sys, types, ctypes
source = SOURCE
def deny(*a, **k): raise AssertionError('forbidden activity')
real_import = builtins.__import__
def guarded(name, *a, **k):
    if name != 'dataclasses': raise AssertionError('unexpected import: ' + name)
    return real_import(name, *a, **k)
class NoEnvironment:
    __getitem__ = get = __iter__ = __contains__ = deny
os.environ = NoEnvironment()
os.getenv = os.putenv = os.stat = os.lstat = os.listdir = os.scandir = os.open = deny
builtins.open = io.open = sqlite3.connect = deny
pathlib.Path.resolve = pathlib.Path.absolute = deny
ctypes.CDLL = ctypes.PyDLL = deny
if hasattr(ctypes, 'WinDLL'): ctypes.WinDLL = deny
if hasattr(ctypes, 'windll'): ctypes.windll = NoEnvironment()
module = types.ModuleType('batch_a_isolation')
sys.modules[module.__name__] = module
compiled = compile(source, '<batch_a>', 'exec')
builtins.__import__ = guarded
exec(compiled, module.__dict__)
assert module._validate_windows_path(r'c:\Paper Data\a.db').drive == 'c:'
for path in ('file:C:/a.db', r'C:\..\a.db', r'C:\%TEMP%\a.db'):
    try: module._validate_windows_path(path)
    except module._PathValidationError: pass
    else: raise AssertionError('unsafe path accepted')
'''.replace('SOURCE', repr(source))
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
