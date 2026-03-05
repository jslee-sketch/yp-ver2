import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../contexts/AuthContext';
import { askPingpong } from '../../api/pingpongApi';

interface ChatMessage {
  id: number;
  from: 'bot' | 'user';
  text: string;
}

const PP_MESSAGES: Record<string, string> = {
  '/login':       '간편하게 가입하고 시작해요!',
  '/register':    '역핑에 오신 걸 환영해요! 😊',
  '/':            '오늘의 핫딜 보여드릴까요? 🔥',
  '/deals':       '딜을 찾아보세요!',
  '/deal/create': '어떤 상품을 원하세요? 🎯',
  '/search':      '무엇을 찾고 있나요?',
  '/my-deals':        '내 딜 현황이에요! 🔥',
  '/my-orders':       '참여/결제/배송 상태를 추적하세요 📦',
  '/completed-deals': '과거 거래 가격을 참고해보세요! 📊',
  '/my':              '내 활동을 한눈에! 참여내역, 딜, 오퍼를 확인하세요 📋',
  '/mypage':          '내 활동을 한눈에! 참여내역, 딜, 오퍼를 확인하세요 📋',
  '/spectating':      '예측의 달인! 🏆',
  '/notifications':   '새 소식을 확인하세요! 🔔',
  '/points':          '포인트 적립 내역이에요! 💰',
};

function getPageMsg(pathname: string): string {
  if (pathname.includes('/offer/create'))       return '판매자님, 좋은 조건으로 오퍼를 내보세요! 💰';
  if (pathname.includes('/join'))              return '이 딜에 함께 참여해보세요! 🤝';
  if (pathname.startsWith('/completed-deals/')) return '이 딜의 상세 가격 분석이에요! 📈';
  if (pathname.startsWith('/deal/'))            return '이 딜의 가격 여정을 확인하세요! 📊';
  return PP_MESSAGES[pathname] ?? '무엇이든 물어보세요! 🤖';
}

function TypingText({ text, onDone }: { text: string; onDone?: () => void }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (shown >= text.length) { onDone?.(); return; }
    const t = setTimeout(() => setShown(s => s + 1), 18);
    return () => clearTimeout(t);
  }, [shown, text, onDone]);
  return <>{text.slice(0, shown)}{shown < text.length ? <span className="blink-fast">|</span> : null}</>;
}

const QUICK_QUESTIONS = [
  '지금 제일 좋은 딜 추천해줘',
  '내 포인트 얼마야?',
  '환불 정책이 뭐야?',
  '관전자 예측 어떻게 해?',
];

