import apiClient from './client';
import { API } from './endpoints';
import { FEATURES } from '../config';
import type { DealResponse } from './types';
import type { Deal } from '../types';

// 백엔드 DealResponse → 프론트엔드 Deal 매핑
export function mapDealResponseToDisplay(d: DealResponse): Deal {
  return {
    id:                 d.id,
    product_name:       d.product_name,
    brand:              d.brand ?? null,
    category:           d.extra_conditions ?? '',
    desired_price:      d.target_price ?? d.max_budget ?? 0,
    anchor_price:       d.anchor_price ?? 0,
    status:             d.status === 'open' ? 'OPEN'
                      : d.status === 'closed' ? 'CLOSED'
                      : d.status === 'archived' ? 'COMPLETED'
                      : 'OPEN',
    deadline_at:        d.deadline_at ?? null,
    participants_count: d.current_qty ?? 0,
    spectator_count:    0,
    offer_count:        0,
    avg_prediction:     0,
    created_at:         d.created_at,
  };
}

export async function fetchDeals(
  page = 1,
  size = 100,
  opts?: { keyword?: string; buyer_id?: number },
) {
  if (!FEATURES.USE_API_DEALS) return null;
  try {
    const params: Record<string, unknown> = { page, size };
    if (opts?.keyword) params.keyword = opts.keyword;
    if (opts?.buyer_id != null) params.buyer_id = opts.buyer_id;
    const res = await apiClient.get(API.DEALS.LIST, { params });
    // Backend returns { items: [...], total, page, size, pages }
    const data = res.data;
    return Array.isArray(data) ? data : (data?.items ?? []);
  } catch (err) {
    console.error('딜 목록 API 실패, Mock 폴백:', err);
    return null;
  }
}

export async function fetchDeal(dealId: number) {
  if (!FEATURES.USE_API_DEALS) return null;
  try {
    const res = await apiClient.get(API.DEALS.DETAIL(dealId));
    return res.data;
  } catch (err) {
    console.error('딜 상세 API 실패, Mock 폴백:', err);
    return null;
  }
}

export async function fetchDealParticipants(dealId: number) {
  if (!FEATURES.USE_API_DEALS) return null;
  try {
    const res = await apiClient.get(API.DEALS.PARTICIPANTS(dealId));
    return res.data;
  } catch (err) {
    console.error('딜 참여자 API 실패:', err);
    return null;
  }
}

export async function addParticipant(dealId: number, buyerId: number, qty: number) {
  const res = await apiClient.post(API.DEALS.ADD_PARTICIPANT(dealId), { buyer_id: buyerId, qty });
  return res.data;
}

export async function updateDealTarget(dealId: number, targetPrice: number, reason?: string) {
  const res = await apiClient.patch(API.DEALS.UPDATE_TARGET(dealId), { target_price: targetPrice, reason });
  return res.data;
}

export async function createDeal(dealData: Record<string, unknown>) {
  const res = await apiClient.post(API.DEALS.CREATE, dealData);
  return res.data;
}
