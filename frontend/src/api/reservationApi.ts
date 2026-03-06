import apiClient from './client';
import { API } from './endpoints';

export async function fetchMyReservations(buyerId: number) {
  try {
    const res = await apiClient.get(API.RESERVATIONS.LIST_BUYER(buyerId));
    return res.data;
  } catch (err) {
    console.error('예약 목록 API 실패:', err);
    return null;
  }
}

export async function fetchSellerReservations(sellerId: number) {
  try {
    const res = await apiClient.get(API.RESERVATIONS.LIST_SELLER(sellerId));
    return res.data;
  } catch (err) {
    console.error('판매자 예약 목록 API 실패:', err);
    return null;
  }
}

export async function fetchOffersByDeal(dealId: number) {
  try {
    const res = await apiClient.get(API.OFFERS_V36.BY_DEAL(dealId));
    return res.data;
  } catch (err) {
    console.error('오퍼 목록 API 실패:', err);
    return null;
  }
}

export async function createReservation(data: {
  deal_id: number;
  offer_id: number;
  buyer_id: number;
  qty: number;
}) {
  const res = await apiClient.post(API.RESERVATIONS_V36.CREATE, data);
  return res.data;
}

export async function payReservation(reservationId: number, buyerId: number, paidAmount: number) {
  const res = await apiClient.post(API.RESERVATIONS_V36.PAY, {
    reservation_id: reservationId,
    buyer_id: buyerId,
    paid_amount: paidAmount,
  });
  return res.data;
}

export async function cancelReservation(reservationId: number, buyerId: number) {
  const res = await apiClient.post(API.RESERVATIONS_V36.CANCEL, {
    reservation_id: reservationId,
    buyer_id: buyerId,
  });
  return res.data;
}

export async function confirmArrival(reservationId: number, buyerId?: number) {
  const res = await apiClient.post(API.RESERVATIONS_V36.CONFIRM_ARRIVAL(reservationId), {
    buyer_id: buyerId,
  });
  return res.data;
}

export async function markShipped(reservationId: number, trackingNumber: string, carrier?: string) {
  const res = await apiClient.post(API.RESERVATIONS_V36.SHIP(reservationId), {
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

export async function refundPreview(reservationId: number, actor = 'buyer_cancel') {
  const res = await apiClient.post(API.RESERVATIONS_V36.REFUND_PREVIEW, {
    reservation_id: reservationId,
    actor,
  });
  return res.data;
}

export async function refundReservation(reservationId: number, reason: string, requestedBy = 'BUYER', refundType = 'refund') {
  const res = await apiClient.post(API.RESERVATIONS_V36.REFUND, {
    reservation_id: reservationId,
    reason,
    requested_by: requestedBy,
    refund_type: refundType,
  });
  return res.data;
}