export default function PingpongFloat() {
  const [chatOpen, setChatOpen]   = useState(false);
  const [messages, setMessages]   = useState<ChatMessage[]>([]);
  const [input, setInput]         = useState('');
  const [isSending, setIsSending] = useState(false);
  const [typingId, setTypingId]   = useState<number | null>(null);
  const messagesEndRef            = useRef<HTMLDivElement>(null);
  const inputRef                  = useRef<HTMLInputElement>(null);
  const location                  = useLocation();
  const { user }                  = useAuth();

  // 현재 딜 ID 추출 (URL /deal/:id)
  const dealIdMatch = location.pathname.match(/^\/deal\/(\d+)/);
  const currentDealId = dealIdMatch ? Number(dealIdMatch[1]) : undefined;

  // 페이지 이동 시 닫기 + 페이지별 인사
  useEffect(() => {
    setChatOpen(false);
    const msgId = Date.now();
    setMessages([{ id: msgId, from: 'bot', text: getPageMsg(location.pathname) }]);
    setTypingId(msgId);
  }, [location.pathname]);

  // Escape 키로 닫기
  useEffect(() => {
    if (!chatOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setChatOpen(false); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [chatOpen]);

  // 새 메시지 시 스크롤 + 채팅 열릴 때 포커스
  useEffect(() => {
    if (chatOpen) {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        inputRef.current?.focus();
      }, 100);
    }
  }, [messages, chatOpen]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isSending) return;
    const userMsg: ChatMessage = { id: Date.now(), from: 'user', text: text.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsSending(true);

    const result = await askPingpong(text.trim(), {
      page:    location.pathname,
      deal_id: currentDealId,
      user_id: user?.id,
    });

    const botText = result
      ? (typeof result === 'string'
          ? result
          : String(result.answer ?? result.message ?? result.text ?? ''))
      : '네트워크 연결을 확인해 주세요. 다시 질문하시면 도움을 드릴게요!';

    const botId = Date.now() + 1;
    setMessages(prev => [...prev, { id: botId, from: 'bot', text: botText }]);
    setTypingId(botId);
    setIsSending(false);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const hideNav =
    ['/login', '/register', '/deal/create'].includes(location.pathname) ||
    location.pathname.includes('/offer/create');
  const floatBottom = hideNav ? 32 : 90;

  return (
    <>
      {/* 플로팅 버튼 */}
      <motion.button
        onClick={() => setChatOpen(p => !p)}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.95 }}
        style={{
          position: 'fixed',
          bottom: floatBottom,
          right: 24,
          width: 52,
          height: 52,
          borderRadius: '50%',
          background: chatOpen ? 'var(--accent-green)' : 'var(--bg-secondary)',
          border: chatOpen
            ? '1px solid rgba(0,230,118,0.5)'
            : '1px solid rgba(255,183,77,0.3)',
          boxShadow: '0 4px 20px rgba(0,0,0,0.45)',
          fontSize: chatOpen ? 18 : 24,
          zIndex: 999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          transition: 'background 0.2s, border 0.2s, font-size 0.15s',
        }}
        aria-label="핑퐁이에게 질문하기"
      >
        {chatOpen ? '✕' : '🤖'}
      </motion.button>

      <AnimatePresence>
        {chatOpen && (
          <>
            {/* 외부 클릭 닫기 */}
            <div
              onClick={() => setChatOpen(false)}
              style={{ position: 'fixed', inset: 0, zIndex: 997 }}
            />

            {/* 채팅 패널 */}
            <motion.div
              initial={{ scale: 0.9, y: 20, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.88, y: 16, opacity: 0 }}
              transition={{ type: 'spring', damping: 24, stiffness: 360 }}
              onClick={e => e.stopPropagation()}
              style={{
                position: 'fixed',
                bottom: floatBottom + 64,
                right: 24,
                width: 'calc(100vw - 48px)',
                maxWidth: 360,
                height: 420,
                background: 'var(--bg-secondary)',
                borderRadius: 20,
                boxShadow: '0 8px 40px rgba(0,0,0,0.55)',
                border: '1px solid rgba(0,230,118,0.15)',
                zIndex: 998,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              {/* 헤더 */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '14px 16px',
                borderBottom: '1px solid var(--border-subtle)',
                flexShrink: 0,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 22 }}>🤖</span>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent-orange)' }}>핑퐁이</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-green)' }} />
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>온라인</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setChatOpen(false)}
                  style={{
                    width: 26, height: 26, borderRadius: '50%',
                    background: 'var(--bg-elevated)',
                    color: 'var(--text-muted)', fontSize: 12,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer',
                  }}
                >✕</button>
              </div>

              {/* 메시지 영역 */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {messages.map(msg => (
                  <div key={msg.id} style={{ display: 'flex', justifyContent: msg.from === 'user' ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '80%',
                      padding: '9px 12px',
                      borderRadius: msg.from === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                      background: msg.from === 'user' ? 'var(--accent-green)' : 'var(--bg-elevated)',
                      color: msg.from === 'user' ? '#0a0a0f' : 'var(--text-secondary)',
                      fontSize: 13, lineHeight: 1.55, whiteSpace: 'pre-wrap',
                    }}>
                      {msg.from === 'bot' && msg.id === typingId
                        ? <TypingText text={msg.text} onDone={() => setTypingId(null)} />
                        : msg.text}
                    </div>
                  </div>
                ))}

                {/* 빠른 질문 */}
                {messages.length === 1 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {QUICK_QUESTIONS.map(q => (
                      <button
                        key={q}
                        onClick={() => void sendMessage(q)}
                        style={{
                          textAlign: 'left', padding: '8px 12px',
                          background: 'var(--bg-tertiary)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 10, fontSize: 12,
                          color: 'var(--text-secondary)', cursor: 'pointer',
                        }}
                      >
                        💬 {q}
                      </button>
                    ))}
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* 입력 */}
              <div style={{
                display: 'flex', gap: 8,
                padding: '10px 12px',
                borderTop: '1px solid var(--border-subtle)',
                flexShrink: 0,
              }}>
                <input
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') void sendMessage(input); }}
                  type="text"
                  placeholder="질문 입력..."
                  autoFocus
                  disabled={isSending}
                  style={{
                    flex: 1, padding: '9px 12px', fontSize: 13,
                    borderRadius: 10,
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    opacity: isSending ? 0.6 : 1,
                  }}
                />
                <button
                  onClick={() => void sendMessage(input)}
                  disabled={isSending || !input.trim()}
                  style={{
                    padding: '9px 14px',
                    background: isSending || !input.trim() ? 'rgba(255,255,255,0.1)' : 'var(--accent-green)',
                    color: isSending || !input.trim() ? 'rgba(255,255,255,0.4)' : '#0a0a0f',
                    borderRadius: 10,
                    fontSize: 13, fontWeight: 700,
                    cursor: isSending || !input.trim() ? 'default' : 'pointer',
                  }}
                >{isSending ? '...' : '전송'}</button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
