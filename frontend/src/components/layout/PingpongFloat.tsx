import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../contexts/AuthContext';
import { askPingpong } from '../../api/pingpongApi';
import { trackBehavior } from '../../utils/behaviorTracker';
import PingpongBallAnimation from '../effects/PingpongBallAnimation';

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

// yeokping://preview/{entity}/{id}/{topic} → frontend route
const DEEPLINK_RE = /yeokping:\/\/preview\/(reservation|offer|dealroom)\/(\d+)(?:\/(refund|payment|shipping|summary))?/g;

function deeplinkToRoute(entity: string, id: string, topic?: string): { path: string; label: string } {
  if (entity === 'reservation') {
    const t = topic || 'summary';
    const labels: Record<string, string> = { refund: '환불 확인', payment: '결제 확인', shipping: '배송 확인', summary: '예약 상세' };
    return { path: `/my-orders`, label: `주문 #${id} ${labels[t] || '상세'}` };
  }
  if (entity === 'offer') return { path: `/deal/${id}`, label: `오퍼 #${id} 보기` };
  if (entity === 'dealroom') return { path: `/deal/${id}`, label: `딜 #${id} 보기` };
  return { path: '/', label: '바로가기' };
}

function parseDeeplinks(text: string): { parts: Array<{ type: 'text' | 'link'; value: string; path?: string; label?: string }> } {
  const parts: Array<{ type: 'text' | 'link'; value: string; path?: string; label?: string }> = [];
  let lastIdx = 0;
  const re = new RegExp(DEEPLINK_RE.source, 'g');
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIdx) parts.push({ type: 'text', value: text.slice(lastIdx, m.index) });
    const { path, label } = deeplinkToRoute(m[1], m[2], m[3]);
    parts.push({ type: 'link', value: m[0], path, label });
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) parts.push({ type: 'text', value: text.slice(lastIdx) });
  return { parts };
}

// /path 패턴 감지 → 네비게이션 버튼 변환
const PATH_RE = /(\/[\w-]+(?:\/[\w-]+)*)/g;
const KNOWN_PATHS = new Set([
  '/', '/deals', '/search', '/my-deals', '/my-orders', '/completed-deals',
  '/my', '/mypage', '/spectating', '/notifications', '/points',
  '/deal/create', '/login', '/register', '/seller/dashboard',
  '/seller/offers', '/seller/orders', '/seller/reviews', '/seller/refunds',
  '/seller/settlements',
]);

function isNavigablePath(p: string): boolean {
  if (KNOWN_PATHS.has(p)) return true;
  if (/^\/deal\/\d+/.test(p)) return true;
  if (/^\/review\/write\/\d+/.test(p)) return true;
  return false;
}

function parsePathLinks(text: string): Array<{ type: 'text' | 'route'; value: string }> {
  const result: Array<{ type: 'text' | 'route'; value: string }> = [];
  let lastIdx = 0;
  const re = new RegExp(PATH_RE.source, 'g');
  let m;
  while ((m = re.exec(text)) !== null) {
    if (isNavigablePath(m[1])) {
      if (m.index > lastIdx) result.push({ type: 'text', value: text.slice(lastIdx, m.index) });
      result.push({ type: 'route', value: m[1] });
      lastIdx = m.index + m[0].length;
    }
  }
  if (lastIdx < text.length) result.push({ type: 'text', value: text.slice(lastIdx) });
  return result;
}

