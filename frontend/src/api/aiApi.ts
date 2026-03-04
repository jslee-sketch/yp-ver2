import apiClient from './client';
import { API } from './endpoints';
import { FEATURES } from '../config';

export async function aiDealHelper(productName: string, freeText?: string) {
  if (!FEATURES.USE_API_AI) return null;
  try {
    const body: Record<string, string> = { raw_title: productName };
    if (freeText) body.raw_free_text = freeText;
    const res = await apiClient.post(API.AI.DEAL_HELPER, body);
    return res.data;
  } catch (err) {
    console.error('AI 딜 헬퍼 API 실패:', err);
    return null;
  }
}

export async function aiResolveIntent(text: string) {
  if (!FEATURES.USE_API_AI) return null;
  try {
    const res = await apiClient.post(API.DEALS.AI_RESOLVE, { text });
    return res.data;
  } catch (err) {
    console.error('AI 의도 분석 API 실패:', err);
    return null;
  }
}
