import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    uvicorn.run("public_site.app:app", host="127.0.0.1", port=8511, reload=False)
