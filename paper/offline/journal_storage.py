"""Internal, pure lexical Windows path checks for storage Batch A.

Acceptance does not authorize storage use: locality (including mapped/substituted
drives), existence, filesystem type, reparse points, hard links, file identity,
ACL protection and exclusive ownership require later handle-based validation.
No expansion, normalization, target access or storage acquisition occurs here.
"""
from dataclasses import dataclass


class _PathValidationError(ValueError):
    """Invalid user path spelling; future factories must map to ContractMismatch."""


@dataclass(frozen=True, slots=True)
class _WindowsPath:
    original: str
    drive: str
    components: tuple[str, ...]


def _validate_windows_path(path):
    """Preserve an exact str with an ASCII drive and nonempty file components.

    Only backslash separators are accepted. Percent, dollar and tilde syntax is
    conservatively refused, even when it might name a literal Windows file.
    Device names are checked in every component, including before extensions.
    """
    if type(path) is not str:
        raise _PathValidationError('Exact str path required')
    if (len(path) < 4 or path[0] not in
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            or path[1:3] != ':\\'):
        raise _PathValidationError('Absolute drive-qualified file path required')
    if any(c in '/:<>"|?*%$~' or ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF
           for c in path[2:]):
        raise _PathValidationError('Forbidden character or expansion syntax')
    components = tuple(path[3:].split('\\'))
    for component in components:
        if not component or component in ('.', '..') or component.endswith(('.', ' ')):
            raise _PathValidationError('Empty, dot or trailing-dot/space component')
        # Spaces before an extension must not disguise a DOS device basename.
        stem = component.split('.', 1)[0].rstrip(' ').upper()
        if (stem in ('CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$')
                or (len(stem) == 4 and stem[:3] in ('COM', 'LPT')
                    and stem[3] in '123456789\u00b9\u00b2\u00b3')):
            raise _PathValidationError('Reserved device component')
    return _WindowsPath(path, path[:2], components)
