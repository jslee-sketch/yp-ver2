import apiClient from './client';
import { API } from './endpoints';
import type { SpectatorPrediction } from './types';

export async function recordView(dealId: number): Promise<void> {
  try {
    await apiClient.post(API.SPECTATOR.VIEW(dealId));
  } catch {
    // silent — 조회수 기록 실패는 무시
  }
}

export async function submitPrediction(
  dealId: number,
  predictedPrice: number,
  comment?: string,
): Promise<SpectatorPrediction | null> {
  try {
    const res = await apiClient.post(API.SPECTATOR.PREDICT, {
      deal_id: dealId,
      predicted_price: predictedPrice,
      comment,
    });
    return res.data as SpectatorPrediction;
  } catch (err) {
    console.error('예측 제출 API 실패:', err);
    return null;
  }
}

export async function fetchPredictions(dealId: number): Promise<SpectatorPrediction[]> {
  try {
    const res = await apiClient.get(API.SPECTATOR.PREDICTIONS(dealId));
    return (res.data ?? []) as SpectatorPrediction[];
  } catch (err) {
    console.error('예측 목록 API 실패:', err);
    return [];
  }
}

export async function fetchMyPredictions(): Promise<SpectatorPrediction[]> {
  try {
    const res = await apiClient.get(API.SPECTATOR.MY_PREDICTIONS);
    return (res.data ?? []) as SpectatorPrediction[];
  } catch (err) {
    console.error('내 예측 목록 API 실패:', err);
    return [];
  }
}

interface RankingEntry {
  rank: number;
  buyer_id: number;
  nickname: string;
  total_points: number;
  hits_count: number;
  predictions_count: number;
  hit_rate: number;
  badge?: string;
}

export async function fetchRankings(): Promise<RankingEntry[]> {
  try {
    const res = await apiClient.get(API.SPECTATOR.RANKINGS);
    return (res.data ?? []) as RankingEntry[];
  } catch (err) {
    console.error('랭킹 API 실패:', err);
    return [];
  }
}
