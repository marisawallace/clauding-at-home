"""
Make vendored third-party packages importable.

Importing this module prepends `<repo>/vendor` to `sys.path` so that
`import prompt_toolkit` resolves to the vendored copy regardless of what is
installed in the user's site-packages. See vendor/VERSIONS.txt.
"""

import sys
from pathlib import Path

_VENDOR_DIR = Path(__file__).parent.resolve() / "vendor"
_vendor_str = str(_VENDOR_DIR)
if _VENDOR_DIR.is_dir() and _vendor_str not in sys.path:
    # Prepend so vendored copy wins over any system-installed version.
    sys.path.insert(0, _vendor_str)
