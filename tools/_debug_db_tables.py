import sqlite3

db = r"C:\dev\yp-ver2\app\ypver2.db"
con = sqlite3.connect(db)
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in cur.fetchall()]
print("tables:", len(tables))
print("\n".join(tables))

cand = [t for t in tables if "reserv" in t.lower()]
print("\nreserv-like tables:", cand)

for t in cand:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in cur.fetchall()]
        idcol = "id" if "id" in cols else ("reservation_id" if "reservation_id" in cols else None)
        last = None
        if idcol:
            cur.execute(f"SELECT {idcol} FROM {t} ORDER BY {idcol} DESC LIMIT 5")
            last = cur.fetchall()
        print(f"- {t}: count={cnt}, idcol={idcol}, last={last}")
    except Exception as e:
        print(f"- {t}: ERROR {e}")

con.close()
