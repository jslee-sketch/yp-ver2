import apiClient from './client';
import { API } from './endpoints';
import { FEATURES } from '../config';

// 프론트 pathname → 백엔드 screen 매핑
function mapPageToScreen(page?: string): string {
  if (!page) return 'GENERAL';
  if (page.includes('/offer/create')) return 'OFFER_CREATE';
  if (page.match(/^\/deal\/\d+/))    return 'DEAL_ROOM';
  if (page.includes('/my-orders'))    return 'ORDER_LIST';
  if (page.includes('/completed'))    return 'DEAL_LIST';
  if (page.includes('/deals'))        return 'DEAL_LIST';
  if (page.includes('/search'))       return 'DEAL_LIST';
  if (page.includes('/settlements'))  return 'SETTLEMENT';
  if (page.includes('/points'))       return 'POINT';
  if (page.includes('/mypage') || page === '/my') return 'MY_PAGE';
  return 'GENERAL';
}

export async function askPingpong(
  message: string,
  context?: { page?: string; deal_id?: number; user_id?: number; role?: string },
) {
  if (!FEATURES.USE_API_PINGPONG) return null;
  try {
    const res = await apiClient.post(API.PINGPONG.ASK, {
      question: message,
      screen: mapPageToScreen(context?.page),
      user_id: context?.user_id ?? null,
      role: (context?.role || 'buyer').toUpperCase(),
      context: {
        deal_id: context?.deal_id ?? null,
      },
      mode: 'read_only',
    });
    return res.data;
  } catch (err) {
    console.error('핑퐁이 API 실패:', err);
    return { answer: '핑퐁이가 잠시 쉬고 있어요 🏓 잠시 후 다시 시도해주세요!' };
  }
}
