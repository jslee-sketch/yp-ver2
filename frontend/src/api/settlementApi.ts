import apiClient from './client';
import { API } from './endpoints';
import type { Settlement } from './types';

export async function fetchMySettlements(sellerId?: number): Promise<Settlement[]> {
  try {
    if (sellerId) {
      const res = await apiClient.get(`/settlements/seller/${sellerId}`);
      return (res.data ?? []) as Settlement[];
    }
    const res = await apiClient.get(API.SETTLEMENTS.LIST);
    return (res.data ?? []) as Settlement[];
  } catch (err) {
    console.error('정산 목록 API 실패:', err);
    return [];
  }
}

export async function fetchSettlementDetail(id: number): Promise<Settlement | null> {
  try {
    const res = await apiClient.get(API.SETTLEMENTS.DETAIL(id));
    return res.data as Settlement;
  } catch (err) {
    console.error('정산 상세 API 실패:', err);
    return null;
  }
}