export default function PingpongFloat() {
  const [chatOpen, setChatOpen]   = useState(false);
  const [messages, setMessages]   = useState<ChatMessage[]>([]);
  const [input, setInput]         = useState('');
  const [isSending, setIsSending] = useState(false);
  const [typingId, setTypingId]   = useState<number | null>(null);
  const [ppSearchOpen, setPpSearchOpen] = useState(false);
  const [ppSearch, setPpSearch]   = useState('');
  const messagesEndRef            = useRef<HTMLDivElement>(null);
  const inputRef                  = useRef<HTMLInputElement>(null);
  const location                  = useLocation();
  const navigate                  = useNavigate();
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

    const isSeller = !!user?.seller;
    trackBehavior(isSeller ? 'SELLER_PINGPONG_CHAT' : 'PINGPONG_CHAT', {
      target_name: text.trim().slice(0, 100),
    });

    const role = user?.role || (user?.seller ? 'seller' : 'buyer');
    const result = await askPingpong(text.trim(), {
      page:    location.pathname,
      deal_id: currentDealId,
      user_id: user?.id,
      role,
    });

    const botText = result
      ? (typeof result === 'string'
          ? result
          : String(result.answer ?? result.message ?? result.text ?? ''))
      : '핑퐁이가 잠시 쉬고 있어요 🏓 잠시 후 다시 시도해주세요!';

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
          zIndex: 9999,
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
              style={{ position: 'fixed', inset: 0, zIndex: 9997 }}
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
                zIndex: 9998,
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    onClick={() => { setPpSearchOpen(v => !v); if (ppSearchOpen) setPpSearch(''); }}
                    style={{
                      width: 26, height: 26, borderRadius: '50%',
                      background: ppSearchOpen ? 'rgba(0,230,118,0.15)' : 'var(--bg-elevated)',
                      color: ppSearchOpen ? 'var(--accent-green)' : 'var(--text-muted)', fontSize: 12,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', border: 'none',
                    }}
                  >🔍</button>
                  <button
                    onClick={() => setChatOpen(false)}
                    style={{
                      width: 26, height: 26, borderRadius: '50%',
                      background: 'var(--bg-elevated)',
                      color: 'var(--text-muted)', fontSize: 12,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', border: 'none',
                    }}
                  >✕</button>
                </div>
              </div>

              {/* 검색바 */}
              {ppSearchOpen && (
                <div style={{ padding: '6px 12px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>🔍</span>
                  <input
                    value={ppSearch}
                    onChange={e => setPpSearch(e.target.value)}
                    placeholder="대화 검색..."
                    autoFocus
                    style={{
                      flex: 1, padding: '5px 10px', borderRadius: 8, fontSize: 12,
                      background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                      color: 'var(--text-primary)', outline: 'none',
                    }}
                  />
                  {ppSearch && (
                    <button onClick={() => setPpSearch('')} style={{
                      width: 20, height: 20, borderRadius: 6, background: 'rgba(255,255,255,0.08)',
                      border: 'none', color: 'var(--text-muted)', fontSize: 10, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>✕</button>
                  )}
                </div>
              )}

              {/* 메시지 영역 */}
              <div className="chat-scroll" style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {(ppSearch ? messages.filter(m => m.text.toLowerCase().includes(ppSearch.toLowerCase())) : messages).map(msg => (
                  <div key={msg.id} style={{ display: 'flex', justifyContent: msg.from === 'user' ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '80%',
                      padding: '9px 12px',
                      borderRadius: msg.from === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                      background: ppSearch && msg.text.toLowerCase().includes(ppSearch.toLowerCase())
                        ? 'rgba(255,235,59,0.18)'
                        : msg.from === 'user' ? 'var(--accent-green)' : 'var(--bg-elevated)',
                      color: msg.from === 'user' ? '#0a0a0f' : 'var(--text-secondary)',
                      fontSize: 13, lineHeight: 1.55, whiteSpace: 'pre-wrap',
                      border: ppSearch && msg.text.toLowerCase().includes(ppSearch.toLowerCase())
                        ? '1px solid rgba(255,235,59,0.4)' : 'none',
                    }}>
                      {msg.from === 'bot' && msg.id === typingId
                        ? <TypingText text={msg.text} onDone={() => setTypingId(null)} />
                        : msg.from === 'bot'
                        ? (() => {
                            const { parts } = parseDeeplinks(msg.text);
                            // Render deeplinks + /path route buttons
                            const renderTextWithPaths = (text: string, keyPrefix: string) => {
                              const pathParts = parsePathLinks(text);
                              if (pathParts.length === 1 && pathParts[0].type === 'text') return <span key={keyPrefix}>{text}</span>;
                              return pathParts.map((pp, j) => pp.type === 'route' ? (
                                <button key={`${keyPrefix}-p${j}`} onClick={() => { navigate(pp.value); setChatOpen(false); }} style={{
                                  display: 'inline-block', margin: '2px 4px', padding: '4px 12px', borderRadius: 12,
                                  background: '#4ade80', color: '#000', fontSize: 13,
                                  fontWeight: 700, border: 'none', cursor: 'pointer',
                                }}>📍 {pp.value} 바로가기</button>
                              ) : <span key={`${keyPrefix}-t${j}`}>{pp.value}</span>);
                            };
                            return (<>
                              {parts.map((p, i) => p.type === 'link' ? (
                                <button key={i} onClick={() => { navigate(p.path!); setChatOpen(false); }} style={{
                                  display: 'inline-block', margin: '2px 0', padding: '3px 8px', borderRadius: 6,
                                  background: 'rgba(0,176,255,0.15)', color: '#00b0ff', fontSize: 12,
                                  fontWeight: 600, border: 'none', cursor: 'pointer', textDecoration: 'none',
                                }}>{p.label}</button>
                              ) : renderTextWithPaths(p.value, `d${i}`))}
                            </>);
                          })()
                        : msg.text}
                    </div>
                  </div>
                ))}

                {/* 핑퐁이 탁구 로딩 애니메이션 */}
                {isSending && (
                  <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <PingpongBallAnimation active={true} size={40} />
                  </div>
                )}

                {/* 빠른 질문 */}
                {messages.length === 1 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {(user?.role === 'seller' || user?.role === 'both'
                      ? ['오퍼 어떻게 내?', '정산 언제 돼?', '배송 처리 방법', '수수료 얼마야?']
                      : QUICK_QUESTIONS
                    ).map(q => (
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

              {/* AI 면책 */}
              <div style={{ padding: '4px 12px', fontSize: 10, color: '#888', lineHeight: 1.4, borderTop: '1px solid var(--border-subtle)' }}>
                핑퐁이의 답변은 일반적인 안내이며, 법적·전문적 조언이 아닙니다.
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
