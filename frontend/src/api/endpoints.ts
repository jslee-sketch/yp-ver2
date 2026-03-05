// 백엔드 FastAPI 엔드포인트 매핑 (Yeokping Ver2 API v3.5/v3.6)

export const API = {

  // ── 인증 ────────────────────────────────────────────────────
  AUTH: {
    LOGIN:           '/auth/login',
    LOGOUT:          '/auth/logout',
    REGISTER_BUYER:  '/auth/register/buyer',
    REGISTER_SELLER: '/auth/register/seller',
    ME:              '/auth/me',
    REFRESH:         '/auth/refresh',
    CHECK_EMAIL:     '/auth/check-email',
    CHECK_NICKNAME:  '/users/check-nickname',
    CHECK_PHONE:     '/users/check-phone',
    CHANGE_PASSWORD: '/auth/change-password',
    SELLER_LOGIN:    '/auth/seller/login',
    SELLER_ME:       '/auth/seller/me',
    SOCIAL_AUTHORIZE: (provider: string) => `/auth/social/${provider}/authorize`,
    SOCIAL_CALLBACK:  (provider: string) => `/auth/social/${provider}/callback`,
  },

  // ── 계정 ────────────────────────────────────────────────────
  ACCOUNT: {
    WITHDRAW:        '/account/withdraw',
  },

  // ── 바이어 ───────────────────────────────────────────────────
  BUYERS: {
    LIST:            '/buyers/',
    DETAIL:          (id: number) => `/buyers/${id}`,
    UPDATE:          (id: number) => `/buyers/${id}`,
    PROFILE:         '/buyers/me',
    POINTS:          '/buyers/me/points',
    LEVEL:           '/buyers/me/level',
    TRUST_TIER:      '/buyers/me/trust_tier',
    ONBOARDING:      '/buyers/onboarding',
  },

  // ── 셀러 ────────────────────────────────────────────────────
  SELLERS: {
    LIST:            '/sellers/',
    DETAIL:          (id: number) => `/sellers/${id}`,
    UPDATE:          (id: number) => `/sellers/${id}`,
    PROFILE:         '/sellers/me',
    ONBOARDING:      '/sellers/onboarding',
    VERIFY:          (id: number) => `/sellers/${id}/verify`,
    RATING:          (id: number) => `/sellers/${id}/rating`,
  },

  // ── 딜 ──────────────────────────────────────────────────────
  DEALS: {
    LIST:              '/deals/',
    CREATE:            '/deals/',
    DETAIL:            (id: number) => `/deals/${id}`,
    UPDATE:            (id: number) => `/deals/${id}`,
    UPDATE_TARGET:     (id: number) => `/deals/${id}/target`,
    PARTICIPANTS:      (id: number) => `/deals/${id}/participants`,
    ADD_PARTICIPANT:   (id: number) => `/deals/${id}/participants`,
    CLOSE:             (id: number) => `/deals/${id}/close`,
    CLOSE_EXPIRED:     '/deals/close_expired',
    SEARCH:            '/deals/search',
    COMPLETED:         '/deals/completed',
    AI_RESOLVE:        '/deals/ai/resolve_from_intent',
    INTENT_CREATE:     '/deals/intent',
    INTENT_LIST:       '/deals/intents',
    INTENT_DETAIL:     (id: number) => `/deals/intent/${id}`,
  },

  // ── 딜 채팅 ─────────────────────────────────────────────────
  DEAL_CHAT: {
    MESSAGES:          (dealId: number) => `/deals/${dealId}/chat/messages`,
    SEND:              (dealId: number) => `/deals/${dealId}/chat/messages`,
    DELETE:            (dealId: number, msgId: number) => `/deals/${dealId}/chat/messages/${msgId}`,
  },

  // ── 오퍼 (v3.5) ─────────────────────────────────────────────
  OFFERS: {
    LIST:              '/offers',
    CREATE:            '/offers',
    DETAIL:            (id: number)       => `/offers/${id}`,
    UPDATE:            (id: number)       => `/offers/${id}`,
    DEACTIVATE:        (id: number)       => `/offers/${id}/deactivate`,
    BY_DEAL:           (dealId: number)   => `/offers?deal_id=${dealId}`,
    PREVIEW_PRICING:   (id: number)       => `/offers/${id}/preview_pricing`,
    PREVIEW_PACK:      '/offers/preview_pack',
  },

  // ── 오퍼+예약 통합 (v3.6) ────────────────────────────────────
  OFFERS_V36: {
    LIST:              '/v3_6/offers',
    CREATE:            '/v3_6/offers',
    DETAIL:            (id: number)       => `/v3_6/offers/${id}`,
    UPDATE:            (id: number)       => `/v3_6/offers/${id}`,
    BY_DEAL:           (dealId: number)   => `/v3_6/offers?deal_id=${dealId}`,
    PREVIEW_PRICING:   (id: number)       => `/v3_6/offers/${id}/preview_pricing`,
  },

  // ── 예약/결제 (v3.5) ─────────────────────────────────────────
  RESERVATIONS: {
    CREATE:            '/reservations/',
    LIST_BUYER:        '/reservations/buyer/',
    LIST_SELLER:       '/reservations/seller/',
    DETAIL:            (id: number) => `/reservations/${id}`,
    PAY:               (id: number) => `/reservations/${id}/pay`,
    SHIP:              (id: number) => `/reservations/${id}/ship`,
    CONFIRM_ARRIVAL:   (id: number) => `/reservations/${id}/arrival_confirm`,
    CANCEL:            (id: number) => `/reservations/${id}/cancel`,
    REFUND_PREVIEW:    (id: number) => `/reservations/${id}/refund_preview`,
  },

  // ── 예약/결제 (v3.6 통합) ────────────────────────────────────
  RESERVATIONS_V36: {
    LIST:              '/v3_6/reservations/',
    CREATE:            '/v3_6/reservations/',
    DETAIL:            (id: number) => `/v3_6/reservations/${id}`,
    PAY:               (id: number) => `/v3_6/reservations/${id}/pay`,
    SHIP:              (id: number) => `/v3_6/reservations/${id}/ship`,
    CONFIRM_ARRIVAL:   (id: number) => `/v3_6/reservations/${id}/arrival_confirm`,
    CANCEL:            (id: number) => `/v3_6/reservations/${id}/cancel`,
    REFUND_PREVIEW:    (id: number) => `/v3_6/reservations/${id}/refund_preview`,
    ADMIN_CANCEL:      (id: number) => `/v3_6/reservations/${id}/admin_cancel`,
    ADMIN_FORCE_SHIP:  (id: number) => `/v3_6/reservations/${id}/admin_force_ship`,
  },

  // ── 예약 검색/필터 ───────────────────────────────────────────
  RESERVATIONS_SEARCH: {
    BY_DEAL:           (dealId: number) => `/reservations/by_deal/${dealId}`,
    FIND_PAID:         '/reservations/find_paid_without_settlement',
    ADMIN_LIST:        '/admin/reservations/',
  },

  // ── 포인트 ──────────────────────────────────────────────────
  POINTS: {
    HISTORY:           '/points/history',
    BALANCE:           '/points/balance',
    EARN:              '/points/earn',
    SPEND:             '/points/spend',
  },

  // ── 알림 ────────────────────────────────────────────────────
  NOTIFICATIONS: {
    LIST:              '/notifications/',
    DETAIL:            (id: number) => `/notifications/${id}`,
    READ:              (id: number) => `/notifications/${id}/read`,
    READ_ALL:          '/notifications/read_all',
    UNREAD_COUNT:      '/notifications/unread_count',
  },

  // ── 리뷰 ────────────────────────────────────────────────────
  REVIEWS: {
    LIST:              '/reviews/',
    CREATE:            '/reviews/',
    DETAIL:            (id: number)         => `/reviews/${id}`,
    BY_SELLER:         (sellerId: number)   => `/reviews/seller/${sellerId}`,
    BY_BUYER:          (buyerId: number)    => `/reviews/buyer/${buyerId}`,
    SUMMARY:           (sellerId: number)   => `/reviews/seller/${sellerId}/summary`,
  },

  // ── 관전자(스펙테이터) ────────────────────────────────────────
  SPECTATOR: {
    VIEW:              (dealId: number) => `/spectator/view/${dealId}`,
    VIEWERS:           (dealId: number) => `/spectator/viewers/${dealId}`,
    PREDICT:           '/spectator/predict',
    PREDICTIONS:       (dealId: number) => `/spectator/predictions/${dealId}`,
    PREDICTION_COUNT:  (dealId: number) => `/spectator/predictions/${dealId}/count`,
    MY_PREDICTIONS:    '/spectator/my_predictions',
    SETTLE:            (dealId: number) => `/spectator/settle/${dealId}`,
    RANKINGS:          '/spectator/rankings',
  },

  // ── 대시보드 ─────────────────────────────────────────────────
  DASHBOARD: {
    SUMMARY:           '/dashboard/summary',
    BUYER:             '/dashboard/buyer',
    SELLER:            '/dashboard/seller',
    ADMIN:             '/dashboard/admin',
  },

  // ── 인사이트 ─────────────────────────────────────────────────
  INSIGHTS: {
    DEAL_PRICE:        (dealId: number) => `/insights/deal/${dealId}/price`,
    OFFER_TREND:       (dealId: number) => `/insights/deal/${dealId}/offers`,
    MARKET:            '/insights/market',
    CATEGORY:          (category: string) => `/insights/category/${category}`,
  },

  // ── 업로드 ──────────────────────────────────────────────────
  UPLOADS: {
    IMAGE:             '/uploads/image',
    FILE:              '/uploads/file',
    PRESIGNED:         '/uploads/presigned',
  },

  // ── 배송 ────────────────────────────────────────────────────
  DELIVERY: {
    TRACK:             (trackingNumber: string) => `/delivery/track/${trackingNumber}`,
    CARRIERS:          '/delivery/carriers',
    UPDATE_TRACKING:   (reservationId: number) => `/delivery/reservation/${reservationId}/tracking`,
  },

  // ── AI 딜 헬퍼 ───────────────────────────────────────────────
  AI: {
    DEAL_HELPER:       '/ai/deal_helper',
    INTENT_RESOLVE:    '/ai/resolve_intent',
    PRICE_SUGGEST:     '/ai/price_suggest',
  },

  // ── 핑퐁이 AI 에이전트 ────────────────────────────────────────
  PINGPONG: {
    ASK:               '/v3_6/pingpong/ask',
    CHAT:              '/v3_6/pingpong',
    CASES:             '/v3_6/pingpong/cases',
    LOGS:              '/v3_6/pingpong/logs',
  },

  // ── 정산 ────────────────────────────────────────────────────
  SETTLEMENTS: {
    LIST:              '/settlements/',
    DETAIL:            (id: number) => `/settlements/${id}`,
    APPROVE:           (id: number) => `/settlements/${id}/approve`,
    PAYOUT:            (id: number) => `/settlements/${id}/payout`,
    ADMIN_LIST:        '/admin/settlements/',
    ADMIN_APPROVE:     (id: number) => `/admin/settlements/${id}/approve`,
    REFUND_PREVIEW:    '/admin/refund_preview',
  },

  // ── 활동 로그 ────────────────────────────────────────────────
  ACTIVITY: {
    LIST:              '/activity/',
    BUYER:             (buyerId: number) => `/activity/buyer/${buyerId}`,
    DEAL:              (dealId: number)  => `/activity/deal/${dealId}`,
  },

  // ── 시스템/정책 ───────────────────────────────────────────────
  SYSTEM: {
    HEALTH:            '/health',
    POLICY:            '/admin/policy/',
    POLICY_DETAIL:     (key: string) => `/admin/policy/${key}`,
    SIMULATE:          '/admin/simulate',
  },

  // ── 액추에이터 ─────────────────────────────────────────────
  ACTUATORS: {
    LIST:              '/actuators/',
    CREATE:            '/actuators/',
    DETAIL:            (id: number) => `/actuators/${id}`,
  },

} as const;
