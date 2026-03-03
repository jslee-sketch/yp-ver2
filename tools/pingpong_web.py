"""
핑퐁이 팀 테스트용 웹 채팅 서버
실행: python tools/pingpong_web.py
접속: http://localhost:5000
팀원: http://<서버IP>:5000
"""
import os
import sys
import json
import datetime
import threading
import uuid
from pathlib import Path

# .env 로드 (sidecar가 사용하는 OPENAI_API_KEY, NAVER_CLIENT_* 등)
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass  # dotenv 없으면 시스템 환경변수 사용

from flask import Flask, render_template_string, request, jsonify, session

# ── sidecar 임포트 ──────────────────────────────────────────────────────────
import pingpong_sidecar_openai as _sidecar
from pingpong_sidecar_openai import (
    ConversationState,
    step_once,
    classify_intent,
    OPENAI_MODEL,
)
from openai import OpenAI

# ── Google Sheets 설정 ──────────────────────────────────────────────────────
GSHEET_CRED = _ROOT / "credentials" / "gsheet_key.json"
GSHEET_ID   = os.environ.get("GSHEET_ID", "YOUR_SPREADSHEET_ID_HERE")

# ── Flask ────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", os.urandom(24).hex())

# ── 공유 상태 (스레드 안전) ──────────────────────────────────────────────────
_lock     = threading.Lock()
_sessions: dict[str, ConversationState] = {}      # sid → ConversationState
_client: OpenAI = OpenAI()                         # OpenAI 클라이언트 (공유)


# ── sidecar 래퍼 ─────────────────────────────────────────────────────────────
def ask_pingpong(question: str, sid: str) -> dict:
    """
    per-session ConversationState를 스왑하면서 step_once 호출.
    classify_intent를 먼저 호출해 intent.kind 를 얻고,
    step_once 내부에서 캐시 히트로 재사용 → LLM 이중 호출 없음.
    """
    with _lock:
        # 세션 상태 스왑
        if sid not in _sessions:
            _sessions[sid] = ConversationState()
        _sidecar.S = _sessions[sid]

        try:
            prev_mode = _sidecar.S.last_mode
            # 1) intent 분류 (캐시 저장)
            intent = classify_intent(
                question, prev_mode, _sidecar.S.history[-2:], _client
            )
            # 2) 실제 답변 (캐시 히트)
            answer = step_once(question, _client)
            kind   = intent.kind
        except Exception as e:
            kind   = "ERROR"
            answer = f"서버 오류: {e}"
        finally:
            # 세션 상태 저장
            _sessions[sid] = _sidecar.S

    return {"kind": kind, "answer": answer}


def reset_session(sid: str) -> None:
    with _lock:
        _sessions[sid] = ConversationState()
        _sidecar.S = _sessions[sid]


