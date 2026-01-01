#!/usr/bin/env python
"""
scripts/policy_audit.py
- 레거시 정책(R/RV) 참조를 스캔해서 "정책 중앙화 후보" 리포트를 만든다.
사용법:
  python scripts/policy_audit.py --root . --out out/policy_audit.md
"""
from __future__ import annotations
import argparse, os, re
from collections import defaultdict

PATTERNS = [
    ("getattr(R, ...)", re.compile(r'getattr\(\s*R\s*,\s*"([A-Z0-9_]+)"')),
    ("getattr(RV, ...)", re.compile(r'getattr\(\s*RV\s*,\s*"([A-Z0-9_]+)"')),
    ("R.<CONST>", re.compile(r'\bR\.([A-Z][A-Z0-9_]+)\b')),
    ("RV.<CONST>", re.compile(r'\bRV\.([A-Z][A-Z0-9_]+)\b')),
]

EXCLUDE_DIRS = {".git", "venv", "__pycache__", ".pytest_cache", "node_modules"}

def iter_py_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)

def read_text(path: str) -> str:
    with open(path, "rb") as f:
        b = f.read()
    for enc in ("utf-8", "cp949", "utf-16", "latin1"):
        try:
            s = b.decode(enc)
            if s.count("\x00") > 0.1 * len(s):
                continue
            return s
        except Exception:
            pass
    return b.decode("utf-8", errors="replace")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--out", default="policy_audit.md", help="output md path")
    args = ap.parse_args()

    hits = {name: defaultdict(set) for name, _ in PATTERNS}

    for fpath in iter_py_files(args.root):
        txt = read_text(fpath)
        rel = os.path.relpath(fpath, args.root)
        for name, pat in PATTERNS:
            for m in pat.finditer(txt):
                key = m.group(1)
                hits[name][key].add(rel)

    lines = []
    lines.append("# Policy audit (legacy references)\n")
    for name, _ in PATTERNS:
        lines.append(f"## {name}")
        for key, files in sorted(hits[name].items(), key=lambda kv: (-len(kv[1]), kv[0])):
            sample = ", ".join(sorted(list(files))[:5])
            lines.append(f"- `{key}` ({len(files)} files) :: {sample}")
        lines.append("")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[ok] wrote: {args.out}")

if __name__ == "__main__":
    main()
