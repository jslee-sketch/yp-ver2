# scripts/snapshot_state.py
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    "app/crud.py",
    "app/core/shipping_policy.py",
    "app/core/refund_policy.py",
    "app/core/refund_context_builder.py",
    "app/models.py",
]

FUNC_PATTERNS = [
    r"def\s+preview_refund_for_paid_reservation\s*\(",
    r"def\s+refund_paid_reservation\s*\(",
    r"def\s+create_reservation\s*\(",
    r"def\s+pay_reservation\s*\(",
    r"def\s+pay_reservation_v35\s*\(",
]

def sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def extract_signature(text: str, def_line_index: int) -> str:
    # def 라인부터 ")" 또는 ":"가 닫힐 때까지 대충 합친다(멀티라인 시그니처 대응)
    lines = text.splitlines()
    buf = []
    for i in range(def_line_index, min(def_line_index + 25, len(lines))):
        buf.append(lines[i].rstrip())
        if lines[i].strip().endswith("):") or lines[i].strip().endswith(") -> Reservation:") or lines[i].strip().endswith(")-> Reservation:"):
            break
    return " ".join(buf)

def main():
    print("=== SNAPSHOT ROOT ===")
    print(str(ROOT))
    print()

    for rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            print(f"[MISS] {rel}")
            continue
        digest = sha256_of_file(p)
        size = p.stat().st_size
        print(f"[OK] {rel}  size={size}  sha256={digest}")

    print("\n=== SIGNATURE CHECK ===")
    for rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for pat in FUNC_PATTERNS:
            rx = re.compile(pat)
            for idx, line in enumerate(lines):
                if rx.search(line):
                    sig = extract_signature(text, idx)
                    print(f"- {rel}: {sig}")
                    break

    print("\n=== DONE ===")

if __name__ == "__main__":
    main()