#!/usr/bin/env python3
"""Export the FastAPI OpenAPI spec to JSON for Orval codegen.

Usage:
    python scripts/export-openapi.py

Outputs:
    packages/api-client/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the backend package is importable
backend_src = Path(__file__).resolve().parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

from aerisun.main import app  # noqa: E402

spec = app.openapi()

root = Path(__file__).resolve().parent.parent
dest = root / "packages" / "api-client" / "openapi.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(spec, indent=2, default=str, ensure_ascii=False) + "\n")
print(f"Wrote {dest}")