# ── Google Sheets ─────────────────────────────────────────────────────────────
def append_to_gsheet(row: list) -> None:
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        if not GSHEET_CRED.exists():
            print("⚠️ credentials/gsheet_key.json 없음 — 리포트 스킵")
            return
        if GSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
            print("⚠️ GSHEET_ID 미설정 — 리포트 스킵")
            return

        creds  = Credentials.from_service_account_file(
            str(GSHEET_CRED),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc     = gspread.authorize(creds)
        sheet  = gc.open_by_key(GSHEET_ID).sheet1
        sheet.append_row(row)
        print(f"✅ GSheets 저장: {row[3]!r}")
    except Exception as e:
        print(f"⚠️ GSheets 저장 실패: {e}")


# ── HTML ─────────────────────────────────────────────────────────────────────
# %% → Flask render_template_string에서 리터럴 %로 처리
_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🏓 핑퐁이 팀 테스트</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Pretendard',-apple-system,'Malgun Gothic',sans-serif;
     background:#f5f5f5;height:100vh;display:flex;flex-direction:column}
.header{background:#2563eb;color:#fff;padding:12px 20px;
        display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:18px}
.info{font-size:13px;opacity:.8}
.chat{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:10px 14px;border-radius:12px;
     font-size:14px;line-height:1.6;word-break:break-word;white-space:pre-wrap}
.msg.user{align-self:flex-end;background:#2563eb;color:#fff;border-bottom-right-radius:4px}
.msg.bot{align-self:flex-start;background:#fff;color:#333;
         border-bottom-left-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.kind{display:inline-block;background:#e0e7ff;color:#3b82f6;
      font-size:11px;padding:2px 6px;border-radius:4px;margin-bottom:4px}
.report-btn{display:inline-block;margin-top:8px;font-size:12px;color:#ef4444;
            cursor:pointer;border:1px solid #fca5a5;padding:2px 8px;border-radius:4px}
.report-btn:hover{background:#fef2f2}
.bar{padding:12px 16px;background:#fff;border-top:1px solid #e5e7eb;display:flex;gap:8px}
.bar input{flex:1;padding:10px 14px;border:1px solid #d1d5db;
           border-radius:8px;font-size:14px;outline:none}
.bar input:focus{border-color:#2563eb}
.bar button{padding:10px 20px;background:#2563eb;color:#fff;
            border:none;border-radius:8px;font-size:14px;cursor:pointer}
.bar button:disabled{background:#93c5fd;cursor:not-allowed}
.rst{background:#6b7280 !important;font-size:12px !important;padding:8px 12px !important}
.typing{color:#999;font-style:italic;font-size:13px;padding:4px 14px}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);
         z-index:100;justify-content:center;align-items:center}
.overlay.on{display:flex}
.modal{background:#fff;padding:24px;border-radius:12px;width:420px;max-width:90vw}
.modal h3{margin-bottom:12px}
.modal select,.modal textarea{width:100%;padding:8px;margin-bottom:12px;
  border:1px solid #d1d5db;border-radius:6px;font-size:14px}
.modal textarea{height:80px;resize:vertical}
.modal .btns{display:flex;gap:8px;justify-content:flex-end}
.modal .btns button{padding:8px 16px;border-radius:6px;border:none;
                    cursor:pointer;font-size:14px}
.cancel{background:#e5e7eb}
.submit{background:#ef4444;color:#fff}
</style>
</head>
<body>
<div class="header">
  <h1>🏓 핑퐁이 팀 테스트</h1>
  <div class="info" id="info"></div>
</div>
<div class="chat" id="chat"></div>
<div class="bar">
  <input id="inp" placeholder="핑퐁이에게 질문하세요..."
         onkeydown="if(event.key==='Enter'&&!event.isComposing)send()">
  <button onclick="send()" id="btn">전송</button>
  <button class="rst" onclick="doReset()">초기화</button>
</div>

<div class="overlay" id="modal">
  <div class="modal">
    <h3>🚨 Bad Case 리포트</h3>
    <p style="font-size:13px;color:#666;margin-bottom:12px" id="mQ"></p>
    <select id="mType">
      <option value="wrong_intent">의도 분류 오류</option>
      <option value="wrong_answer">답변 내용 오류</option>
      <option value="no_basis">근거 없는 답변 (뇌피셜)</option>
      <option value="wrong_price">가격 정보 이상</option>
      <option value="bad_tone">말투/어조 부적절</option>
      <option value="other">기타</option>
    </select>
    <textarea id="mCmt" placeholder="구체적으로 뭐가 이상한지 적어주세요..."></textarea>
    <div class="btns">
      <button class="cancel" onclick="mClose()">취소</button>
      <button class="submit" onclick="mSubmit()">제출</button>
    </div>
  </div>
</div>

<script>
let T = localStorage.getItem('pp_tester');
if(!T){T=prompt('테스터 이름을 입력하세요 (팀 내 구분용)');
       localStorage.setItem('pp_tester',T||'익명');T=T||'익명';}
document.getElementById('info').textContent='👤 '+T;
let R={};

function add(role,text,kind){
  const c=document.getElementById('chat'),d=document.createElement('div');
  d.className='msg '+role;
  if(role==='bot'){
    const k=kind?'<span class="kind">'+kind+'</span><br>':'';
    d.innerHTML=k+text.replace(/</g,'&lt;').replace(/>/g,'&gt;')
                       .replace(/\n/g,'<br>')+
      '<br><span class="report-btn" onclick="mOpen(this)">🚨 이상한 답변</span>';
    d.dataset.q=R.q||'';d.dataset.k=kind||'';d.dataset.a=text.substring(0,300);
  }else{d.textContent=text;}
  c.appendChild(d);c.scrollTop=c.scrollHeight;
}

async function send(){
  const i=document.getElementById('inp'),q=i.value.trim();
  if(!q)return;i.value='';add('user',q);R.q=q;
  document.getElementById('btn').disabled=true;
  const c=document.getElementById('chat');
  const t=document.createElement('div');t.className='typing';
  t.textContent='핑퐁이가 답변 중...';c.appendChild(t);c.scrollTop=c.scrollHeight;
  try{
    const r=await fetch('/api/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({question:q,tester:T})});
    const d=await r.json();t.remove();add('bot',d.answer,d.kind);
  }catch(e){t.remove();add('bot','❌ 오류: '+e.message,'ERROR');}
  document.getElementById('btn').disabled=false;i.focus();
}

async function doReset(){
  if(!confirm('대화 기록을 초기화할까요?'))return;
  await fetch('/api/reset',{method:'POST'});
  document.getElementById('chat').innerHTML='';
}

function mOpen(el){
  const m=el.closest('.msg');
  R={q:m.dataset.q,k:m.dataset.k,a:m.dataset.a};
  document.getElementById('mQ').textContent='"'+R.q+'" → '+R.k;
  document.getElementById('mType').selectedIndex=0;
  document.getElementById('mCmt').value='';
  document.getElementById('modal').classList.add('on');
}
function mClose(){document.getElementById('modal').classList.remove('on');}
async function mSubmit(){
  const btn=document.querySelector('.submit');
  btn.disabled=true;
  try{
    await fetch('/api/report',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({tester:T,question:R.q,kind:R.k,answer:R.a,
        problem_type:document.getElementById('mType').value,
        comment:document.getElementById('mCmt').value})});
    alert('✅ 리포트 저장됐어요!');mClose();
  }finally{btn.disabled=false;}
}
</script>
</body>
</html>
"""


# ── 라우트 ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())[:8]
    return render_template_string(_HTML)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    q    = (data.get("question") or "").strip()
    sid  = session.get("sid") or "default"

    if not q:
        return jsonify({"kind": "", "answer": ""})

    result = ask_pingpong(q, sid)
    return jsonify(result)


@app.route("/api/reset", methods=["POST"])
def api_reset():
    sid = session.get("sid") or "default"
    reset_session(sid)
    session["sid"] = str(uuid.uuid4())[:8]  # 새 세션 ID
    return jsonify({"ok": True})


@app.route("/api/report", methods=["POST"])
def api_report():
    d = request.get_json(force=True)
    row = [
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        d.get("tester", ""),
        session.get("sid", ""),
        d.get("question", ""),
        d.get("kind", ""),
        (d.get("answer") or "")[:300],
        d.get("problem_type", ""),
        d.get("comment", ""),
    ]
    append_to_gsheet(row)
    print(
        f"🚨 BAD [{d.get('tester')}] "
        f"\"{d.get('question')}\" → {d.get('problem_type')} | {d.get('comment','')[:60]}"
    )
    return jsonify({"ok": True})


@app.route("/api/sessions")
def api_sessions():
    """디버그용: 현재 활성 세션 수"""
    return jsonify({"active_sessions": len(_sessions)})


# ── 진입점 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        print("❌ OPENAI_API_KEY가 없습니다. .env 또는 환경변수를 확인하세요.")
        sys.exit(1)

    print("=" * 52)
    print("🏓 핑퐁이 팀 테스트 서버")
    print("=" * 52)
    print(f"   접속: http://localhost:5000")
    print(f"   모델: {OPENAI_MODEL}")
    gsheet_ok = GSHEET_CRED.exists() and GSHEET_ID != "YOUR_SPREADSHEET_ID_HERE"
    print(f"   GSheets: {'✅ 연결됨' if gsheet_ok else '⚠️  미설정 (리포트 콘솔만 출력)'}")
    print("=" * 52)
    print("팀원 접속 주소: python -c \"import socket; print(socket.gethostbyname(socket.gethostname()))\"")
    print("  → http://<위 IP>:5000")
    print("=" * 52)

    # threaded=True: 동시 접속 처리 (Lock으로 step_once 직렬화)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
