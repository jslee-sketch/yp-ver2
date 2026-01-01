import requests, sys, json
base = sys.argv[1] if len(sys.argv)>1 else "http://127.0.0.1:9000"
op = requests.get(f"{base}/openapi.json", timeout=5).json()
paths = op.get("paths", {})
print("Total paths:", len(paths))
for k, v in paths.items():
    if k.startswith(("/admin/deposit","/reservations","/offers")):
        print(k, "->", ", ".join(v.keys()))