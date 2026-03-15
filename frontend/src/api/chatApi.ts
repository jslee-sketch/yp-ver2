import apiClient from './client';
import { API } from './endpoints';
import { FEATURES } from '../config';

export async function fetchChatMessages(dealId: number, buyerId?: number) {
  if (!FEATURES.USE_API_DEALS) return null;
  if (!buyerId) return null; // buyer_id is required by backend
  try {
    const res = await apiClient.get(API.DEAL_CHAT.MESSAGES(dealId), {
      params: { buyer_id: buyerId },
    });
    // Backend returns { items: [...], total: N }
    const data = res.data;
    return Array.isArray(data) ? data : (data?.items ?? []);
  } catch (err) {
    console.error('채팅 API 실패:', err);
    return null;
  }
}

export async function sendChatMessage(
  dealId: number,
  message: string,
  userId: number,
  _userType = 'buyer',
) {
  if (!FEATURES.USE_API_DEALS) return null;
  const res = await apiClient.post(API.DEAL_CHAT.SEND(dealId), {
    buyer_id: userId,
    text: message,
  });
  return res.data;
}
