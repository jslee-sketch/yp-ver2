# app/config/feature_flags.py
# YeokPing Feature Flags (dev/sim convenience)
# Version: 3.5

FEATURE_FLAGS = {
    # 신규 판매자 자동 승인(시뮬/개발 편의)
    "AUTO_VERIFY_SELLER": True,
    # Deal/Offer 생성 시 DeadTime 고려 마감 자동 계산
    "AUTO_SET_DEADLINES": True,
    # Deposit 기능(기록만) 활성화
    "ENABLE_DEPOSIT_TRACKING": True,
}