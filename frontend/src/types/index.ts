// ── 딜 단계 ──────────────────────────────────────────
export interface DealStage {
  key: string;
  label: string;
  completed: boolean;
  deadline_at?: string | null;
}

// ── 딜 ──────────────────────────────────────────────
export type DealStatus = 'OPEN' | 'CLOSED' | 'EXPIRED' | 'CANCELLED' | 'COMPLETED';

export interface Deal {
  id: number;
  product_name: string;
  brand: string | null;
  category: string;
  desired_price: number;
  anchor_price: number | null;
  status: DealStatus;
  deadline_at: string | null;
  participants_count: number;
  spectator_count: number;
  offer_count?: number;
  avg_prediction?: number | null;
  created_at: string;
}

// ── 오퍼 ─────────────────────────────────────────────
export type OfferTier = 'PREMIUM' | 'MATCHING' | 'BELOW';

export interface Offer {
  id: number;
  seller_name: string;
  price: number;
  tier: OfferTier;
  rating: number;
  review_count: number;
  shipping_fee: number;
  delivery_days: number;
  warranty_months: number;
  is_selected?: boolean;
}

// ── 관전자 ────────────────────────────────────────────
export type SpectatorTier = 'PERFECT' | 'EXCELLENT' | 'GOOD' | 'FAIR' | 'MISS';

export interface SpectatorPrediction {
  id: number;
  deal_id: number;
  buyer_id: number;
  predicted_price: number;
  comment?: string;
  created_at: string;
  settled_price?: number | null;
  error_pct?: number | null;
  tier_name?: SpectatorTier | null;
  points_earned?: number | null;
}

export interface PredictionBucket {
  label: string;   // "85-88K"
  min: number;
  max: number;
  count: number;
  pct: number;
}

export interface SpectatorStats {
  deal_id: number;
  total_count: number;
  avg_predicted_price: number | null;
  median_predicted_price: number | null;
  buckets: PredictionBucket[];
  my_prediction?: number | null;
}

// ── 랭킹 ─────────────────────────────────────────────
export interface RankingEntry {
  rank: number;
  buyer_id: number;
  nickname: string;
  total_points: number;
  hits_count: number;
  predictions_count: number;
  hit_rate: number;
  badge?: string | null;
}

// ── 대시보드 ──────────────────────────────────────────
export interface BuyerDashboard {
  buyer_id: number;
  nickname: string;
  points_balance: number;
  active_deals_count: number;
  watching_deals_count: number;
  my_rank?: number | null;
}

// ── 실시간 이벤트 (LiveTicker) ──────────────────────
export interface LiveEvent {
  id: string;
  type: 'new_offer' | 'spectator_join' | 'deal_closed' | 'new_deal';
  deal_id?: number;
  deal_name?: string;
  price?: number;
  count?: number;
  timestamp: string;
  label: string;
}
