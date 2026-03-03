New-Item -ItemType Directory -Force .\scripts | Out-Null

@'
import sqlite3
db = r"C:\dev\yp-ver2\app\ypver2.db"
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("""
select r.id, r.status, r.amount_total
from reservations r
left join reservation_settlements s on s.reservation_id = r.id
where r.status = ? and s.id is null
order by r.id desc
limit 200
""", ("PAID",))
rows = cur.fetchall()
print("COUNT", len(rows))
for row in rows:
    print(row)
con.close()
'@ | Set-Content -Encoding UTF8 .\scripts\find_paid_without_settlement.py

python .\scripts\find_paid_without_settlement.py