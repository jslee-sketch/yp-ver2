import sys, json, urllib.request as u

url = "http://127.0.0.1:9000/openapi.json"
# 사용법: python openapi_summary.py [openapi_url] [/path METHOD] [/path METHOD] ...
# 예:    python openapi_summary.py http://127.0.0.1:9000/openapi.json /reservations POST /reservations/pay POST

args = sys.argv[1:]
if args and not args[0].startswith("/"):
    url = args[0]
    args = args[1:]

pairs = list(zip(args[0::2], args[1::2])) if args else [
    ("/reservations", "POST"),
    ("/reservations/pay", "POST"),
]

doc = json.loads(u.urlopen(url).read().decode("utf-8"))

for ep, method in pairs:
    m = method.lower()
    try:
        info = doc["paths"][ep][m]
        print(f"{ep} {method.upper()} -> {info.get('summary')}")
    except KeyError:
        print(f"{ep} {method.upper()} -> (not found)")
