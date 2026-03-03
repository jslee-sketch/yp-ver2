import apiClient from './client';
import { API } from './endpoints';
import { FEATURES } from '../config';

export async function fetchMyReservations() {
  if (!FEATURES.USE_API_RESERVATIONS) return null;
  try {
    const res = await apiClient.get(API.RESERVATIONS.LIST_BUYER);
    return res.data;
  } catch (err) {
    console.error('예약 목록 API 실패:', err);
    return null;
  }
}

export async function createReservation(data: {
  deal_id: number;
  offer_id: number;
  buyer_id: number;
  qty: number;
}) {
  if (!FEATURES.USE_API_RESERVATIONS) return null;
  const res = await apiClient.post(API.RESERVATIONS.CREATE, data);
  return res.data;
}

export async function payReservation(reservationId: number) {
  if (!FEATURES.USE_API_RESERVATIONS) return null;
  const res = await apiClient.post(API.RESERVATIONS.PAY(reservationId));
  return res.data;
}

export async function cancelReservation(reservationId: number, actor = 'buyer_cancel') {
  if (!FEATURES.USE_API_RESERVATIONS) return null;
  const res = await apiClient.post(API.RESERVATIONS.CANCEL(reservationId), { actor });
  return res.data;
}

export async function confirmArrival(reservationId: number) {
  if (!FEATURES.USE_API_RESERVATIONS) return null;
  const res = await apiClient.post(API.RESERVATIONS.CONFIRM_ARRIVAL(reservationId));
  return res.data;
}

export async function markShipped(reservationId: number, trackingNumber: string, carrier?: string) {
  if (!FEATURES.USE_API_RESERVATIONS) return null;
  const res = await apiClient.post(API.RESERVATIONS.SHIP(reservationId), {
    tracking_number: trackingNumber,
    shipping_carrier: carrier,
  });
  return res.data;
}

export async function fetchCarriers() {
  try {
    const res = await apiClient.get(API.DELIVERY.CARRIERS);
    return res.data;
  } catch {
    return null;
  }
}
