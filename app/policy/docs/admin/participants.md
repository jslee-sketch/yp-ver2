 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 李몄뿬??Actors) ?뺤콉 ??SSOT v3.6

??븨? ?쒖궗????븷??以묒떖?쇰줈 ?ㅻ챸?댁빞 CS/?묓릟?닿? ?붾뱾由ъ? ?딅뒗??
沅뚰븳 SSOT???꾨옒 ??異뺤쑝濡??뺤쓽?쒕떎.

1) **Action Permissions**: ?꾧? ?대뼡 ?≪뀡???몄텧?????덈뒗媛
2) **State Transitions**: ?곹깭癒몄떊 ??媛?ν븳 ?꾩씠?멸?

---

## 1) ?듭떖 李몄뿬??

### Buyer(援щℓ??
- ???앹꽦/洹몃９ 李몄뿬/?ㅽ띁 ?좏깮/?덉빟/寃곗젣
- ?댁뒋 ?쒓린(?섎텋/遺꾩웳)
- 愿???쇱슦??
  - `/buyers/*`, `/dashboard/buyer/*`, `/insights/buyer/*`
  - `/reservations/buyer/{buyer_id}`

### Seller(?먮ℓ??
- ?ㅽ띁 ?쒖텧/?섎씫/異쒓퀬/?댄뻾
- 由щ럭/?덈꺼 ?곹뼢
- 愿???쇱슦??
  - `/sellers/*`, `/dashboard/seller/*`, `/insights/seller/*`
  - `/offers/*`, `/reservations/seller/{seller_id}`
  - `/reviews/seller/{seller_id}/*`

### Actuator(?≪텛?먯씠??
- ?먮ℓ??紐⑥쭛/愿由?
- ?뺤궛 諛쒖깮 ??而ㅻ????섏랬(ActuatorCommission)
- 愿???쇱슦??
  - `/actuators/*`
  - `/actuators/{actuator_id}/commissions`
  - `/actuators/commissions/payout-due`
  - `/actuators/me/commissions/settle`

### Admin(愿由ъ옄)
- ?뺤콉 蹂寃? ?섎텋 ?꾨━酉?吏묓뻾, ?뺤궛 ?댁쁺, ?쒕??덉씠??
- 愿???쇱슦??
  - `/admin/policy/*`
  - `/admin/refund/preview`
  - `/admin/settlements/*`
  - `/admin/simulate/*`

### System(?쒖뒪??諛곗튂)
- ?쒓컙 ?몃━嫄??먮룞 留뚮즺/?뺤궛 諛곗튂/?뚮┝

### Agent(PingPong)
- ?쒖젙梨낆쭛 + 洹쇨굅(濡쒓렇/?ㅻ깄????湲곕컲?쇰줈 ?ㅻ챸/?쒖븞
- ?댁쁺???뱀씤 ???곸슜 援ъ“媛 紐⑺몴

---

## 2) ?쒖? 媛앹껜(?뺤콉???곸슜?섎뒗 ???

- Deal: 援щℓ???붿껌(??
- Offer: ?먮ℓ???쒖븞(?ㅽ띁)
- Reservation: ?ㅽ띁 ?좏깮/?덉빟(寃곗젣 ?덈룄???쒖옉)
- Payment: 寃곗젣
- Fulfillment: 諛곗넚/?댄뻾
- Review: ?좊ː ?좏샇
- Dispute/Refund: 遺꾩웳/?섎텋
- Settlement: ?뺤궛
- ActuatorCommission: ?≪텛?먯씠??而ㅻ???

---

## 3) 沅뚰븳 SSOT (Action Permissions)

?꾨옒 ACTION_PERMISSIONS媛 ?쒕늻媛 ?대뼡 ?≪뀡???????덈굹?앹쓽 SSOT??

```python
ACTION_PERMISSIONS: Dict[str, Set[str]] = {
    # Reservation lifecycle
    "reservation.create": {"buyer", "system"},
    "reservation.pay": {"buyer", "system"},          # 寃곗젣 ?깃났 webhook/?쒖뒪?쒕룄 ?ы븿 媛??
    "reservation.cancel": {"buyer", "admin", "system"},
    "reservation.expire": {"system", "admin"},

    # Shipping / Fulfillment
    "reservation.mark_shipped": {"seller", "admin", "system"},
    "reservation.confirm_arrival": {"buyer", "admin", "system"},

    # Refund/Dispute (preview???덉쟾?섎땲 ?볤쾶)
    "refund.preview": {"buyer", "seller", "admin", "system", "agent"},
    "refund.force": {"admin", "system"},
}
