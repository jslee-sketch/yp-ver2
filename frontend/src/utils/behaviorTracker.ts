import apiClient from '../api/client';

export function trackBehavior(action: string, data?: {
  target_type?: string;
  target_id?: number;
  target_name?: string;
  meta?: Record<string, unknown>;
  user_type?: string;
  user_id?: number;
}) {
  // Fire-and-forget — no UX impact
  apiClient.post('/behavior/track', {
    action,
    target_type: data?.target_type,
    target_id: data?.target_id,
    target_name: data?.target_name,
    meta: data?.meta || {},
    user_type: data?.user_type,
    user_id: data?.user_id,
  }).catch(() => {}); // silent fail
}
