from pathlib import Path

p = Path(r"app/policy/docs/admin/guardrails.md")
b = p.read_bytes()

print("PATH", p)
print("bytes", len(b))
print("BOM_UTF8", b[:3] == b"\xef\xbb\xbf")
print("has_null_byte", b"\x00" in b)

def score(s: str):
    hangul = sum(1 for ch in s if ("\uac00" <= ch <= "\ud7a3"))
    repl = s.count("\ufffd")
    q = s.count("?")
    latin1 = sum(1 for ch in s if 0x00C0 <= ord(ch) <= 0x00FF)
    return hangul, repl, q, latin1

cands = []
for enc in ["utf-8","cp949","euc-kr","utf-16","utf-16le","utf-16be","cp1252","latin1"]:
    try:
        s = b.decode(enc)
        cands.append((enc,) + score(s))
    except Exception:
        pass

print("CANDIDATES (enc, hangul, repl, ?, latin1):")
for row in sorted(cands, key=lambda x: (x[1], -x[2], -x[3], -x[4]), reverse=True)[:12]:
    print(row)
