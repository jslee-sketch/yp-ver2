# scripts/show_ai_logs.py
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def main():
    # 프로젝트 루트 기준: app/ypver2.db
    project_root = Path(__file__).resolve().parents[1]
    db_path = project_root / "app" / "ypver2.db"

    print(f"📂 DB Path: {db_path}")
    if not db_path.exists():
        print("❌ DB 파일을 찾을 수 없습니다.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 테이블 이름이 다르면 여기만 바꿔주면 됨
    table_name = "deal_ai_logs"

    try:
        cur.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 10")
    except Exception as e:
        print(f"❌ 쿼리 실패: {e}")
        conn.close()
        return

    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("ℹ️ 아직 로그가 없습니다.")
        return

    print(f"\n✅ 최근 {len(rows)}개 로그 ({table_name})")
    for r in rows:
        print("\n----------------------------------------")
        for col in r.keys():
            val = r[col]
            # request_json / response_json 같은 JSON 컬럼은 예쁘게 출력
            if isinstance(val, str) and (col.endswith("json") or col.endswith("_json")):
                try:
                    parsed = json.loads(val)
                    print(f"{col}:")
                    print(json.dumps(parsed, ensure_ascii=False, indent=2))
                    continue
                except Exception:
                    # 그냥 문자열로 출력
                    pass
            print(f"{col}: {val}")


if __name__ == "__main__":
    main()