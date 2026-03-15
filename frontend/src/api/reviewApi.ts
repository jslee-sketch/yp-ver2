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
  count: number;
  raw_avg: number;
  adjusted_rating: number;
  last_30d_count: number;
  // frontend-computed aliases
  avg_rating: number;
  total_count: number;
  rating_distribution?: Record<number, number>; // 1~5
}

export async function fetchSellerReviewSummary(sellerId: number): Promise<SellerReviewSummary | null> {
  try {
    const res = await apiClient.get(API.REVIEWS.SUMMARY(sellerId));
    const d = res.data as Record<string, unknown>;
    // backend returns {count, raw_avg, adjusted_rating, last_30d_count}
    // map to frontend-expected fields
    return {
      ...d,
      avg_rating: (d.adjusted_rating ?? d.raw_avg ?? 0) as number,
      total_count: (d.count ?? 0) as number,
      rating_distribution: (d.rating_distribution ?? {}) as Record<number, number>,
    } as SellerReviewSummary;
  } catch (err) {
    console.error('셀러 리뷰 요약 API 실패:', err);
    return null;
  }
}
