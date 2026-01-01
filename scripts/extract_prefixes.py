from __future__ import annotations

import re
from pathlib import Path


PARAM_RE = re.compile(r"\{[^}]+\}")


def normalize_path(p: str) -> str:
    # /offers/{id}/confirm -> /offers/confirm 로 만들지 말고
    # /offers 로 prefix용 묶음을 만들기 위해 파라미터 이후는 제거에 가까운 방식
    p = p.strip()
    if not p.startswith("/"):
        return ""

    # 파라미터 제거 (prefix 계산 전에)
    p_no_params = PARAM_RE.sub("", p)
    p_no_params = re.sub(r"//+", "/", p_no_params)

    # 토큰 분리
    parts = [x for x in p_no_params.split("/") if x]

    if not parts:
        return "/"

    # prefix 규칙:
    # 1) v3_6로 시작하면 두 토큰까지 ( /v3_6/reservations )
    # 2) 그 외는 첫 토큰까지 ( /offers, /reservations, /admin 등 )
    if parts[0] == "v3_6":
        if len(parts) >= 2:
            return f"/{parts[0]}/{parts[1]}"
        return f"/{parts[0]}"

    return f"/{parts[0]}"


def main() -> int:
    src = Path("docs/engineering/routes.txt")
    if not src.exists():
        print("routes.txt not found. Run dump_routes.py first.")
        return 1

    prefixes = set()

    for line in src.read_text(encoding="utf-8", errors="ignore").splitlines():
        # 라인 형태: GET /path name
        line = line.strip()
        if not line:
            continue
        cols = line.split()
        if len(cols) < 2:
            continue
        path = cols[1]
        pref = normalize_path(path)
        if pref:
            prefixes.add(pref)

    out = Path("docs/engineering/prefixes.txt")
    out.parent.mkdir(parents=True, exist_ok=True)

    for p in sorted(prefixes):
        print(p)

    out.write_text("\n".join(sorted(prefixes)) + "\n", encoding="utf-8")
    print(f"\n[OK] wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())