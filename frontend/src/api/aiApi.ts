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

export async function aiRecalcPrice(searchQuery: string, selectedOptions?: string, brand?: string) {
  if (!FEATURES.USE_API_AI) return null;
  try {
    const body: Record<string, unknown> = {
      raw_title: searchQuery,
      recalc_price: true,
    };
    if (selectedOptions) body.selected_options = selectedOptions;
    if (brand) body.brand = brand;
    const res = await apiClient.post(API.AI.DEAL_HELPER, body);
    return res.data;
  } catch (err) {
    console.error('가격 재계산 API 실패:', err);
    return null;
  }
}

export async function aiImageRecognize(file: File) {
  if (!FEATURES.USE_API_AI) return null;
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post(API.AI.DEAL_HELPER_IMAGE, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 20000,
    });
    return res.data;
  } catch (err) {
    console.error('이미지 인식 API 실패:', err);
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
