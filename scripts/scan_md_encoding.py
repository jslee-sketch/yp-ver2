import os, re, pathlib

root = pathlib.Path("policy/docs/admin")
bad = []

# 모지바케 흔적(UTF-8을 CP949로 잘못 읽거나 그 반대에서 자주 보이는 패턴)
mojibake_re = re.compile(r"[ìëêãâ¤\uFFFD]")

for p in root.rglob("*.md"):
    b = p.read_bytes()
    # 1) utf-8로 읽어보기
    try:
        s = b.decode("utf-8")
        # replacement char(�) 또는 대표 모지바케 문자 있으면 의심
        if "\uFFFD" in s or mojibake_re.search(s):
            bad.append((str(p), "looks_garbled_or_replacement_in_utf8"))
        continue
    except UnicodeDecodeError:
        bad.append((str(p), "not_utf8"))

print("FOUND", len(bad))
for path, why in bad[:200]:
    print(why, "=>", path)
