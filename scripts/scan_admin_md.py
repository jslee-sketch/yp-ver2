from pathlib import Path

root = Path(r"app/policy/docs/admin")
rows = []

def score(s: str):
    hangul = sum(1 for ch in s if ("\uac00" <= ch <= "\ud7a3"))
    q = s.count("?")
    repl = s.count("\ufffd")
    latin1 = sum(1 for ch in s if 0x00C0 <= ord(ch) <= 0x00FF)
    n = len(s)
    q_ratio = (q / n) if n else 0.0
    h_ratio = (hangul / n) if n else 0.0
    return hangul, q, repl, latin1, n, q_ratio, h_ratio

for p in sorted(root.rglob("*.md")):
    b = p.read_bytes()
    try:
        s = b.decode("utf-8")
        enc = "utf-8"
    except Exception:
        # utf-8이 아니면 일단 cp949로 읽어봄(옛 파일 가능)
        try:
            s = b.decode("cp949")
            enc = "cp949"
        except Exception:
            s = ""
            enc = "unknown"

    hangul, q, repl, latin1, n, q_ratio, h_ratio = score(s)
    # 의심도: 물음표 비율 높거나, latin1 이상치 많거나, replacement 있으면
    suspect = (q_ratio >= 0.02) or (latin1 >= 20) or (repl > 0)
    rows.append((str(p), enc, n, hangul, q, repl, latin1, round(q_ratio,4), round(h_ratio,4), suspect))

print("TOTAL", len(rows))
print("SUSPECT", sum(1 for r in rows if r[-1]))
print("")
print("path | enc | len | hangul | ? | repl | latin1 | q_ratio | h_ratio | suspect")
for r in rows:
    if r[-1]:
        print(" | ".join(map(str, r)))

# csv도 저장
out = Path("out_admin_md_scan.csv")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(
    "path,enc,len,hangul,q,repl,latin1,q_ratio,h_ratio,suspect\n" +
    "\n".join(",".join(map(str, r)) for r in rows),
    encoding="utf-8"
)
print("\nWROTE", out)
