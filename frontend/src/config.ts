// 기능별 API 전환 플래그
// true = 실제 API 사용, false = Mock 데이터 유지
export const FEATURES = {
  USE_API_AUTH:         true,  // 인증
  USE_API_DEALS:        true,  // 딜 CRUD
  USE_API_OFFERS:       true,  // 오퍼
  USE_API_RESERVATIONS: true,  // 예약/결제
  USE_API_PINGPONG:     true,  // 핑퐁이 봇
  USE_API_AI:           true,  // AI 딜 헬퍼
};
