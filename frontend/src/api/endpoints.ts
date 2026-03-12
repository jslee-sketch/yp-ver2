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
    RESET_PASSWORD:  '/auth/reset-password',
    RESET_PASSWORD_VERIFY: '/auth/reset-password/verify',
    RESET_PASSWORD_CONFIRM: '/auth/reset-password/confirm',
    SELLER_LOGIN:    '/auth/seller/login',
    SELLER_ME:       '/auth/seller/me',
    SOCIAL_AUTHORIZE: (provider: string) => `/auth/social/${provider}/authorize`,
    SOCIAL_CALLBACK:  (provider: string) => `/auth/social/${provider}/callback`,
    SOCIAL_REGISTER:  '/auth/social/register',
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
    VERIFY:          (id: number) => `/sellers/${id}/approve`,
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
    FIND_SIMILAR:      '/deals/find-similar',
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
    WS:                (dealId: number) => `/ws/chat/${dealId}`,
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
    LIST_BUYER:        (buyerId: number) => `/reservations/buyer/${buyerId}`,
    LIST_SELLER:       (sellerId: number) => `/reservations/seller/${sellerId}`,
    DETAIL:            (id: number) => `/reservations/${id}`,
    PAY:               '/reservations/pay',
    SHIP:              (id: number) => `/reservations/${id}/mark_shipped`,
    CONFIRM_ARRIVAL:   (id: number) => `/reservations/${id}/arrival-confirm`,
    CANCEL:            (id: number) => `/reservations/${id}/cancel`,
    REFUND_PREVIEW:    (id: number) => `/reservations/${id}/refund_preview`,
  },

  // ── 예약/결제 (v3.6 통합) ────────────────────────────────────
  RESERVATIONS_V36: {
    LIST:              '/v3_6/reservations',
    CREATE:            '/v3_6/reservations',
    DETAIL:            (id: number) => `/v3_6/by-id/${id}`,
    PAY:               '/v3_6/reservations/pay',
    SHIP:              (id: number) => `/v3_6/reservations/${id}/ship`,
    CONFIRM_ARRIVAL:   (id: number) => `/v3_6/reservations/${id}/arrival-confirm`,
    CANCEL:            '/v3_6/reservations/cancel',
    REFUND:            '/v3_6/reservations/refund',
    REFUND_PREVIEW:    '/v3_6/reservations/refund/preview',
    ADMIN_CANCEL:      (id: number) => `/v3_6/reservations/${id}/admin_cancel`,
    ADMIN_FORCE_SHIP:  (id: number) => `/v3_6/reservations/${id}/admin_force_ship`,
    DISPUTE_OPEN:      (id: number) => `/v3_6/${id}/dispute/open`,
    DISPUTE_CLOSE:     (id: number) => `/v3_6/${id}/dispute/close`,
  },

  // ── 예약 검색/필터 ───────────────────────────────────────────
  RESERVATIONS_SEARCH: {
    SEARCH:            '/v3_6/search',
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
    FCM_TOKEN:         '/notifications/fcm-token',
  },

  // ── 알림 설정 / 관심 상품 ──────────────────────────────────
  NOTIFICATION_SETTINGS: {
    EVENTS:            '/notification-settings/events',
    USER_SETTINGS:     (userId: number) => `/notification-settings/${userId}`,
    SAVE_SETTINGS:     (userId: number) => `/notification-settings/${userId}`,
    BULK:              (userId: number) => `/notification-settings/${userId}/bulk`,
    USER_INTERESTS:    (userId: number) => `/users/${userId}/interests`,
    SAVE_INTERESTS:    (userId: number) => `/users/${userId}/interests`,
    MY_INTERESTS:      '/users/me/interests',
    SAVE_MY_INTERESTS: '/users/me/interests',
    INTEREST_PRESETS:  '/interests/presets',
  },

  // ── 리뷰 ────────────────────────────────────────────────────
  REVIEWS: {
    LIST:              '/reviews/',
    CREATE:            '/reviews/',
    DETAIL:            (id: number)         => `/reviews/${id}`,
    BY_SELLER:         (sellerId: number)   => `/reviews/seller/${sellerId}`,
    BY_BUYER:          (buyerId: number)    => `/reviews/buyer/${buyerId}`,
    SUMMARY:           (sellerId: number)   => `/reviews/seller/${sellerId}/summary`,
    REPLY:             (id: number)         => `/reviews/${id}/reply`,
    LEVEL:             (sellerId: number)   => `/reviews/seller/${sellerId}/level`,
  },

  // ── 고객 문의 ──────────────────────────────────────────────
  CUSTOMER_INQUIRIES: {
    CREATE:            '/customer-inquiries/',
    LIST_SELLER:       (sellerId: number) => `/customer-inquiries/seller/${sellerId}`,
    REPLY:             (id: number) => `/customer-inquiries/${id}/reply`,
    CLOSE:             (id: number) => `/customer-inquiries/${id}/close`,
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
    DEAL_HELPER_IMAGE: '/ai/deal_helper/image-recognize',
    DEAL_HELPER_VOICE: '/ai/deal_helper/voice-recognize',
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
    PDF:               (id: number) => `/settlements/${id}/pdf`,
    WITHHOLDING_PDF:   (actId: number) => `/settlements/actuator/${actId}/withholding-pdf`,
    BY_SELLER:         (sellerId: number) => `/settlements/seller/${sellerId}`,
    ADMIN_LIST:        '/admin/settlements/',
    ADMIN_APPROVE:     (id: number) => `/admin/settlements/${id}/approve`,
    REFUND_PREVIEW:    '/admin/refund_preview',
  },

  // ── 활동 로그 ────────────────────────────────────────────────
  ACTIVITY: {
    LIST:              '/activity/recent',
    BUYER:             (buyerId: number) => `/activity/by-buyer/${buyerId}`,
    DEAL:              (dealId: number)  => `/activity/by-deal/${dealId}`,
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
    PROFILE:           '/actuators/me',
    BY_EMAIL:          (email: string) => `/actuators/by-email?email=${encodeURIComponent(email)}`,
    VERIFY_CODE:       (code: string) => `/actuators/verify-code?code=${encodeURIComponent(code)}`,
    SELLERS:           (id: number) => `/actuators/${id}/sellers`,
    ME_SELLERS:        '/actuators/me/sellers',
    COMMISSIONS:       (id: number) => `/actuators/${id}/commissions`,
    COMMISSIONS_SUMMARY: (id: number) => `/actuators/${id}/commissions/summary`,
    AGREE_CONTRACT:    (id: number) => `/actuators/${id}/agree-contract`,
    CONTRACT_STATUS:   (id: number) => `/actuators/${id}/contract-status`,
    PAYOUT_PREVIEW:    (id: number) => `/actuators/${id}/payout-preview`,
    BUSINESS_INFO:     (id: number) => `/actuators/${id}/business-info`,
  },

  // ── 관리자 ─────────────────────────────────────────────
  ADMIN: {
    DASHBOARD:           '/admin/dashboard/',
    DEALS:               '/admin/deals',
    OFFERS:              '/admin/offers',
    RESERVATIONS:        '/admin/reservations',
    STATS:               '/admin/stats',
    STATS_COUNTS:        '/admin/stats/counts',
    STATS_DAILY:         '/admin/stats/daily',
    STATS_STATUS:        '/admin/stats/status-summary',
    POLICY_YAML:         '/admin/policy/yaml',
    POLICY_YAML_HISTORY: '/admin/policy/yaml/history',
    POLICY_DOCS:         '/admin/policy/docs',
    POLICY_DOC:          (path: string) => `/admin/policy/docs/${encodeURIComponent(path)}`,
    ANOMALY_DETECT:      '/admin/anomaly/detect',
    REPORTS:             '/admin/reports',
    REPORT_RESOLVE:      (id: number) => `/admin/reports/${id}/resolve`,
    USERS_BAN:           '/admin/users/ban',
    USERS_UNBAN:         '/admin/users/unban',
    USERS_BANNED:        '/admin/users/banned',
    ANNOUNCEMENTS:       '/admin/announcements',
    ANNOUNCEMENT:        (id: number) => `/admin/announcements/${id}`,
    NOTIFICATIONS_ALL:   '/admin/notifications/all',
    NOTIFICATIONS_BROADCAST: '/admin/notifications/broadcast',
    REFUND_SIMULATE:     '/admin/refund-simulate',
    POLICY_STATUS:       '/admin/policy/status',
    POLICY_PROPOSALS:    '/admin/policy/proposals',
    POLICY_PROPOSAL:     (id: number) => `/admin/policy/proposals/${id}`,
    UNIFIED_SEARCH:      '/admin/unified-search',
    CUSTOM_REPORT_FIELDS:    '/admin/custom-report/fields',
    CUSTOM_REPORT_QUERY:     '/admin/custom-report/query',
    CUSTOM_REPORT_TEMPLATES: '/admin/custom-report/templates',
    CUSTOM_REPORT_TEMPLATE:  (id: number) => `/admin/custom-report/templates/${id}`,
  },

  // ── 세금계산서 ──────────────────────────────────────────
  TAX_INVOICES: {
    LIST:              '/v3_6/tax-invoices',
    GENERATE:          '/v3_6/tax-invoices/generate',
    CONFIRM:           (id: number) => `/v3_6/tax-invoices/${id}/confirm`,
    ISSUE:             (id: number) => `/v3_6/tax-invoices/${id}/issue`,
    CANCEL:            (id: number) => `/v3_6/tax-invoices/${id}/cancel`,
    BATCH_ISSUE:       '/v3_6/tax-invoices/batch-issue',
    SELLER_ME:         '/v3_6/tax-invoices/seller/me',
    EXPORT_ECOUNT:     '/v3_6/tax-invoices/export-ecount',
    EXPORT_ECOUNT_SALES: '/v3_6/tax-invoices/export-ecount-sales',
    EXPORT_ECOUNT_PURCHASE: '/v3_6/tax-invoices/export-ecount-purchase',
  },

  // ── 판매자 OCR / 사업자 정보 ──────────────────────────
  SELLER_BUSINESS: {
    OCR:               '/sellers/ocr-business',
    UPDATE:            (id: number) => `/sellers/${id}/business-info`,
    VERIFY:            '/sellers/business/verify',
  },

  // ── 행동 수집 + AI 프로파일링 ──────────────────────────
  BEHAVIOR: {
    TRACK:               '/behavior/track',
    LOGS:                '/behavior/logs',
    STATS:               '/behavior/stats',
    ANALYZE:             (type: string, id: number) => `/behavior/analyze/${type}/${id}`,
    ANALYZE_ALL:         '/behavior/analyze-all',
    PROFILES:            '/behavior/profiles',
    PROFILE:             (type: string, id: number) => `/behavior/profiles/${type}/${id}`,
    MATCH_DEALS:         '/behavior/match-deals',
    MATCH_SELLERS:       '/behavior/match-deals-for-sellers',
    HESITATING:          '/behavior/hesitating',
    SELLER_SKIP_PATTERNS: '/behavior/seller-skip-patterns',
  },

  // ── 참여자 조건 관리 ──────────────────────────────────
  USER_CONDITIONS: {
    GET:    (userId: number) => `/admin/users/${userId}/conditions`,
    UPDATE: (userId: number) => `/admin/users/${userId}/conditions`,
    RESET:  (userId: number) => `/admin/users/${userId}/conditions`,
  },

} as const;
