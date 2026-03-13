import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

const BASE = import.meta.env.VITE_API_BASE || '';

interface ChatMessage {
  id: number;
  deal_id: number;
  sender_id: number | null;
  sender_nickname: string;
  message_type: string;
  content: string;
  created_at: string;
}

export default function DonzzulChatPage() {
  const { dealId } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [newMsg, setNewMsg] = useState('');
  const [nickname, setNickname] = useState(() => localStorage.getItem('donzzul_nickname') || '');
  const [showNicknameInput, setShowNicknameInput] = useState(false);
  const [dealTitle, setDealTitle] = useState('');
  const [loading, setLoading] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchMessages = async () => {
    try {
      const res = await fetch(`${BASE}/donzzul/deals/${dealId}/chat/messages?limit=100`);
      if (res.ok) {
        const data = await res.json();
        setMessages((data.messages || []).reverse());
      }
    } catch {}
    setLoading(false);
  };

  const fetchDeal = async () => {
    try {
      const res = await fetch(`${BASE}/donzzul/deals/${dealId}`);
      if (res.ok) {
        const data = await res.json();
        setDealTitle(data.deal?.title || `딜 #${dealId}`);
      }
    } catch {}
  };

  useEffect(() => {
    fetchDeal();
    fetchMessages();
    // 5초 폴링
    intervalRef.current = setInterval(fetchMessages, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [dealId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const content = newMsg.trim();
    if (!content) return;

    const nick = nickname.trim() || '익명';
    localStorage.setItem('donzzul_nickname', nick);

    try {
      const res = await fetch(`${BASE}/donzzul/deals/${dealId}/chat/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sender_nickname: nick,
          content,
          message_type: 'CHEER',
        }),
      });
      if (res.ok) {
        setNewMsg('');
        fetchMessages();
      }
    } catch {}
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDelete = async (msgId: number) => {
    try {
      await fetch(`${BASE}/donzzul/chat/messages/${msgId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      fetchMessages();
    } catch {}
  };

  const formatTime = (dt: string) => {
    try {
      const d = new Date(dt);
      return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    } catch { return ''; }
  };

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border-subtle, #333)',
        display: 'flex', alignItems: 'center', gap: 12, background: 'var(--bg-secondary, #1a1a2e)',
      }}>
        <button onClick={() => navigate(-1)} style={{
          background: 'none', border: 'none', color: 'var(--text-primary, #fff)',
          fontSize: 20, cursor: 'pointer', padding: 0,
        }}>←</button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary, #fff)' }}>
            {dealTitle || '응원방'}
          </div>
          <div style={{ fontSize: 11, color: '#4ade80' }}>응원 채팅방</div>
        </div>
        <button
          onClick={() => setShowNicknameInput(!showNicknameInput)}
          style={{
            background: 'rgba(74,222,128,0.15)', border: '1px solid rgba(74,222,128,0.3)',
            borderRadius: 6, padding: '4px 10px', fontSize: 12, color: '#4ade80', cursor: 'pointer',
          }}
        >
          {nickname || '닉네임 설정'}
        </button>
      </div>

      {/* Nickname input */}
      {showNicknameInput && (
        <div style={{ padding: '8px 16px', background: 'rgba(74,222,128,0.05)', borderBottom: '1px solid var(--border-subtle, #333)' }}>
          <input
            value={nickname}
            onChange={e => setNickname(e.target.value)}
            placeholder="닉네임 (최대 15자)"
            maxLength={15}
            onKeyDown={e => { if (e.key === 'Enter') { localStorage.setItem('donzzul_nickname', nickname); setShowNicknameInput(false); } }}
            style={{
              width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 13,
              background: 'var(--bg-primary, #0d0d1a)', border: '1px solid var(--border-subtle, #333)',
              color: 'var(--text-primary, #fff)', outline: 'none',
            }}
          />
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {loading && <div style={{ textAlign: 'center', color: '#888', padding: 40 }}>로딩 중...</div>}
        {!loading && messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#888', padding: 40 }}>
            아직 응원 메시지가 없어요.<br />첫 번째 응원을 남겨보세요!
          </div>
        )}
        {messages.map(m => (
          <div key={m.id} style={{
            padding: '8px 12px', borderRadius: 10,
            background: m.message_type === 'SYSTEM' ? 'rgba(74,222,128,0.08)' : 'rgba(255,255,255,0.04)',
            border: m.message_type === 'SYSTEM' ? '1px solid rgba(74,222,128,0.2)' : '1px solid rgba(255,255,255,0.06)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#4ade80' }}>
                {m.sender_nickname}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 10, color: '#666' }}>{formatTime(m.created_at)}</span>
                <button
                  onClick={() => handleDelete(m.id)}
                  style={{ background: 'none', border: 'none', color: '#555', fontSize: 10, cursor: 'pointer', padding: 0 }}
                  title="삭제"
                >x</button>
              </div>
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-primary, #fff)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
              {m.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '8px 12px', borderTop: '1px solid var(--border-subtle, #333)',
        background: 'var(--bg-secondary, #1a1a2e)', display: 'flex', gap: 8, alignItems: 'flex-end',
      }}>
        <textarea
          value={newMsg}
          onChange={e => setNewMsg(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="응원 메시지를 남겨보세요..."
          maxLength={500}
          rows={1}
          style={{
            flex: 1, padding: '10px 12px', borderRadius: 10, fontSize: 14,
            background: 'var(--bg-primary, #0d0d1a)', border: '1px solid var(--border-subtle, #333)',
            color: 'var(--text-primary, #fff)', outline: 'none', resize: 'none',
            maxHeight: 80, lineHeight: 1.4,
          }}
        />
        <button
          onClick={handleSend}
          disabled={!newMsg.trim()}
          style={{
            padding: '10px 16px', borderRadius: 10, fontSize: 14, fontWeight: 700,
            background: newMsg.trim() ? '#4ade80' : '#333', color: newMsg.trim() ? '#000' : '#666',
            border: 'none', cursor: newMsg.trim() ? 'pointer' : 'default',
            transition: 'all 0.2s',
          }}
        >
          전송
        </button>
      </div>
    </div>
  );
}
