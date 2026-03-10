import { useState } from 'react';

interface DateRangeFilterProps {
  onFilter: (dateFrom: string, dateTo: string) => void;
  style?: React.CSSProperties;
}

const C = {
  cyan: '#00e5ff',
  card: 'var(--bg-elevated)',
  border: 'var(--border-subtle)',
  text: 'var(--text-primary)',
  textSec: 'var(--text-muted)',
};

const presets: { label: string; days: number | null }[] = [
  { label: '오늘', days: 0 },
  { label: '7일', days: 7 },
  { label: '30일', days: 30 },
  { label: '90일', days: 90 },
  { label: '1년', days: 365 },
  { label: '전체', days: null },
];

function toISO(d: Date) {
  return d.toISOString().split('T')[0];
}

export default function DateRangeFilter({ onFilter, style }: DateRangeFilterProps) {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [active, setActive] = useState<string>('전체');

  const applyPreset = (label: string, days: number | null) => {
    setActive(label);
    if (days === null) {
      setDateFrom('');
      setDateTo('');
      onFilter('', '');
    } else {
      const to = new Date();
      const from = new Date();
      if (days > 0) from.setDate(from.getDate() - days);
      const f = toISO(from);
      const t = toISO(to);
      setDateFrom(f);
      setDateTo(t);
      onFilter(f, t);
    }
  };

  const handleManual = () => {
    setActive('');
    onFilter(dateFrom, dateTo);
  };

  const inputStyle: React.CSSProperties = {
    padding: '6px 8px',
    borderRadius: 6,
    border: `1px solid ${C.border}`,
    background: C.card,
    color: C.text,
    fontSize: 12,
    width: 130,
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', ...style }}>
      {presets.map(p => (
        <button
          key={p.label}
          onClick={() => applyPreset(p.label, p.days)}
          style={{
            padding: '4px 10px',
            borderRadius: 14,
            border: 'none',
            cursor: 'pointer',
            fontSize: 11,
            fontWeight: 600,
            background: active === p.label ? C.cyan : C.card,
            color: active === p.label ? '#000' : C.textSec,
          }}
        >
          {p.label}
        </button>
      ))}
      <input
        type="date"
        value={dateFrom}
        onChange={e => { setDateFrom(e.target.value); setActive(''); }}
        style={inputStyle}
      />
      <span style={{ color: C.textSec, fontSize: 12 }}>~</span>
      <input
        type="date"
        value={dateTo}
        onChange={e => { setDateTo(e.target.value); setActive(''); }}
        style={inputStyle}
      />
      <button
        onClick={handleManual}
        style={{
          padding: '5px 10px',
          borderRadius: 6,
          border: `1px solid ${C.border}`,
          background: C.card,
          color: C.text,
          fontSize: 11,
          cursor: 'pointer',
        }}
      >
        적용
      </button>
    </div>
  );
}
