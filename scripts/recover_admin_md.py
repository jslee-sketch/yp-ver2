from pathlib import Path

ROOT = Path("app/policy/docs/admin")

def try_fix(text: str):
    # 케이스A: UTF-8을 CP949로 잘못 디코딩해서 생긴 모지바케를 되돌리기
    # (즉: 현재 문자열을 cp949로 다시 바이트화 -> utf-8로 디코딩)
    for enc in ("cp949", "euc-kr"):
        try:
            b = text.encode(enc, errors="strict")
            s2 = b.decode("utf-8", errors="strict")
            return f"{enc}->utf8", s2
        except Exception:
            pass

    # 케이스B: latin1 뒤집기(ì ì° 류)
    try:
        s2 = text.encode("latin1", errors="strict").decode("utf-8", errors="strict")
        return "latin1->utf8", s2
    except Exception:
        pass

    return None, None

targets = list(ROOT.rglob("*.md"))
made = 0

for p in targets:
    raw = p.read_bytes()

    # 우선 utf-8로 읽어보고(대부분 이 케이스)
    try:
        s = raw.decode("utf-8")
    except Exception:
        # 혹시 cp949 파일이면 -> utf8 변환본 생성
        try:
            s = raw.decode("cp949")
            out = p.with_suffix(p.suffix + ".converted.cp949_to_utf8.md")
            out.write_text(s, encoding="utf-8")
            print("CONVERT", p, "=>", out)
            made += 1
        except Exception:
            print("SKIP", p)
        continue

    # 눈에 띄는 모지바케 패턴이 있으면 복구 시도
    if ("紐" in s) or ("?댁" in s) or ("?쒕" in s) or ("ì " in s):
        how, fixed = try_fix(s)
        if fixed:
            out = p.with_suffix(p.suffix + f".recovered.{how}.md")
            out.write_text(fixed, encoding="utf-8")
            print("RECOVER", p, "via", how, "=>", out)
            made += 1
        else:
            print("NO_CAND", p)

print("DONE created:", made)
