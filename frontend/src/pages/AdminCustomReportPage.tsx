import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252',
  purple: '#7c4dff', blue: '#60a5fa',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

const CATEGORY_LABELS: Record<string, string> = {
  seller: '판매자', buyer: '구매자', actuator: '액추에이터',
  deal: '딜', offer: '오퍼', reservation: '주문',
  settlement: '정산', tax: '세금계산서', review: '리뷰',
};

const CATEGORY_COLORS: Record<string, string> = {
  seller: '#00e676', buyer: '#60a5fa', actuator: '#ff9100',
  deal: '#00e5ff', offer: '#7c4dff', reservation: '#ff6d00',
  settlement: '#4fc3f7', tax: '#e040fb', review: '#ffd600',
};

interface FieldItem {
  key: string;
  label: string;
  type: string;
}

interface Template {
  id: number;
  name: string;
  fields: string[];
  created_at: string;
}

export default function AdminCustomReportPage() {
  const [fieldRegistry, setFieldRegistry] = useState<Record<string, FieldItem[]>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateName, setTemplateName] = useState('');
  const [limit, setLimit] = useState(200);

  useEffect(() => {
    apiClient.get(API.ADMIN.CUSTOM_REPORT_FIELDS).then(r => setFieldRegistry(r.data)).catch(() => {});
    apiClient.get(API.ADMIN.CUSTOM_REPORT_TEMPLATES).then(r => setTemplates(r.data)).catch(() => {});
  }, []);

  const toggleField = (key: string) => {
    setSelected(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };

  const moveField = (idx: number, dir: -1 | 1) => {
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= selected.length) return;
    const arr = [...selected];
    [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]];
    setSelected(arr);
  };

  const removeField = (key: string) => setSelected(prev => prev.filter(k => k !== key));

  const runQuery = async (format: 'json' | 'csv' = 'json') => {
    if (!selected.length) return alert('필드를 1개 이상 선택하세요.');
    setLoading(true);
    try {
      if (format === 'csv') {
        const r = await apiClient.post(API.ADMIN.CUSTOM_REPORT_QUERY, { fields: selected, limit, format: 'csv' }, { responseType: 'blob' });
        const url = URL.createObjectURL(new Blob([r.data as BlobPart]));
        const a = document.createElement('a');
        a.href = url;
        a.download = `report_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        const r = await apiClient.post(API.ADMIN.CUSTOM_REPORT_QUERY, { fields: selected, limit, format: 'json' });
        setResults(r.data);
      }
    } catch (e: any) {
      const msg = e.response?.data?.detail || '쿼리 실행 실패';
      alert(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    setLoading(false);
  };

  const saveTemplate = async () => {
    if (!templateName.trim() || !selected.length) return;
    try {
      const r = await apiClient.post(API.ADMIN.CUSTOM_REPORT_TEMPLATES, { name: templateName.trim(), fields: selected });
      setTemplates(prev => [r.data, ...prev]);
      setTemplateName('');
    } catch { alert('저장 실패'); }
  };

  const loadTemplate = (t: Template) => {
    setSelected(t.fields);
    setResults(null);
  };

  const deleteTemplate = async (id: number) => {
    if (!confirm('삭제하시겠습니까?')) return;
    try {
      await apiClient.delete(API.ADMIN.CUSTOM_REPORT_TEMPLATE(id));
      setTemplates(prev => prev.filter(t => t.id !== id));
    } catch {}
  };

  // Flat field lookup
  const allFields: Record<string, FieldItem & { category: string }> = {};
  for (const [cat, items] of Object.entries(fieldRegistry)) {
    for (const item of items) {
      allFields[item.key] = { ...item, category: cat };
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>
        커스텀 리포트 빌더
      </h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* Left: Field Picker */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>필드 선택</div>
          <div style={{ maxHeight: 400, overflowY: 'auto' }}>
            {Object.entries(fieldRegistry).map(([cat, items]) => (
              <div key={cat} style={{ marginBottom: 12 }}>
                <div style={{
                  fontSize: 11, fontWeight: 700, color: CATEGORY_COLORS[cat] || C.textSec,
                  textTransform: 'uppercase', marginBottom: 4, letterSpacing: '0.5px',
                }}>
                  {CATEGORY_LABELS[cat] || cat}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {items.map(f => {
                    const isSelected = selected.includes(f.key);
                    return (
                      <button
                        key={f.key}
                        onClick={() => toggleField(f.key)}
                        title={`${f.key} (${f.type})`}
                        style={{
                          padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600,
                          cursor: 'pointer', border: 'none', transition: 'all 0.15s',
                          background: isSelected ? `${CATEGORY_COLORS[cat] || C.cyan}33` : 'rgba(255,255,255,0.04)',
                          color: isSelected ? (CATEGORY_COLORS[cat] || C.cyan) : C.textSec,
                          outline: isSelected ? `1px solid ${CATEGORY_COLORS[cat] || C.cyan}` : 'none',
                        }}
                      >
                        {f.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Selected + Templates */}
        <div>
          {/* Selected fields */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 8 }}>
              선택된 필드 ({selected.length})
              <span style={{ fontSize: 11, fontWeight: 400, color: C.textSec, marginLeft: 8 }}>
                첫 번째 = 기본키(정렬 기준)
              </span>
            </div>
            {selected.length === 0 ? (
              <div style={{ fontSize: 12, color: C.textSec, padding: '20px 0', textAlign: 'center' }}>
                왼쪽에서 필드를 클릭하세요
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
                {selected.map((key, idx) => {
                  const f = allFields[key];
                  const catColor = f ? CATEGORY_COLORS[f.category] || C.cyan : C.cyan;
                  return (
                    <div key={key} style={{
                      display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px',
                      background: idx === 0 ? `${catColor}15` : 'transparent',
                      borderRadius: 6, borderLeft: idx === 0 ? `3px solid ${catColor}` : 'none',
                    }}>
                      <span style={{ fontSize: 11, color: catColor, fontWeight: 600, minWidth: 16 }}>{idx + 1}</span>
                      <span style={{ fontSize: 12, color: C.text, flex: 1 }}>{f?.label || key}</span>
                      <button onClick={() => moveField(idx, -1)} disabled={idx === 0}
                        style={{ background: 'none', border: 'none', color: C.textSec, cursor: 'pointer', fontSize: 11, padding: '2px 4px', opacity: idx === 0 ? 0.3 : 1 }}>
                        &#9650;
                      </button>
                      <button onClick={() => moveField(idx, 1)} disabled={idx === selected.length - 1}
                        style={{ background: 'none', border: 'none', color: C.textSec, cursor: 'pointer', fontSize: 11, padding: '2px 4px', opacity: idx === selected.length - 1 ? 0.3 : 1 }}>
                        &#9660;
                      </button>
                      <button onClick={() => removeField(key)}
                        style={{ background: 'none', border: 'none', color: C.red, cursor: 'pointer', fontSize: 12, padding: '2px 4px', fontWeight: 700 }}>
                        &#10005;
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Templates */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 8 }}>템플릿</div>
            <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
              <input
                value={templateName}
                onChange={e => setTemplateName(e.target.value)}
                placeholder="템플릿 이름"
                style={{ flex: 1, padding: '6px 10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.text, fontSize: 12 }}
              />
              <button onClick={saveTemplate} disabled={!templateName.trim() || !selected.length}
                style={{ padding: '6px 14px', borderRadius: 8, border: 'none', background: C.green, color: '#000', fontWeight: 600, fontSize: 12, cursor: 'pointer', opacity: (!templateName.trim() || !selected.length) ? 0.4 : 1 }}>
                저장
              </button>
            </div>
            <div style={{ maxHeight: 140, overflowY: 'auto' }}>
              {templates.length === 0 ? (
                <div style={{ fontSize: 11, color: C.textSec, textAlign: 'center', padding: 8 }}>저장된 템플릿 없음</div>
              ) : templates.map(t => (
                <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0', borderBottom: `1px solid ${C.border}` }}>
                  <span
                    onClick={() => loadTemplate(t)}
                    style={{ flex: 1, fontSize: 12, color: C.cyan, cursor: 'pointer', fontWeight: 600 }}
                  >
                    {t.name}
                  </span>
                  <span style={{ fontSize: 10, color: C.textSec }}>{t.fields.length}fields</span>
                  <button onClick={() => deleteTemplate(t.id)}
                    style={{ background: 'none', border: 'none', color: C.red, cursor: 'pointer', fontSize: 11, padding: '2px 4px' }}>
                    &#10005;
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <button
          onClick={() => runQuery('json')}
          disabled={loading || !selected.length}
          style={{
            padding: '10px 24px', borderRadius: 10, border: 'none',
            background: C.cyan, color: '#000', fontWeight: 700, fontSize: 14,
            cursor: (loading || !selected.length) ? 'not-allowed' : 'pointer',
            opacity: (loading || !selected.length) ? 0.5 : 1,
          }}
        >
          {loading ? '실행 중...' : '쿼리 실행'}
        </button>
        <button
          onClick={() => runQuery('csv')}
          disabled={loading || !selected.length}
          style={{
            padding: '10px 20px', borderRadius: 10, border: 'none',
            background: C.purple, color: '#fff', fontWeight: 700, fontSize: 13,
            cursor: (loading || !selected.length) ? 'not-allowed' : 'pointer',
            opacity: (loading || !selected.length) ? 0.5 : 1,
          }}
        >
          CSV 다운로드
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 8 }}>
          <span style={{ fontSize: 12, color: C.textSec }}>Limit:</span>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))}
            style={{ padding: '6px 10px', borderRadius: 8, border: `1px solid ${C.border}`, background: '#1a1a2e', color: '#e0e0e0', fontSize: 12 }}>
            {[50, 100, 200, 500, 1000].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        {results && <span style={{ marginLeft: 'auto', fontSize: 12, color: C.textSec }}>{results.total}건</span>}
      </div>

      {/* Results Table */}
      {results && results.rows && (
        <div style={{ overflowX: 'auto', borderRadius: 12, border: `1px solid ${C.border}` }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: '#1a1a2e' }}>
                {results.columns.map((col: string, i: number) => (
                  <th key={i} style={{ padding: '8px 10px', color: C.textSec, textAlign: 'left', fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.rows.map((row: Record<string, any>, ri: number) => (
                <tr key={ri} style={{ borderTop: `1px solid ${C.border}` }}>
                  {results.keys.map((key: string, ci: number) => {
                    const val = row[key];
                    const meta = allFields[key];
                    const isId = meta?.type === 'int' && meta?.label?.includes('ID');
                    return (
                      <td key={ci} style={{
                        padding: '7px 10px',
                        color: ci === 0 ? C.cyan : isId ? C.blue : C.text,
                        fontWeight: ci === 0 ? 600 : 400,
                        whiteSpace: 'nowrap',
                        maxWidth: 200,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }} title={val ?? ''}>
                        {val ?? '-'}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {results.rows.length === 0 && (
                <tr><td colSpan={results.columns.length} style={{ padding: 40, textAlign: 'center', color: C.textSec }}>결과 없음</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {!results && !loading && (
        <div style={{ padding: 60, textAlign: 'center', color: C.textSec }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>&#128202;</div>
          <div style={{ fontSize: 15 }}>필드를 선택하고 쿼리를 실행하세요</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>첫 번째 필드가 기본키(정렬 기준)가 됩니다</div>
        </div>
      )}
    </div>
  );
}
