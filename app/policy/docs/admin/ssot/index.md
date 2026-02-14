@'
<!--
ADMIN ONLY
- BUYER/SELLER 응답 근거로 사용 금지
- 내부 운영/정책 SSOT 인덱스
-->

# Yeokping Policy SSOT Index (Admin)

이 폴더(`docs/admin/ssot/`)는 **역핑 정책의 SSOT(Single Source of Truth)** 입니다.  
코드/운영/테스트/에이전트(핑퐁이) 모두가 “정책의 원문”을 참조할 때, **여기에 적힌 내용을 최우선으로** 봅니다.

---

## 0) 규칙 (SSOT 운영 원칙)

- **정책의 최종본은 여기**에만 둔다. (다른 문서/노션/대화는 참고자료)
- 코드에 하드코딩된 정책이 있으면 **SSOT로 끌어올리고**, 코드는 “SSOT를 읽는 구조”로 간다.
- 변경은 “제안 → 검증(테스트/시뮬) → 적용” 순서로 한다.
- 문서명은 가급적 `*_ssot_v1.md` 형태로 버전이 보이게 만든다.
- 새로운 SSOT 파일을 만들면 **반드시 이 index.md에 링크를 추가**한다.

---

## 1) SSOT 문서 목록 (이 폴더 기준)

### A. Pricing SSOT (가격/비교/설명 축)
- `target_vs_anchor_gap_ssot_v1.md`
  - Target(딜방 목표가) vs Anchor(외부 기준가) 괴리 평가(결정/상태/UI/로그 포함)
- `groupbuy_index_gq_ssot_v1.md`
  - 공동구매지수 G(Q) 수학적 구조(카테고리 파라미터, 보수적 초기값, 동적 업데이트 TODO 포함)
- `pingpong_pricing_explain_rules_ssot_v1.md`
  - 핑퐁이 가격 설명 규칙(금지문/4줄 템플릿/노출 레벨/회귀 방지)

### B. Guardrails (차단/경고/승인 루프)
- (가격 가드레일은 위 `target_vs_anchor_gap_ssot_v1.md`가 정본)
- (추후 전사 가드레일이 커지면 별도 `guardrails_ssot_v1.md`를 추가)

### C. Offer 노출/정렬/랭킹
- (현재 offers.py 구현이 SSOT에 가까움. 추후 문서화 시 여기에 `offer_exposure_ssot_v1.md` 추가)

---

## 2) 연결 문서 (이 폴더 밖, 하지만 SSOT에 준하는 상위 문서)

- `docs/admin/ROADMAP_NOW.md`
  - “지금 당장” 진행 순서/우선순위(SSOT STATUS)

---

## 3) TODO / 다음 정리 포인트

- [ ] Target vs Anchor 괴리 임계값(카테고리별 튜닝)은 `target_vs_anchor_gap_ssot_v1.md`에서 파라미터로 확정
- [ ] G(Q) 파라미터(k, x0, max_discount, q_target_default) pricing.yaml 연결 고정
- [ ] 핑퐁이/UX 문구 템플릿을 pricing.yaml(phrasing)과 1:1로 연결(재가공 금지)

'@ | Out-File -Encoding utf8 "docs\admin\ssot\index.md"