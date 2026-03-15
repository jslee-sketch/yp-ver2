import { useRef, useState } from 'react';
import { T, groupColor, groupBg, groupBorder } from './journeyTokens';
import type { JourneyOffer, OfferGroup, SortKey } from './types';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'adjPrice',    label: '보정가순' },
  { key: 'rawPrice',    label: '오퍼가순' },
  { key: 'totalQty',    label: '판매수량순' },
  { key: 'remainQty',   label: '남은수량순' },
  { key: 'sellerScore', label: '판매자등급순' },
  { key: 'shipDays',    label: '배송빠른순' },
  { key: 'indexPct',    label: '지수순' },
];

const GROUP_ORDER:  Record<OfferGroup, number> = { PREMIUM: 0, MATCHING: 1, BELOW: 2 };
const GROUP_LABELS: Record<OfferGroup, string> = {
  PREMIUM:  'PREMIUM · 목표가 이하',
  MATCHING: 'MATCHING · 목표가 부합',
  BELOW:    'BELOW · 목표가 초과',
};
const ITEMS_PER_PAGE = 10;

function sortOffers(offers: JourneyOffer[], key: SortKey): JourneyOffer[] {
  const arr = [...offers];
  switch (key) {
    case 'adjPrice':
      return arr.sort((a, b) => {
        const g = GROUP_ORDER[a.group] - GROUP_ORDER[b.group];
        return g !== 0 ? g : a.adjPrice - b.adjPrice;
      });
    case 'rawPrice':    return arr.sort((a, b) => a.rawPrice - b.rawPrice);
    case 'totalQty':    return arr.sort((a, b) => b.totalQty - a.totalQty);
    case 'remainQty':   return arr.sort((a, b) => b.remainQty - a.remainQty);
    case 'sellerScore': return arr.sort((a, b) => b.sellerScore - a.sellerScore);
    case 'shipDays':    return arr.sort((a, b) => a.shipDays - b.shipDays);
    case 'indexPct':    return arr.sort((a, b) => a.offerIndexPct - b.offerIndexPct);
  }
}

// ── Rank badge ──────────────────────────────────────────
function RankBadge({ rank }: { rank: number }) {
  const styles: Record<number, { bg: string; color: string; border: string }> = {
    1: { bg: 'linear-gradient(135deg,rgba(57,255,20,0.2),rgba(0,240,255,0.1))', color: T.green,  border: 'rgba(57,255,20,0.3)' },
    2: { bg: 'rgba(255,225,86,0.1)',   color: T.yellow, border: 'rgba(255,225,86,0.25)' },
    3: { bg: 'rgba(255,140,66,0.1)',   color: T.orange, border: 'rgba(255,140,66,0.25)' },
  };
  const s = styles[rank] ?? { bg: T.bgSurface, color: T.textSec, border: T.border };
  return (
    <div style={{
      width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: s.bg, border: `1px solid ${s.border}`,
      fontFamily: "'Outfit', sans-serif", fontSize: 13, fontWeight: 800, color: s.color,
    }}>
      {rank}
    </div>
  );
}

// ── Group separator ─────────────────────────────────────
function GroupSep({ group, count }: { group: OfferGroup; count: number }) {
  const c = groupColor[group];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '12px 0 8px' }}>
      <div style={{
        padding: '3px 10px', borderRadius: 8, fontSize: 9, fontWeight: 700,
        letterSpacing: 1, fontFamily: "'Space Mono', monospace", whiteSpace: 'nowrap',
        background: `${c}22`, color: c, border: `1px solid ${c}44`,
      }}>
        {GROUP_LABELS[group]}
      </div>
      <div style={{ flex: 1, height: 1, background: `${c}30` }} />
      <span style={{ fontSize: 10, color: T.textSec, whiteSpace: 'nowrap' }}>{count}건</span>
    </div>
  );
}

