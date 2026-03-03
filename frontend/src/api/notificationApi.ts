import apiClient from './client';
import { API } from './endpoints';

export async function fetchNotifications() {
  try {
    const res = await apiClient.get(API.NOTIFICATIONS.LIST);
    return res.data;
  } catch (err) {
    console.error('알림 API 실패:', err);
    return null;
  }
}

export async function markNotificationRead(notificationId: number) {
  try {
    await apiClient.post(API.NOTIFICATIONS.READ(notificationId));
    return true;
  } catch {
    return false;
  }
}

export async function markAllRead() {
  try {
    await apiClient.post(API.NOTIFICATIONS.READ_ALL);
    return true;
  } catch {
    return false;
  }
}

export async function fetchUnreadCount(): Promise<number> {
  try {
    const res = await apiClient.get(API.NOTIFICATIONS.UNREAD_COUNT);
    return typeof res.data === 'number' ? res.data : Number(res.data?.count ?? 0);
  } catch {
    return 0;
  }
}
