import apiClient from './client';
import { API } from './endpoints';
import type { Review } from './types';

export async function fetchReviewsBySeller(sellerId: number): Promise<Review[]> {
  try {
    const res = await apiClient.get(API.REVIEWS.BY_SELLER(sellerId));
    return (res.data ?? []) as Review[];
  } catch (err) {
    console.error('셀러 리뷰 목록 API 실패:', err);
    return [];
  }
}

export interface SellerReviewSummary {
  seller_id: number;
  avg_rating: number;
  total_count: number;
  rating_distribution: Record<number, number>; // 1~5
}

export async function fetchSellerReviewSummary(sellerId: number): Promise<SellerReviewSummary | null> {
  try {
    const res = await apiClient.get(API.REVIEWS.SUMMARY(sellerId));
    return res.data as SellerReviewSummary;
  } catch (err) {
    console.error('셀러 리뷰 요약 API 실패:', err);
    return null;
  }
}
