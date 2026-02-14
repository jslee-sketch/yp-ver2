# Pricing SSOT (Anchor / Base / Target)

## 목적
역핑의 가격 판단은 “기준값(Anchor/Base)”과 “희망값(Target)”을 분리해,
Anchor가 없어도 서비스가 진행되도록 설계한다.

---

## 핵심 용어
- Target: 구매자 희망가격(사용자 입력)
- Base: 임시 기준가격(서비스 진행용, clamp/내부벤치 혼합)
- Anchor: 비동기 기준가격(외부/내부 데이터 기반, 도착하면 교체/보정)
- Formula Output: 실제 추천/설명에 쓰이는 계산 결과(단, 결제 가격을 강제하지 않음)

---

## 원칙
1) Anchor는 늦게 와도 된다(없어도 flow 진행)
2) Base는 항상 존재해야 한다(결정론적 생성)
3) Target은 사용자의 의도이며, 시스템은 “왜 가능한지/불가능한지”를 설명한다
4) 가격 결과는 UI에서 사용자가 원할 때만 노출
5) 핑퐁이는 가격을 결정하지 않고, 계산 근거/화면 연결만 한다

---

## 데이터 우선순위
- Anchor가 존재하면: Anchor를 기준값으로 사용
- Anchor가 없으면: Base를 기준값으로 사용
- Target은 비교 대상(차이/괴리/합리성 설명용)

---

## 출력 형식(표준)
- base_used: Anchor|Base
- base_value: number
- target_value: number|null
- formula_low: number (공동구매 최저가)
- formula_conditional: number (조건 반영가)
- explain: 3줄 이내 요약 + 근거 링크(선택)
