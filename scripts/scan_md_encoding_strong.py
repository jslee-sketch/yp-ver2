import pathlib, unicodedata

root = pathlib.Path("policy/docs/admin")
sus = []

def is_hangul(ch):
    o = ord(ch)
    return (0xAC00 <= o <= 0xD7A3) or (0x1100 <= o <= 0x11FF) or (0x3130 <= o <= 0x318F)

def is_weird_latin(ch):
    # 라틴1 보이는 문자 중 모지바케에 자주 등장하는 범위
    o = ord(ch)
    return 0x00C0 <= o <= 0x00FF  # À-ÿ

for p in root.rglob("*.md"):
    b = p.read_bytes()
    try:
        s = b.decode("utf-8", errors="strict")
    except Exception:
        # utf-8 자체가 아니면 의심
        sus.append((str(p), "not_utf8"))
        continue

    if "\ufffd" in s:
        sus.append((str(p), "has_replacement_char"))
        continue

    total = len(s) or 1
    hangul = sum(1 for ch in s if is_hangul(ch))
    weird  = sum(1 for ch in s if is_weird_latin(ch))

    # 한글 거의 없는데 weird latin이 있으면 의심(문서가 한국어일 거라면 특히)
    if hangul < 5 and weird > 10:
        sus.append((str(p), f"low_hangul({hangul})_weirdlatin({weird})"))

print("SUSPECT", len(sus))
for x in sus[:200]:
    print(x[1], "=>", x[0])
