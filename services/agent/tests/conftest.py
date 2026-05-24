import os
import sys
from pathlib import Path

# Make the mono-repo's libs/ importable when running pytest outside Docker
# (Dockerfile sets PYTHONPATH=/libs; locally we replicate that here).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIBS = _REPO_ROOT / "libs"
if _LIBS.exists() and str(_LIBS) not in sys.path:
    sys.path.insert(0, str(_LIBS))

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("CLERK_ISSUER", "https://test.clerk.accounts.dev")
