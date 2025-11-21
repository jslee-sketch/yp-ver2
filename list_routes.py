import sys, importlib, inspect
sys.path.insert(0, r'C:\Users\user\Desktop\yp-ver2')
from app.main import app
seen = {}
for r in app.routes:
    p = getattr(r, 'path', '')
    if p.startswith('/reservations') or p.startswith('/offers'):
        methods = '/'.join(sorted(getattr(r, 'methods', [])))
        key = (methods, p)
        seen[key] = seen.get(key, 0) + 1
        ep = getattr(r, 'endpoint', None)
        name = getattr(ep, '__name__', '?')
        print(f"{methods:10s} {p:35s} -> {name}")
print('DUPLICATES:', {k:v for k,v in seen.items() if v>1})
