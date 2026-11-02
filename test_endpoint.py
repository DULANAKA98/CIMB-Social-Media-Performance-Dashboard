import os
import sys

sys.path.append("backend")

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL must be supplied externally; never hard-code database credentials.")

from main import export_platform_highlights

try:
    export_platform_highlights("2026-04-30", "2026-05-31")
    print("SUCCESS")
except Exception:
    import traceback

    traceback.print_exc()
