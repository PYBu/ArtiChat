from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault('WEBUI_SECRET_KEY', 'test-images-secret-key')

BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
