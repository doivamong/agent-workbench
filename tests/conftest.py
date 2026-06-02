"""Make the kit's modules importable from tests without packaging."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# "" so ``import install`` (a repo-root module) resolves, plus the kit's source dirs.
for _p in ("", "scripts", "tools", ".claude/hooks/scripts", ".claude/hooks/lib"):
    sys.path.insert(0, str(ROOT / _p))