// ── Offer card ──────────────────────────────────────────
function OfferCard({
  offer, rank, target, onSelect,
}: {
  offer: JourneyOffer; rank: number; target: number; onSelect: () => void;
}) {
  const gc = groupColor[offer.group];
  const gb = groupBg[offer.group];
  const gborder = groupBorder[offer.group];

  return (
    <div
      onClick={onSelect}
      style={{
        background: T.bgCard, border: `1px solid ${T.border}`,
        borderLeft: `3px solid ${gc}`, borderRadius: 14,
        padding: '14px 14px 14px 12px',
        marginBottom: 8, cursor: 'pointer', position: 'relative',
        transition: 'transform 0.15s',
      }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateX(2px)'; }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'none'; }}
    >
      {/* Main row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <RankBadge rank={rank} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: T.text, display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
            {offer.icon} {offer.seller}
            <span style={{
              fontSize: 7, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
              letterSpacing: 0.5, fontFamily: "'Space Mono', monospace",
              background: `${gb}`, color: gc, border: `1px solid ${gborder}`,
            }}>{offer.group}</span>
          </div>
          <div style={{ fontSize: 9, color: T.textSec, marginTop: 2, lineHeight: 1.4 }}>
            {offer.totalQty}개 · 배송 {offer.shipDays}일
            {' · '}{offer.shipFee === '무료' ? '무료배송' : `배송비 ${offer.shipFee}`}
            {' · '}환불 {offer.refund}
            {' · '}<span style={{ color: T.yellow }}>잔여 {offer.remainQty}개</span>
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 13, fontWeight: 700, color: T.text }}>
            ₩{offer.rawPrice.toLocaleString('ko-KR')}
          </div>
          <div style={{ fontSize: 9, marginTop: 1, color: offer.adjPrice <= target + 15000 ? T.green : T.orange }}>
            보정 ₩{offer.adjPrice.toLocaleString('ko-KR')}
          </div>
          <div style={{ fontSize: 8, marginTop: 1, color: T.textDim }}>
            잔여 {offer.remainQty}/{offer.totalQty}개
          </div>
        </div>
        <div style={{ color: T.textDim, fontSize: 11, flexShrink: 0, paddingTop: 4 }}>›</div>
      </div>

      {/* BEST badge — top left */}
      {rank === 1 && (
        <div style={{
          position: 'absolute', top: -5, left: 10,
          background: 'linear-gradient(135deg, #39ff14, #00f0ff)',
          color: '#000', fontSize: 8, fontWeight: 700,
          padding: '1px 7px', borderRadius: 6,
        }}>
          BEST
        </div>
      )}

      {/* MY badge — top right */}
      {offer.isMine && (
        <div style={{
          position: 'absolute', top: -5, right: 10,
          background: 'linear-gradient(135deg, #ff8c42, #ffe156)',
          color: '#0a0e1a', fontSize: 8, fontWeight: 800,
          padding: '1px 7px', borderRadius: 6, letterSpacing: 0.5,
        }}>
          MY
        </div>
      )}
    </div>
  );
}

// ── Main component ──────────────────────────────────────
interface Props {
  offers:         JourneyOffer[];
  target:         number;
  onSelectOffer:  (offer: JourneyOffer) => void;
}

export function OfferListSection({ offers, target, onSelectOffer }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('adjPrice');
  const [page, setPage]       = useState(0);
  const sectionRef            = useRef<HTMLDivElement>(null);

  const sorted     = sortOffers(offers, sortKey);
  const totalPages = Math.max(1, Math.ceil(sorted.length / ITEMS_PER_PAGE));
  const paged      = sorted.slice(page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE);

  const handleSort = (key: SortKey) => {
    setSortKey(key);
    setPage(0);
  };

  const handlePage = (p: number) => {
    setPage(p);
    sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Group counts (for separator labels)
  const groupCounts: Partial<Record<OfferGroup, number>> = {};
  sorted.forEach(o => { groupCounts[o.group] = (groupCounts[o.group] ?? 0) + 1; });

  // Build render list with optional group separators
  type Row = { kind: 'sep'; group: OfferGroup; count: number } | { kind: 'card'; offer: JourneyOffer; rank: number };

  const rows: Row[] = [];
  let lastGroup: OfferGroup | null = null;
  paged.forEach((offer, idx) => {
    const rank = page * ITEMS_PER_PAGE + idx + 1;
    if (sortKey === 'adjPrice' && offer.group !== lastGroup) {
      rows.push({ kind: 'sep', group: offer.group, count: groupCounts[offer.group] ?? 0 });
      lastGroup = offer.group;
    }
    rows.push({ kind: 'card', offer, rank });
  });

  return (
    <div ref={sectionRef} style={{ margin: '14px 16px 0', overflow: 'visible' }}>
      {/* Title */}
      <div style={{
        fontSize: 16, fontWeight: 800, color: T.text,
        marginBottom: 10, paddingLeft: 4,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'linear-gradient(135deg, rgba(0,240,255,0.08), rgba(57,255,20,0.06))',
        padding: '10px 14px',
        borderRadius: 12,
      }}>
        <span>{
          offers.length === 0
            ? '🕐 아직 판매자의 오퍼가 없습니다. 첫 오퍼를 기다려보세요!'
            : offers.length === 1
            ? '🎯 첫 번째 판매자가 등장했습니다!'
            : `⚔️ 판매자들의 가격 전쟁! ${offers.length}건의 오퍼가 경쟁 중!`
        }</span>
      </div>

      {/* Sort chips — wrap으로 2줄 처리 (스크롤 불필요) */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          marginBottom: 10,
        }}
      >
        {SORT_OPTIONS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => handleSort(key)}
            style={{
              flexShrink: 0,
              padding: '5px 12px',
              borderRadius: 20,
              background: sortKey === key ? `${groupColor.MATCHING}20` : T.bgSurface,
              border: `1px solid ${sortKey === key ? T.cyan : T.border}`,
              color: sortKey === key ? T.cyan : T.textSec,
              fontSize: 11, fontWeight: sortKey === key ? 700 : 400,
              cursor: 'pointer', whiteSpace: 'nowrap',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Offer cards */}
      <div>
        {rows.map((row) =>
          row.kind === 'sep'
            ? <GroupSep key={`sep-${row.group}`} group={row.group} count={row.count} />
            : <OfferCard
                key={row.offer.id}
                offer={row.offer}
                rank={row.rank}
                target={target}
                onSelect={() => onSelectOffer(row.offer)}
              />
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 12 }}>
          <PagBtn label="‹" disabled={page === 0} onClick={() => handlePage(page - 1)} />
          {Array.from({ length: totalPages }, (_, i) => (
            <PagBtn
              key={i} label={String(i + 1)}
              active={i === page} disabled={false}
              onClick={() => handlePage(i)}
            />
          ))}
          <PagBtn label="›" disabled={page === totalPages - 1} onClick={() => handlePage(page + 1)} />
        </div>
      )}
      <div style={{ fontSize: 10, color: T.textDim, textAlign: 'center', marginTop: 6 }}>
        {page * ITEMS_PER_PAGE + 1}–{Math.min((page + 1) * ITEMS_PER_PAGE, sorted.length)} / 총 {sorted.length}건
      </div>
    </div>
  );
}

function PagBtn({ label, active, disabled, onClick }: {
  label: string; active?: boolean; disabled: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        width: 30, height: 30, borderRadius: 8,
        background: active ? T.cyan : T.bgSurface,
        border: `1px solid ${active ? T.cyan : T.border}`,
        color: active ? '#000' : disabled ? T.textDim : T.textSec,
        fontSize: 12, fontWeight: active ? 700 : 400,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      {label}
    </button>
  );
}
