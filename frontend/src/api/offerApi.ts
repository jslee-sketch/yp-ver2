import apiClient from './client';
import { API } from './endpoints';
import { FEATURES } from '../config';

export async function fetchOffersByDeal(dealId: number) {
  if (!FEATURES.USE_API_OFFERS) return null;
  try {
    const res = await apiClient.get(API.OFFERS.BY_DEAL(dealId));
    return res.data;
  } catch (err) {
    console.error('오퍼 목록 API 실패, Mock 폴백:', err);
    return null;
  }
}

export async function fetchOfferDetail(offerId: number) {
  if (!FEATURES.USE_API_OFFERS) return null;
  try {
    const res = await apiClient.get(API.OFFERS.DETAIL(offerId));
    return res.data;
  } catch (err) {
    console.error('오퍼 상세 API 실패:', err);
    return null;
  }
}

export async function createOffer(offerData: Record<string, unknown>) {
  const res = await apiClient.post(API.OFFERS.CREATE, offerData);
  return res.data;
}
