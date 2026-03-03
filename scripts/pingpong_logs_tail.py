import sqlite3
DB=r"C:\dev\yp-ver2\app\ypver2.db"
con=sqlite3.connect(DB); cur=con.cursor()
cur.execute("""
select id, created_at, screen, question, error_code
from pingpong_logs
order by id desc
limit 5
""")
for r in cur.fetchall():
  print(r)
con.close()
