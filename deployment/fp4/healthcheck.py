import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as r:
    assert r.status == 200
with urllib.request.urlopen("http://127.0.0.1:8000/v1/models", timeout=5) as r:
    models = json.load(r)["data"]
assert any(
    m["id"] == "ephemerai-qwen3.8-27b-nvfp4-131072" and m.get("max_model_len") == 131072
    for m in models
)
