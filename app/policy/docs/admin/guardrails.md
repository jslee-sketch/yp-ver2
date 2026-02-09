 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# ?댁쁺/?덉쟾 媛?쒕젅??(Guardrails)


## 0. 紐⑹쟻
- ?뺤콉 蹂寃쎌? ?쒕컮濡?諛섏쁺?앹씠 ?꾨땲???쒖븞??猷⑦봽?앸줈 ?댁쁺?쒕떎.
- ?묓릟?대뒗 蹂寃??쒖븞?먯씠硫? ?곸슜? 愿由ъ옄 ?뱀씤/?먯쭊諛고룷/濡ㅻ갚/媛먯궗濡쒓렇媛 ?꾩닔??

## 1. ?뚮옒洹?媛?쒕젅??肄붾뱶 洹쇨굅)
- AUTO_SET_DEADLINES 媛숈? ?뚮옒洹몃뒗 ?댁쁺 ?덉쟾?μ튂濡?臾몄꽌?????栽?8栽?
- ENABLE_DEPOSIT_TRACKING 媛숈? ?쒓린濡앸쭔 ?⑤뒗 ?덇굅?쒋앸룄 DEPRECATED濡?寃⑸━

## 2. 蹂寃??덉쟾 猷⑦봽(?쒖?)
- ?쒖븞(?묓릟) ??愿由ъ옄 ?뱀씤 ???곸슜(?뚮씪誘명꽣/猷??뚮옒洹? ???먯쭊諛고룷 ??紐⑤땲?곕쭅 ??濡ㅻ갚 媛??
- 紐⑤뱺 蹂寃쎌?:
  - before/after
  - 蹂寃쎌옄(actor)
  - ?ъ쑀(reason)
  - 洹쇨굅(evidence_refs)
  - ?곹뼢 踰붿쐞(scope)
  瑜??④릿??

## 3. DEPRECATED 愿由?
- Deposit 愿??猷??ㅺ? 援щ쾭?꾩뿉 ?⑥븘?덉쓬 栽?0栽?
- ?쒗쁽???뺤콉???쒓굅?앸? 臾몄꽌??紐낆떆?섍퀬,
- 肄붾뱶?먯꽌 ?ㅼ떆 ?깆옣?섎㈃ ?뚯뒪??寃利??ㅽ겕由쏀듃濡??〓뒗??

---

## 4) Policy Snapshot SSOT Guardrails (Reservation.policy_snapshot_json)

?뺤콉? ?쒖?湲덉쓽 ?뺤콉?앹씠 ?꾨땲??**嫄곕옒 ?쒖젏??諛뺤젣???뺤콉**??1?쒖쐞 SSOT??  
?곕씪??`Reservation.policy_snapshot_json` ? ?쏶SOT 而⑦뀒?대꼫?앸줈 ?댁쁺?쒕떎.

---

### 4.1 SSOT Container: Reservation.policy_snapshot_json (?쒖? ?ㅽ궎留?

`policy_snapshot_json` ? ?덉빟 ?⑥쐞濡??쒓렇 ?덉빟???뺤콉/?섏닔猷??깃툒?앹쓣 ?④퍡 諛뺤젣?쒕떎.

# ---------------------------------------------------------
    # ??Snapshot Guardrail (EVIDENCE ONLY)
    #
    # time_snapshot / exposure_snapshot ? "寃곗젙(SSOT)"???꾨땲??
    # "洹??쒖젏??怨꾩궛 寃곌낵瑜??④린??利앸튃(Evidence)" ?⑸룄??
    #
    # - ??媛믪씠 ?녾굅???꾨씫) UNKNOWN ?댁뼱???덉빟 ?앹꽦/寃곗젣 濡쒖쭅? ?뺤긽 ?숈옉?댁빞 ?쒕떎.
    # - ?몄텧(Exposure) ?뺤콉???ㅼ젣 ?먮떒/李⑤떒? 'Offer ?쒖텧/?몄텧 濡쒖쭅(??궧/?몄텧 API)'?먯꽌 ?섑뻾?쒕떎.
    # - Reservation??諛뺤젣?섎뒗 exposure_snapshot? CS/?묓릟???ㅻ챸/?ы쁽/?붾쾭源낆쓣 ?꾪븳 罹먯떆+利앸튃?대떎.
    #
    # ?곕씪??
    # - exposure_snapshot.allowed=False ?щ룄 create_reservation()? ?ㅽ뙣?쒗궎吏 ?딅뒗??
    # - wish_price ?녿뒗 寃쎌슦(reason=wish_price_missing)???뺤긽 耳?댁뒪濡?痍④툒?쒕떎.
    # ---------------------------------------------------------


#### ?쒖? ????怨좎젙)
- ?ㅽ띁 ?뺤콉 ?ㅻ깄??痍⑥냼 洹쒖튃)
  - `offer_policy_id`
  - `cancel_rule`
  - `cancel_within_days`
  - `extra_text`
- 寃곗젣 ?쒖젏 ?섏닔猷??ㅻ깄??SSOT)
  - `fee_snapshot`
- 寃곗젣 ?쒖젏 ?깃툒/?곗뼱 ?ㅻ깄??SSOT)
  - `tier_snapshot`

#### ?덉떆(JSON)
```json
{
  "offer_policy_id": 1,
  "cancel_rule": "A3",
  "cancel_within_days": 3,
  "extra_text": "諛곗넚?꾨즺 ??3???대궡 ?⑥닚蹂??痍⑥냼 媛?? ?뺣났諛곗넚鍮꾨뒗 援щℓ??遺??",
  "fee_snapshot": {
    "policy_version": "v0",
    "policy_hash": "aa59fe0e1158d56c",
    "captured_at": "2026-01-04T06:47:47.026732+00:00",
    "keys": {
      "fees.platform_fee_rate": 0.035,
      "fees.pg_fee_rate": 0.033,
      "fees.vat_rate": 0.1,
      "fees.seller_fee_floor": 0.0,
      "fees.seller_fee_ceil": 1.0,
      "fees.points_earn_rate": 0.01
    }
  },
  "tier_snapshot": {
    "policy_version": "v0",
    "policy_hash": "aa59fe0e1158d56c",
    "captured_at": "2026-01-04T08:26:20.547973+00:00",
    "buyer": {
      "buyer_id": 1,
      "tier": "T4",
      "restricted": false,
      "total": 10,
      "paid": 4,
      "fulfillment_rate": 0.4,
      "deposit_percent": 0.0
    },
    "points": { "balance": 0, "grade": "BRONZE" },
    "seller": { "level": "Lv.2", "fee_percent": 0.025, "sold_count": 460, "rating": 4.0 }
  }
}
