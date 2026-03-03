// 백엔드 응답 타입 (schemas.py 기반)

export interface BuyerProfile {
  id: number;
  email: string;
  name: string;
  nickname?: string;
  phone?: string;
  address?: string;
  zip_code?: string;
  points: number;
  level: number;
  trust_tier?: string;
  is_active: boolean;
  created_at: string;
}

export interface SellerProfile {
  id: number;
  email: string;
  business_name: string;
  nickname?: string;
  phone?: string;
  points: number;
  level: number;
  verified_at?: string;
  is_active: boolean;
  created_at: string;
}

export interface DealResponse {
  id: number;
  product_name: string;
  creator_id: number;
  desired_qty: number;
  current_qty: number;
  target_price?: number;
  max_budget?: number;
  current_avg_price: number;
  anchor_price?: number;
  brand?: string;
  option1_title?: string;
  option1_value?: string;
  option2_title?: string;
  option2_value?: string;
  option3_title?: string;
  option3_value?: string;
  option4_title?: string;
  option4_value?: string;
  option5_title?: string;
  option5_value?: string;
  free_text?: string;
  shipping_fee_krw?: number;
  refund_days?: number;
  warranty_months?: number;
  delivery_days?: number;
  extra_conditions?: string;
  status: 'open' | 'closed' | 'archived';
  deadline_at?: string;
  created_at: string;
}

export interface OfferResponse {
  id: number;
  deal_id: number;
  seller_id: number;
  price: number;
  total_available_qty: number;
  sold_qty: number;
  reserved_qty: number;
  delivery_days?: number;
  comment?: string;
  shipping_mode?: string;
  shipping_fee_per_reservation: number;
  shipping_fee_per_qty: number;
  is_active: boolean;
  is_confirmed: boolean;
  created_at: string;
  deadline_at?: string;
}

export interface ReservationResponse {
  id: number;
  deal_id: number;
  offer_id: number;
  buyer_id: number;
  qty: number;
  amount_goods: number;
  amount_shipping: number;
  amount_total: number;
  status: 'PENDING' | 'PAID' | 'CANCELLED' | 'EXPIRED';
  created_at: string;
  paid_at?: string;
  shipped_at?: string;
  delivered_at?: string;
  cancelled_at?: string;
  tracking_number?: string;
  shipping_carrier?: string;
}

export interface DealParticipantResponse {
  id: number;
  deal_id: number;
  buyer_id: number;
  qty: number;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: BuyerProfile | SellerProfile;
  role: 'buyer' | 'seller';
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface ChatMessage {
  id: number;
  deal_id: number;
  sender_id: number;
  sender_role: 'buyer' | 'seller' | 'system';
  sender_name: string;
  content: string;
  created_at: string;
}

export interface Notification {
  id: number;
  user_id: number;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  link?: string;
  created_at: string;
}

export interface Review {
  id: number;
  reservation_id: number;
  buyer_id: number;
  seller_id: number;
  rating: number;          // 1~5
  comment?: string;
  created_at: string;
}

export interface SpectatorPrediction {
  id: number;
  deal_id: number;
  buyer_id: number;
  predicted_price: number;
  comment?: string;
  created_at: string;
  // settle 후 추가 필드
  settled_price?: number;
  error_pct?: number;
  tier_name?: string;
  tier_label?: string;
  points_earned?: number;
  settled_at?: string;
}

export interface UploadedFile {
  id: string;
  url: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Settlement {
  id: number;
  reservation_id: number;
  seller_id: number;
  gross_amount: number;
  platform_fee: number;
  net_amount: number;
  status: 'HOLD' | 'READY' | 'APPROVED' | 'PAID';
  created_at: string;
  approved_at?: string;
  paid_at?: string;
}
