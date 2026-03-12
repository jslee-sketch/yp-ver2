import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FAQ_CATEGORIES } from '../data/faqData';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

export default function FAQPage() {
  const navigate = useNavigate();
  const [openIndex, setOpenIndex] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const filteredCategories = FAQ_CATEGORIES.map(cat => ({
    ...cat,
    items: cat.items.filter(item =>
      item.q.includes(search) || item.a.includes(search)
    )
  })).filter(cat => cat.items.length > 0);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>자주 묻는 질문</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 검색 */}
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="질문 검색..."
          style={{
            width: '100%', padding: '12px 16px', borderRadius: 12,
            background: C.bgCard, color: C.text,
            border: `1px solid ${C.border}`, fontSize: 14,
            marginBottom: 20, boxSizing: 'border-box',
            outline: 'none',
          }}
        />

        {filteredCategories.map(cat => (
          <div key={cat.category} style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 10 }}>
              {cat.icon} {cat.category}
            </div>
            <div style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderRadius: 14, overflow: 'hidden',
            }}>
              {cat.items.map((item, i) => {
                const key = `${cat.category}-${i}`;
                const isOpen = openIndex === key;
                return (
                  <div key={key}>
                    {i > 0 && <div style={{ height: 1, background: C.border, margin: '0 14px' }} />}
                    <div
                      onClick={() => setOpenIndex(isOpen ? null : key)}
                      style={{ padding: '13px 16px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                    >
                      <span style={{ fontSize: 13, color: C.text, flex: 1 }}>{item.q}</span>
                      <span style={{
                        color: C.green, fontSize: 16, fontWeight: 700,
                        transition: 'transform 0.2s',
                        transform: isOpen ? 'rotate(45deg)' : 'rotate(0deg)',
                        flexShrink: 0, marginLeft: 8,
                      }}>+</span>
                    </div>
                    {isOpen && (
                      <div style={{
                        padding: '0 16px 13px',
                        color: C.textSec, fontSize: 12, lineHeight: 1.7,
                      }}>{item.a}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {/* 핑퐁이 안내 */}
        <div style={{
          textAlign: 'center', padding: 20, marginTop: 8,
          background: `${C.green}10`, borderRadius: 14,
          border: `1px solid ${C.green}30`,
        }}>
          <div style={{ color: C.green, fontSize: 14, fontWeight: 700, marginBottom: 6 }}>
            찾는 답이 없나요?
          </div>
          <div style={{ color: C.textDim, fontSize: 12 }}>
            화면 오른쪽 하단 🏓 버튼을 눌러 핑퐁이에게 직접 물어보세요!
          </div>
        </div>
      </div>
    </div>
  );
}
