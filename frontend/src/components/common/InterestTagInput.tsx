import { useState } from 'react';

const C = {
  bg: 'var(--bg-primary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

const PRESET_CATEGORIES = [
  '스마트폰', '노트북', '태블릿', 'TV/모니터', '가전',
  '게임/콘솔', '음향/이어폰', '카메라', '생활용품', '식품',
  '패션', '뷰티', '유아/키즈', '스포츠/아웃도어', '자동차용품',
];

const LEVEL_COLORS: Record<string, string> = {
  category: '#60a5fa',
  product: '#4ade80',
  model: '#f59e0b',
  general: '#a78bfa',
};
const LEVEL_ICONS: Record<string, string> = {
  category: '\uD83D\uDCC2',
  product: '\uD83D\uDCE6',
  model: '\uD83C\uDFF7\uFE0F',
  general: '\uD83D\uDCCC',
};

export interface InterestEntry {
  value: string;
  level: string;
  source: string;
}

interface Props {
  interests: InterestEntry[];
  onChange: (interests: InterestEntry[]) => void;
  maxCount: number;
  showPresets?: boolean;
}

export default function InterestTagInput({ interests, onChange, maxCount, showPresets = true }: Props) {
  const [customInput, setCustomInput] = useState('');

  const togglePreset = (cat: string) => {
    const idx = interests.findIndex(i => i.value === cat && i.level === 'category');
    if (idx >= 0) {
      onChange(interests.filter((_, i) => i !== idx));
    } else if (interests.length < maxCount) {
      onChange([...interests, { value: cat, level: 'category', source: 'preset' }]);
    }
  };

  const addCustom = () => {
    const val = customInput.trim();
    if (!val || interests.length >= maxCount || interests.some(i => i.value === val)) return;
    onChange([...interests, { value: val, level: 'general', source: 'custom' }]);
    setCustomInput('');
  };

  const remove = (idx: number) => onChange(interests.filter((_, i) => i !== idx));

  const inputStyle = {
    flex: 1, padding: '10px 14px', borderRadius: 8,
    background: C.bgEl, color: C.text,
    border: `1px solid ${C.border}`, fontSize: 13,
  };

  return (
    <div>
      {/* Preset categories */}
      {showPresets && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>
            카테고리 선택
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {PRESET_CATEGORIES.map(cat => {
              const isSelected = interests.some(i => i.value === cat && i.level === 'category');
              return (
                <button key={cat} onClick={() => togglePreset(cat)}
                  style={{
                    padding: '7px 14px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
                    background: isSelected ? 'rgba(96,165,250,0.15)' : C.bgEl,
                    border: `1px solid ${isSelected ? '#60a5fa' : C.border}`,
                    color: isSelected ? '#60a5fa' : C.textDim,
                    fontWeight: isSelected ? 700 : 400,
                  }}
                >
                  {isSelected && '\u2713 '}{cat}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Custom input */}
      <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>
        제품/모델 직접 입력
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        <input
          value={customInput}
          onChange={e => setCustomInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustom(); } }}
          placeholder="카테고리, 제품명 또는 모델명 입력"
          disabled={interests.length >= maxCount}
          style={inputStyle}
        />
        <button
          onClick={addCustom}
          disabled={interests.length >= maxCount || !customInput.trim()}
          style={{
            padding: '10px 16px', borderRadius: 8, border: 'none',
            background: interests.length < maxCount ? '#4ade80' : '#333',
            color: interests.length < maxCount ? '#000' : '#666',
            fontWeight: 700, cursor: 'pointer', fontSize: 13,
            opacity: (interests.length >= maxCount || !customInput.trim()) ? 0.4 : 1,
          }}
        >
          + 추가
        </button>
      </div>

      {/* Tags */}
      {interests.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
          {interests.map((item, i) => {
            const clr = LEVEL_COLORS[item.level] || '#a78bfa';
            const icon = LEVEL_ICONS[item.level] || '\uD83D\uDCCC';
            return (
              <span key={i} style={{
                padding: '6px 12px', borderRadius: 20, fontSize: 13,
                display: 'inline-flex', alignItems: 'center', gap: 6,
                background: `${clr}15`, border: `1px solid ${clr}`,
                color: clr,
              }}>
                {icon} {item.value}
                <span style={{ fontSize: 10, color: C.textDim }}>
                  ({item.source === 'preset' ? '프리셋' : '직접입력'})
                </span>
                <span onClick={() => remove(i)}
                  style={{ cursor: 'pointer', color: '#888', fontSize: 16, lineHeight: 1 }}>
                  \u2715
                </span>
              </span>
            );
          })}
        </div>
      )}

      <div style={{ color: C.textDim, fontSize: 12 }}>
        {interests.length}/{maxCount}
      </div>
    </div>
  );
}
