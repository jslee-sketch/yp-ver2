import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

interface EventDef {
  key: string;
  title: string;
  desc: string;
  default: { app: boolean; push: boolean; email: boolean };
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      style={{
        width: 36, height: 20, borderRadius: 10, border: 'none',
        background: checked ? '#4ade80' : '#333', cursor: 'pointer',
        position: 'relative', transition: 'background 0.2s',
      }}
    >
      <span style={{
        position: 'absolute', top: 2, left: checked ? 18 : 2,
        width: 16, height: 16, borderRadius: '50%',
        background: '#fff', transition: 'left 0.2s',
      }} />
    </button>
  );
}

export default function NotificationSettingsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const userId = user?.id || 0;
  const role = user?.role === 'seller' || user?.role === 'both' ? 'seller' : user?.role === 'actuator' ? 'actuator' : 'buyer';

  const [events, setEvents] = useState<Record<string, EventDef[]>>({});
  const [settings, setSettings] = useState<Record<string, { app: boolean; push: boolean; email: boolean }>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!userId) return;
    Promise.all([
      apiClient.get('/notification-settings/events', { params: { role } }),
      apiClient.get(`/notification-settings/${userId}`),
    ]).then(([evtRes, setRes]) => {
      setEvents(evtRes.data);
      setSettings(setRes.data);
    }).catch(console.error).finally(() => setLoading(false));
  }, [userId, role]);

  const getSetting = (key: string, channel: 'app' | 'push' | 'email', defaultVal: boolean) => {
    if (settings[key]) return settings[key][channel];
    return defaultVal;
  };

  const updateSetting = (key: string, channel: 'app' | 'push' | 'email', value: boolean) => {
    setSettings(prev => {
      const cur = prev[key] || { app: true, push: false, email: false };
      return { ...prev, [key]: { ...cur, [channel]: value } };
    });
  };

  const setAllChannel = (channel: 'app' | 'push' | 'email', value: boolean) => {
    const newSettings = { ...settings };
    for (const [, items] of Object.entries(events)) {
      for (const evt of items) {
        const cur = newSettings[evt.key] || { ...evt.default };
        newSettings[evt.key] = { ...cur, [channel]: value };
      }
    }
    setSettings(newSettings);
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      const items = Object.entries(settings).map(([event_type, channels]) => ({
        event_type,
        app: channels.app,
        push: channels.push,
        email: channels.email,
      }));
      await apiClient.post(`/notification-settings/${userId}`, { settings: items });
      alert('저장되었습니다!');
    } catch { alert('저장 실패'); }
    setSaving(false);
  };

  if (loading) return <div style={{ padding: 40, color: C.textDim }}>로딩 중...</div>;

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>알림 설정</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 700, margin: '0 auto' }}>
        {/* Bulk actions */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
          <button onClick={() => setAllChannel('app', true)} style={bulkBtn}>앱 전체 ON</button>
          <button onClick={() => setAllChannel('push', true)} style={bulkBtn}>푸시 전체 ON</button>
          <button onClick={() => setAllChannel('email', true)} style={bulkBtn}>이메일 전체 ON</button>
          <button onClick={() => { setAllChannel('app', false); setAllChannel('push', false); setAllChannel('email', false); }} style={{ ...bulkBtn, background: 'rgba(255,82,82,0.12)', color: '#ff5252', borderColor: '#ff5252' }}>전체 OFF</button>
        </div>

        {/* Event groups */}
        {Object.entries(events).map(([groupName, items]) => (
          <div key={groupName} style={{
            background: C.bgCard, borderRadius: 12, padding: 16,
            border: `1px solid ${C.border}`, marginBottom: 12,
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#4ade80', marginBottom: 12 }}>
              {groupName}
            </div>

            {/* Header */}
            <div style={{ display: 'flex', padding: '0 0 8px', borderBottom: `1px solid ${C.border}` }}>
              <div style={{ flex: 1, color: C.textDim, fontSize: 11 }}>이벤트</div>
              <div style={{ width: 50, textAlign: 'center', color: C.textDim, fontSize: 11 }}>앱</div>
              <div style={{ width: 50, textAlign: 'center', color: C.textDim, fontSize: 11 }}>푸시</div>
              <div style={{ width: 50, textAlign: 'center', color: C.textDim, fontSize: 11 }}>이메일</div>
            </div>

            {items.map((evt: EventDef) => (
              <div key={evt.key} style={{
                display: 'flex', alignItems: 'center',
                padding: '10px 0', borderBottom: `1px solid rgba(255,255,255,0.03)`,
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ color: C.text, fontSize: 13 }}>{evt.title}</div>
                  <div style={{ color: C.textDim, fontSize: 10, marginTop: 2 }}>{evt.desc}</div>
                </div>
                <div style={{ width: 50, display: 'flex', justifyContent: 'center' }}>
                  <Toggle
                    checked={getSetting(evt.key, 'app', evt.default.app)}
                    onChange={v => updateSetting(evt.key, 'app', v)}
                  />
                </div>
                <div style={{ width: 50, display: 'flex', justifyContent: 'center' }}>
                  <Toggle
                    checked={getSetting(evt.key, 'push', evt.default.push)}
                    onChange={v => updateSetting(evt.key, 'push', v)}
                  />
                </div>
                <div style={{ width: 50, display: 'flex', justifyContent: 'center' }}>
                  <Toggle
                    checked={getSetting(evt.key, 'email', evt.default.email)}
                    onChange={v => updateSetting(evt.key, 'email', v)}
                  />
                </div>
              </div>
            ))}
          </div>
        ))}

        <button
          onClick={saveSettings}
          disabled={saving}
          style={{
            width: '100%', padding: 14, borderRadius: 12, border: 'none',
            background: saving ? '#4ade8055' : '#4ade80', color: '#000',
            fontWeight: 700, fontSize: 15, cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? '저장 중...' : '설정 저장'}
        </button>
      </div>
    </div>
  );
}

const bulkBtn: React.CSSProperties = {
  padding: '6px 12px', borderRadius: 8, fontSize: 11, fontWeight: 600,
  cursor: 'pointer', background: 'rgba(74,222,128,0.1)',
  border: '1px solid rgba(74,222,128,0.3)', color: '#4ade80',
};
