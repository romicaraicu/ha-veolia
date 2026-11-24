#!/usr/bin/env python3
"""Generează dashboard-ul Veolia pentru un loc de consum.

Utilizare:
    python3 tools/genereaza_dashboard.py <cod_loc_consum> [folder_ieșire]
    -> creează dashboard/veolia_<cod>.yaml (gata de lipit în editorul brut)

Codul locului de consum e numărul de serie al dispozitivului Veolia din
Setări -> Dispozitive și servicii -> Veolia VRSI.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "4000000000"


def slug(code: str) -> str:
    """Aceeași transformare ca homeassistant.util.slugify pentru coduri numerice."""
    return re.sub(r"[^a-z0-9]+", "_", code.strip().lower()).strip("_")


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 1
    code = sys.argv[1].strip()
    out_dir = Path(sys.argv[2]) if len(sys.argv) == 3 else ROOT / "dashboard"
    src = ROOT / "dashboard" / "veolia_dashboard.yaml"
    out = out_dir / f"veolia_{code}.yaml"
    out.write_text(src.read_text(encoding="utf-8").replace(PLACEHOLDER, slug(code)), encoding="utf-8")
    print(f"✓ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
