export interface CondTag {
  text: string;
  type: 'good' | 'neutral' | 'bad';
}

export type OfferGroup  = 'PREMIUM' | 'MATCHING' | 'BELOW';
export type SortKey     = 'adjPrice' | 'rawPrice' | 'totalQty' | 'remainQty' | 'sellerScore' | 'shipDays' | 'indexPct';
export type VerdictType = 'good' | 'close' | 'far';

export interface JourneyOffer {
  id:           number;
  seller:       string;
  icon:         string;
  rawPrice:     number;
  adjPrice:     number;
  offerIndexPct: number;    // rawPrice / target × 100
  totalQty:     number;
  remainQty:    number;
  shipDays:     number;
  shipFee:      string;     // '무료' or '3,000원' etc.
  refund:       string;
  asGrade:      string;     // AS 등급
  sellerTier:   string;
  sellerScore:  number;
  sellerDeals:  number;
  sellerRate:   string;
  condTags:     CondTag[];
  group:        OfferGroup;
  // waterfall
  groupAdj:     number;
  groupResult:  number;
  condAdj:      number;
  condResult:   number;
  condDetail:   string;
  // verdict
  verdictType:  VerdictType;
  verdictEmoji: string;
  verdictTitle: string;
  verdictDesc:  string;     // may contain safe HTML markup
  isMine?:      boolean;
  detail?:      string;     // 제품 상세 설명 (plain text, \n 줄바꿈)
  images?:      string[];   // 제품 이미지 URL 배열
}
