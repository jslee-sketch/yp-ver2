import { useState, useEffect, useRef } from 'react';

export type TimelineStage = 'recruiting' | 'offer_competition' | 'reservation_payment' | 'completed';

interface TimelineProps {
  currentStage: TimelineStage;
  showBanner?: boolean;
  onBannerDismiss?: () => void;
}

const STAGES: { key: TimelineStage; label: string; icon: string; color: string }[] = [
  { key: 'recruiting',          label: '딜 모집',   icon: '🎯', color: '#39ff14' },
  { key: 'offer_competition',   label: '오퍼 경쟁', icon: '⚔️', color: '#00b0ff' },
  { key: 'reservation_payment', label: '예약/결제', icon: '💳', color: '#ffe156' },
  { key: 'completed',           label: '완료',      icon: '🎉', color: '#ff69b4' },
];

const BANNER_MESSAGES: Record<TimelineStage, string> = {
  recruiting:          '🎯 딜 모집이 시작되었습니다!',
  offer_competition:   '⚔️ 오퍼 경쟁이 시작되었습니다!',
  reservation_payment: '💳 예약 및 결제가 시작되었습니다!',
  completed:           '🎉 딜이 성공적으로 완료되었습니다!',
};

export function mapDealToTimelineStage(deal: Record<string, unknown>): TimelineStage {
  const status = String(deal?.status ?? '').toLowerCase();

  if (status === 'completed' || status === 'archived') return 'completed';

  if (status === 'closed' || status === 'reserved' || status === 'paid') return 'reservation_payment';

  const offerCount = (deal?.offer_count as number) ?? 0;
  if (offerCount > 0 || status === 'offer_phase' || status === 'bidding') return 'offer_competition';

  return 'recruiting';
}

export default function DealTimeline({ currentStage, showBanner = false, onBannerDismiss }: TimelineProps) {
  const currentIndex = STAGES.findIndex(s => s.key === currentStage);
  const [bannerVisible, setBannerVisible] = useState(false);
  const [bannerText, setBannerText] = useState('');
  const confettiFired = useRef(false);

  // Banner — auto-dismiss after 3s
  useEffect(() => {
    if (showBanner && BANNER_MESSAGES[currentStage]) {
      setBannerText(BANNER_MESSAGES[currentStage]);
      setBannerVisible(true);
      const t = setTimeout(() => {
        setBannerVisible(false);
        onBannerDismiss?.();
      }, 3000);
      return () => clearTimeout(t);
    }
  }, [currentStage, showBanner, onBannerDismiss]);

  const dismissBanner = () => {
    setBannerVisible(false);
    onBannerDismiss?.();
  };

  // Confetti
  useEffect(() => {
    if (currentStage === 'completed' && !confettiFired.current) {
      confettiFired.current = true;
      import('canvas-confetti').then(mod => {
        const confetti = mod.default;
        confetti({ particleCount: 80, spread: 70, origin: { x: 0.2, y: 0.6 } });
        setTimeout(() => confetti({ particleCount: 80, spread: 70, origin: { x: 0.8, y: 0.6 } }), 300);
        setTimeout(() => confetti({ particleCount: 120, spread: 100, origin: { x: 0.5, y: 0.5 } }), 600);
      });
    }
  }, [currentStage]);

  return (
    <div style={{ position: 'relative' }}>
      {/* Banner */}
      {bannerVisible && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
          display: 'flex', justifyContent: 'center', padding: 16,
          animation: 'tlBannerIn 0.3s ease-out',
          pointerEvents: 'auto',
        }}>
          <div style={{
            background: 'linear-gradient(135deg, #1a1a2e 0%, #2a2a4a 100%)',
            border: '1px solid #4ade80',
            borderRadius: 16, padding: '16px 32px',
            color: '#fff', fontSize: 18, fontWeight: 700,
            boxShadow: '0 8px 32px rgba(74,222,128,0.3)',
            textAlign: 'center',
            position: 'relative',
          }}>
            {bannerText}
            <button
              onClick={dismissBanner}
              style={{
                position: 'absolute', top: 6, right: 10,
                background: 'transparent', border: 'none',
                color: 'rgba(255,255,255,0.6)', fontSize: 16,
                cursor: 'pointer', padding: '2px 6px',
                lineHeight: 1,
              }}
              aria-label="닫기"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 8px', position: 'relative',
      }}>
        {STAGES.map((stage, index) => {
          const isActive = index <= currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <div key={stage.key} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              flex: 1, position: 'relative',
            }}>
              {/* Connector */}
              {index > 0 && (
                <div style={{
                  position: 'absolute', top: 20, left: '-50%', right: '50%', height: 3,
                  background: isActive
                    ? `linear-gradient(90deg, ${STAGES[index - 1].color}, ${stage.color})`
                    : '#333',
                  transition: 'background 0.5s ease',
                }} />
              )}

              {/* Icon circle */}
              <div style={{
                width: 44, height: 44, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 20,
                background: isActive ? stage.color : 'rgba(255,255,255,0.06)',
                border: isCurrent ? `3px solid ${stage.color}` : isActive ? `2px solid ${stage.color}88` : '2px solid #333',
                boxShadow: isCurrent ? `0 0 10px ${stage.color}, 0 0 25px ${stage.color}60` : 'none',
                transition: 'all 0.5s ease',
                animation: isCurrent ? 'pulseGlow 2s infinite' : 'none',
                color: isCurrent ? stage.color : undefined,
                opacity: isActive ? 1 : 0.4,
                zIndex: 1,
              }}>
                {isActive ? stage.icon : '○'}
              </div>

              {/* Label */}
              <div style={{
                marginTop: 8, fontSize: 12,
                fontWeight: isCurrent ? 700 : 400,
                color: isCurrent ? stage.color : isActive ? '#fff' : 'rgba(255,255,255,0.3)',
                textAlign: 'center', transition: 'color 0.5s ease',
              }}>
                {stage.label}
              </div>

              {/* Pulse dot */}
              {isCurrent && (
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: stage.color, marginTop: 4,
                  animation: 'tlPulse 1.5s infinite',
                }} />
              )}
            </div>
          );
        })}
      </div>

      <style>{`
        @keyframes tlPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.5); }
        }
        @keyframes tlBannerIn {
          from { opacity: 0; transform: translateY(-20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulseGlow {
          0%, 100% { transform: scale(1); box-shadow: 0 0 10px currentColor; }
          50% { transform: scale(1.3); box-shadow: 0 0 25px currentColor; }
        }
      `}</style>
    </div>
  );
}
