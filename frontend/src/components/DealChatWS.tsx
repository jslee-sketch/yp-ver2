import { useState, useEffect, useRef, useCallback } from 'react';

interface ChatMessage {
  type: string;
  user_id?: number;
  nickname?: string;
  role?: string;
  message?: string;
  timestamp?: string;
  chat_id?: number;
  online_count?: number;
}

interface DealChatWSProps {
  dealId: number;
  token: string;
  currentUserId: number;
}

const BASE_WS = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
  window.location.host;

export default function DealChatWS({ dealId, token, currentUserId }: DealChatWSProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [typing, setTyping] = useState<string[]>([]);
  const [onlineCount, setOnlineCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // WebSocket 연결
  useEffect(() => {
    const wsUrl = `${BASE_WS}/ws/chat/${dealId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ token }));
    };

    ws.onmessage = (event) => {
      const data: ChatMessage = JSON.parse(event.data);

      switch (data.type) {
        case 'AUTH_OK':
          setConnected(true);
          if (data.online_count !== undefined) setOnlineCount(data.online_count);
          break;
        case 'CHAT':
        case 'SYSTEM':
          setMessages(prev => [...prev, data]);
          break;
        case 'TYPING':
          if (data.nickname) {
            setTyping(prev => [...new Set([...prev, data.nickname!])]);
          }
          break;
        case 'STOP_TYPING':
          setTyping(prev => prev.filter(n => n !== data.nickname));
          break;
        case 'ONLINE_LIST':
          if (data.online_count !== undefined) setOnlineCount(data.online_count);
          break;
        case 'ERROR':
          console.error('[WS Chat] Error:', data.message);
          break;
      }

      if (data.online_count !== undefined && data.type !== 'AUTH_OK') {
        setOnlineCount(data.online_count);
      }
    };

    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    return () => {
      ws.close();
    };
  }, [dealId, token]);

  // 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 메시지 전송
  const sendMessage = useCallback(() => {
    if (!input.trim() || !wsRef.current || !connected) return;
    wsRef.current.send(JSON.stringify({ type: 'CHAT', message: input.trim() }));
    setInput('');
    wsRef.current.send(JSON.stringify({ type: 'STOP_TYPING' }));
  }, [input, connected]);

  // 입력 중 표시
  const handleTyping = useCallback(() => {
    if (!wsRef.current || !connected) return;
    wsRef.current.send(JSON.stringify({ type: 'TYPING' }));
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => {
      wsRef.current?.send(JSON.stringify({ type: 'STOP_TYPING' }));
    }, 2000);
  }, [connected]);

  const styles = {
    container: {
      display: 'flex', flexDirection: 'column' as const,
      height: '400px', background: 'var(--bg-secondary, #0f0f1a)',
      borderRadius: '12px', overflow: 'hidden',
      border: '1px solid var(--border, #2a2a4a)',
    },
    header: {
      padding: '10px 14px', background: 'var(--bg-tertiary, #1a1a2e)',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      borderBottom: '1px solid var(--border, #2a2a4a)',
    },
    headerTitle: { color: 'var(--text-primary, #e0e0e0)', fontWeight: 'bold' as const, fontSize: '14px' },
    statusDot: {
      width: '8px', height: '8px', borderRadius: '50%',
      background: connected ? '#4ade80' : '#ef4444',
    },
    statusText: { color: 'var(--text-muted, #888)', fontSize: '12px' },
    messageArea: {
      flex: 1, overflow: 'auto', padding: '12px',
      display: 'flex', flexDirection: 'column' as const, gap: '8px',
    },
    systemMsg: { textAlign: 'center' as const, color: 'var(--text-muted, #666)', fontSize: '12px' },
    myBubble: {
      background: 'var(--accent, #4ade80)', color: '#000',
      padding: '8px 12px', borderRadius: '12px',
      fontSize: '14px', lineHeight: '1.4',
    },
    otherBubble: {
      background: 'var(--bg-tertiary, #1a1a2e)', color: 'var(--text-primary, #e0e0e0)',
      padding: '8px 12px', borderRadius: '12px',
      fontSize: '14px', lineHeight: '1.4',
    },
    senderName: { color: 'var(--accent, #4ade80)', fontSize: '11px', marginBottom: '2px' },
    timestamp: { color: 'var(--text-muted, #555)', fontSize: '10px', marginTop: '2px', textAlign: 'right' as const },
    inputArea: {
      padding: '10px', borderTop: '1px solid var(--border, #2a2a4a)',
      display: 'flex', gap: '8px',
    },
    input: {
      flex: 1, padding: '10px 14px', borderRadius: '20px',
      border: '1px solid var(--border, #2a2a4a)',
      background: 'var(--bg-tertiary, #1a1a2e)',
      color: 'var(--text-primary, #e0e0e0)', outline: 'none',
      fontSize: '14px',
    },
  };

  return (
    <div style={styles.container}>
      {/* 헤더 */}
      <div style={styles.header}>
        <span style={styles.headerTitle}>딜방 채팅</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={styles.statusDot} />
          <span style={styles.statusText}>{onlineCount}명 접속</span>
        </div>
      </div>

      {/* 메시지 영역 */}
      <div style={styles.messageArea}>
        {messages.map((msg, i) =>
          msg.type === 'SYSTEM' ? (
            <div key={i} style={styles.systemMsg}>{msg.message}</div>
          ) : (
            <div key={i} style={{
              alignSelf: msg.user_id === currentUserId ? 'flex-end' : 'flex-start',
              maxWidth: '70%',
            }}>
              {msg.user_id !== currentUserId && (
                <div style={styles.senderName}>{msg.nickname}</div>
              )}
              <div style={msg.user_id === currentUserId ? styles.myBubble : styles.otherBubble}>
                {msg.message}
              </div>
              <div style={styles.timestamp}>
                {msg.timestamp
                  ? new Date(msg.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
                  : ''}
              </div>
            </div>
          )
        )}

        {typing.length > 0 && (
          <div style={{ color: 'var(--text-muted, #888)', fontSize: '12px', fontStyle: 'italic' }}>
            {typing.join(', ')}님이 입력 중...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 입력 영역 */}
      <div style={styles.inputArea}>
        <input
          value={input}
          onChange={e => { setInput(e.target.value); handleTyping(); }}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          placeholder={connected ? '메시지를 입력하세요...' : '연결 중...'}
          disabled={!connected}
          style={styles.input}
        />
        <button
          onClick={sendMessage}
          disabled={!connected || !input.trim()}
          style={{
            padding: '10px 16px', borderRadius: '20px',
            background: input.trim() && connected ? 'var(--accent, #4ade80)' : 'var(--bg-tertiary, #333)',
            color: input.trim() && connected ? '#000' : 'var(--text-muted, #666)',
            border: 'none', fontWeight: 'bold',
            cursor: input.trim() && connected ? 'pointer' : 'not-allowed',
            fontSize: '14px',
          }}
        >
          전송
        </button>
      </div>
    </div>
  );
}
