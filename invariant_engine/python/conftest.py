"""
pytest conftest — add engine and export directories to sys.path so that
tests can import from both packages without an installed package.
"""
import sys
import os

_HERE = os.path.dirname(__file__)

for _dir in ("engine", "export"):
    _path = os.path.abspath(os.path.join(_HERE, _dir))
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Root python/ dir itself (so `from export.X import Y` also works)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
