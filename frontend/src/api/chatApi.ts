import apiClient from './client';
import { API } from './endpoints';
import { FEATURES } from '../config';

export async function fetchChatMessages(dealId: number) {
  if (!FEATURES.USE_API_DEALS) return null;
  try {
    const res = await apiClient.get(API.DEAL_CHAT.MESSAGES(dealId));
    return res.data;
  } catch (err) {
    console.error('채팅 API 실패:', err);
    return null;
  }
}

export async function sendChatMessage(
  dealId: number,
  message: string,
  userId: number,
  userType = 'buyer',
) {
  if (!FEATURES.USE_API_DEALS) return null;
  const res = await apiClient.post(API.DEAL_CHAT.SEND(dealId), {
    message,
    user_id: userId,
    user_type: userType,
  });
  return res.data;
}
