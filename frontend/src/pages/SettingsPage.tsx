import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { soundEffects } from '../services/soundEffects';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

function ToggleRow({ label, desc, value, onChange }: {
  label: string; desc?: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 0', borderBottom: `1px solid ${C.border}`,
    }}>
      <div>
        <div style={{ fontSize: 13, color: C.text }}>{label}</div>
        {desc && <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{desc}</div>}
      </div>
      <button
        onClick={() => onChange(!value)}
        style={{
          width: 44, height: 24, borderRadius: 12, padding: 2,
          background: value ? C.green : C.bgEl,
          border: `1px solid ${value ? C.green : C.border}`,
          cursor: 'pointer', position: 'relative',
          transition: 'background 0.2s',
        }}
      >
        <div style={{
          width: 18, height: 18, borderRadius: '50%',
          background: '#fff',
          transform: value ? 'translateX(20px)' : 'translateX(0)',
          transition: 'transform 0.2s',
        }} />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const [isDark, setIsDark] = useState(() =>
    document.documentElement.getAttribute('data-theme') !== 'light'
  );
  const [pushEnabled, setPushEnabled] = useState(() =>
    localStorage.getItem('yp_push_enabled') !== 'false'
  );
  const [dealAlerts, setDealAlerts] = useState(() =>
    localStorage.getItem('yp_deal_alerts') !== 'false'
  );
  const [priceAlerts, setPriceAlerts] = useState(() =>
    localStorage.getItem('yp_price_alerts') !== 'false'
  );
  const [soundEnabled, setSoundEnabled] = useState(() =>
    soundEffects.isEnabled()
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDark ? '' : 'light');
    localStorage.setItem('yp_theme', isDark ? 'dark' : 'light');
  }, [isDark]);

  useEffect(() => { localStorage.setItem('yp_push_enabled', String(pushEnabled)); }, [pushEnabled]);
  useEffect(() => { localStorage.setItem('yp_deal_alerts', String(dealAlerts)); }, [dealAlerts]);
  useEffect(() => { localStorage.setItem('yp_price_alerts', String(priceAlerts)); }, [priceAlerts]);
  useEffect(() => { soundEffects.setEnabled(soundEnabled); }, [soundEnabled]);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>설정</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '4px 16px', marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, paddingTop: 14, marginBottom: 4 }}>테마</div>
          <ToggleRow
            label={isDark ? '다크 모드' : '라이트 모드'}
            desc="앱 테마를 전환합니다"
            value={isDark}
            onChange={setIsDark}
          />
        </div>

        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '4px 16px', marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, paddingTop: 14, marginBottom: 4 }}>알림</div>
          <ToggleRow
            label="푸시 알림"
            desc="앱 알림을 받습니다"
            value={pushEnabled}
            onChange={setPushEnabled}
          />
          <ToggleRow
            label="딜 알림"
            desc="참여한 딜의 상태 변경 알림"
            value={dealAlerts}
            onChange={setDealAlerts}
          />
          <ToggleRow
            label="가격 알림"
            desc="관심 딜의 가격 변동 알림"
            value={priceAlerts}
            onChange={setPriceAlerts}
          />
        </div>

        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '4px 16px', marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, paddingTop: 14, marginBottom: 4 }}>효과음</div>
          <ToggleRow
            label="효과음"
            desc="결제, 알림 등에 효과음을 재생합니다 (기본: 꺼짐)"
            value={soundEnabled}
            onChange={v => { setSoundEnabled(v); if (v) soundEffects.playClick(); }}
          />
        </div>

        <div style={{ padding: '20px 0', textAlign: 'center', fontSize: 11, color: C.textDim }}>
          역핑 v2.0 · Phase 2
        </div>
      </div>
    </div>
  );
}
