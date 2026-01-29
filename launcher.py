#!/usr/bin/env python3
"""HeyClaude launcher for PyInstaller."""

import sys
from pathlib import Path

# Add src to path for imports
if getattr(sys, 'frozen', False):
    # Running as compiled
    base_path = Path(sys._MEIPASS)
else:
    # Running as script
    base_path = Path(__file__).parent

sys.path.insert(0, str(base_path / 'src'))

from heyclaude.app import main

if __name__ == '__main__':
    main()
