import os
import sys

# Ensure the src/ package dir is importable as top-level modules (api, graph, ...)
# so `uv run python -m src` resolves the "api:app" ASGI target. Matches the test
# path, which sets pythonpath=["src"].
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False)
