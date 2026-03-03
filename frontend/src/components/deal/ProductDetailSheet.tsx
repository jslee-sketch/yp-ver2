import React from 'react';
import { BottomSheet } from '../common/BottomSheet';

interface ProductOption {
  title: string;
  selected_value: string | null;
  values: string[];
}

interface ProductConditions {
  shipping_fee_krw: number;
  warranty_months: number;
  delivery_days: number;
  return_policy: string;
  condition_grade: string;
}

interface ProductDetailSheetProps {
  isOpen: boolean;
  onClose: () => void;
  productName: string;
  brand: string | null;
  canonicalName?: string;
  options?: ProductOption[];
  conditions?: ProductConditions;
  naverLowestPrice?: number | null;
  naverProductName?: string | null;
  aiAnalyzedAt?: string | null;
}

export const ProductDetailSheet: React.FC<ProductDetailSheetProps> = ({
  isOpen,
  onClose,
  productName,
  brand,
  canonicalName,
  options = [],
  conditions,
  naverLowestPrice,
  naverProductName,
  aiAnalyzedAt,
}) => {
  return (
    <BottomSheet isOpen={isOpen} onClose={onClose} title="상품 정보" height="75vh">
      <div style={{ padding: '16px 20px 32px' }}>

        {/* 상품명 */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' }}>
            상품명
          </div>
          <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.3 }}>
            {productName}
          </div>
          {brand && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              {brand}
              {canonicalName && canonicalName !== productName && (
                <span style={{ marginLeft: 8, color: 'var(--text-disabled)' }}>
                  ({canonicalName})
                </span>
              )}
            </div>
          )}
        </div>

        <Divider />

        {/* 옵션 */}
        {options.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <SectionLabel>선택 옵션</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {options.map((opt, i) => (
                <div key={i} style={{
                  padding: '10px 12px',
                  background: 'var(--bg-tertiary)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
                    {opt.title}
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {opt.values.map(v => (
                      <span
                        key={v}
                        style={{
                          padding: '4px 10px',
                          borderRadius: 20,
                          fontSize: 12,
                          fontWeight: v === opt.selected_value ? 700 : 400,
                          background: v === opt.selected_value ? 'var(--accent-green-bg)' : 'var(--bg-elevated)',
                          color: v === opt.selected_value ? 'var(--accent-green)' : 'var(--text-muted)',
                          border: v === opt.selected_value ? '1px solid rgba(0,230,118,0.3)' : '1px solid transparent',
                        }}
                      >
                        {v === opt.selected_value ? `✓ ${v}` : v}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 조건 */}
        {conditions && (
          <>
            <Divider />
            <div style={{ marginBottom: 20 }}>
              <SectionLabel>거래 조건</SectionLabel>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <ConditionItem label="배송비" value={conditions.shipping_fee_krw === 0 ? '무료' : `${conditions.shipping_fee_krw.toLocaleString('ko-KR')}원`} highlight={conditions.shipping_fee_krw === 0} />
                <ConditionItem label="보증기간" value={conditions.warranty_months > 0 ? `${conditions.warranty_months}개월` : '없음'} />
                <ConditionItem label="배송일" value={`${conditions.delivery_days}일`} />
                <ConditionItem label="상품 상태" value={conditions.condition_grade} />
              </div>
              <div style={{ marginTop: 8, padding: '10px 12px', background: 'var(--bg-tertiary)', borderRadius: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>반품 정책 · </span>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{conditions.return_policy}</span>
              </div>
            </div>
          </>
        )}

        {/* 네이버 최저가 */}
        {naverLowestPrice && (
          <>
            <Divider />
            <div style={{ marginBottom: 20 }}>
              <SectionLabel>시장가 참고</SectionLabel>
              <div style={{
                padding: '12px 14px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>
                      📊 네이버 최저가
                    </div>
                    {naverProductName && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, lineHeight: 1.3 }}>
                        {naverProductName}
                      </div>
                    )}
                    <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)' }}>
                      {naverLowestPrice.toLocaleString('ko-KR')}원
                    </div>
                  </div>
                  <button style={{
                    padding: '6px 12px',
                    background: 'var(--accent-green-bg)',
                    color: 'var(--accent-green)',
                    borderRadius: 8,
                    fontSize: 11,
                    fontWeight: 700,
                    border: '1px solid rgba(0,230,118,0.2)',
                  }}>
                    확인하기 →
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* AI 분석 일시 */}
        {aiAnalyzedAt && (
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: 10, color: 'var(--text-disabled)' }}>
              🤖 AI 분석: {new Date(aiAnalyzedAt).toLocaleString('ko-KR', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        )}
      </div>
    </BottomSheet>
  );
};

// ── 서브 컴포넌트 ─────────────────────────────────────
const Divider = () => (
  <div style={{ height: 1, background: 'var(--border-subtle)', margin: '0 0 16px' }} />
);

const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 10 }}>
    {children}
  </div>
);

const ConditionItem: React.FC<{ label: string; value: string; highlight?: boolean }> = ({ label, value, highlight }) => (
  <div style={{
    padding: '10px 12px',
    background: 'var(--bg-tertiary)',
    borderRadius: 8,
  }}>
    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
    <div style={{
      fontSize: 13,
      fontWeight: 700,
      color: highlight ? 'var(--accent-green)' : 'var(--text-primary)',
    }}>
      {value}
    </div>
  </div>
);
