from pathlib import Path
import re

ROOT = Path("app/policy/docs/admin")

MOJI = re.compile(r"[ìëêãâ¤]|[紐⑹쟻]|[?][댁쒕덉쟾]|[�]")

def score(s: str):
    hangul = sum(1 for ch in s if "\uac00" <= ch <= "\ud7a3")
    repl   = s.count("\ufffd")  # �
    q      = s.count("?")
    moji   = len(MOJI.findall(s))
    return hangul - (repl*200 + moji*5 + q*1), hangul, q, repl, moji

def gen_candidates(s: str):
    cands = []
    for enc in ("cp949","euc-kr"):
        for err in ("ignore","replace"):
            try:
                b = s.encode(enc, errors=err)
                out = b.decode("utf-8", errors="replace")
                cands.append((f"{enc}_to_utf8_{err}", out))
            except Exception:
                pass

    for err in ("ignore","replace"):
        try:
            out = s.encode("latin1", errors=err).decode("utf-8", errors="replace")
            cands.append((f"latin1_to_utf8_{err}", out))
        except Exception:
            pass

    for err in ("ignore","replace"):
        try:
            out = s.encode("utf-8", errors="strict").decode("cp949", errors=err)
            cands.append((f"utf8bytes_to_cp949_{err}", out))
        except Exception:
            pass

    uniq, seen = [], set()
    for how, t in cands:
        key = (how, t[:200])
        if key in seen:
            continue
        seen.add(key)
        uniq.append((how, t))
    return uniq

def looks_garbled(s: str):
    return ("?댁" in s) or ("?쒕" in s) or ("紐⑹" in s) or ("ì " in s) or ("\ufffd" in s)

def safe_suffix(s: str) -> str:
    # 윈도우 파일명 금지 문자 제거/치환
    return re.sub(r'[<>:"/\\\\|?*]', '_', s)

targets = list(ROOT.rglob("*.md"))
made = 0

for p in targets:
    raw = p.read_bytes()
    try:
        s = raw.decode("utf-8")
        enc_used = "utf-8"
    except Exception:
        try:
            s = raw.decode("cp949")
            enc_used = "cp949"
        except Exception:
            print("SKIP", p)
            continue

    # cp949 원본이면 그냥 utf-8 변환본 생성
    if enc_used == "cp949":
        out = p.with_suffix(p.suffix + ".converted.cp949_to_utf8.md")
        out.write_text(s, encoding="utf-8")
        print("CONVERT", p, "=>", out)
        made += 1
        continue

    if not looks_garbled(s):
        continue

    base_sc = score(s)
    best = (base_sc[0], "ORIGINAL", s, base_sc)

    for how, cand in gen_candidates(s):
        sc = score(cand)
        if sc[0] > best[0]:
            best = (sc[0], how, cand, sc)

    if best[1] != "ORIGINAL":
        how_safe = safe_suffix(best[1])
        out = p.with_suffix(p.suffix + f".recovered.{how_safe}.md")
        out.write_text(best[2], encoding="utf-8")
        print("RECOVER", p, "via", best[1], "score", best[3], "=>", out)
        made += 1
    else:
        print("NO_IMPROVEMENT", p, "base", base_sc)

print("DONE created:", made)
