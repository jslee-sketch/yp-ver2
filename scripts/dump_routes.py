from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout, redirect_stderr


def _force_utf8_stdout() -> None:
    # Windows cp949 환경에서 ✅ 같은 문자 출력 때문에 죽는 문제 방지
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    _force_utf8_stdout()

    # app import 과정에서 찍히는 print(✅ DATABASE_URL 등)로 stdout 오염되는 걸 막기
    buf_out = io.StringIO()
    buf_err = io.StringIO()

    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        from app.main import app  # noqa: F401

    # 여기부터는 "라우트만" 출력
    routes = []
    for r in app.router.routes:
        methods = sorted(getattr(r, "methods", []) or [])
        path = getattr(r, "path", "")
        name = getattr(r, "name", "")
        if not path:
            continue
        if not methods:
            continue
        routes.append((methods[0], path, name))

    # 정렬
    routes.sort(key=lambda x: (x[1], x[0]))

    for method, path, name in routes:
        print(f"{method:<12} {path:<45} {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())