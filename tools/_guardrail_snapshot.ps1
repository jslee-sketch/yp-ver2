# tools/_guardrail_snapshot.ps1
# Guardrail Golden Snapshot helper (stable fields only)

Set-StrictMode -Version Latest

function ConvertTo-StableDealSnapshot {
  param([Parameter(Mandatory=$true)] $DealPreview)

  $pack = $DealPreview.pack
  $deal = $pack.deal
  $pricing = $pack.pricing

  # guardrail 위치는 두 케이스 모두 대응:
  # 1) pack.pricing.guardrail
  # 2) pack.guardrail (pricing 없을 때)
  $g = $null
  if ($pricing -and $pricing.guardrail) { $g = $pricing.guardrail }
  elseif ($pack.guardrail) { $g = $pack.guardrail }

  return [ordered]@{
    entity = "deal"
    id = $DealPreview.id
    deal = [ordered]@{
      id = $deal.id
      status = $deal.status
      target_price = $deal.target_price
      qty_target = $deal.qty_target
    }
    guardrail = if ($g) {
      [ordered]@{
        level = $g.level
        reason_codes = @($g.reason_codes)
        badge = $g.badge
        short_title = $g.short_title
        short_body = $g.short_body
      }
    } else { $null }
  }
}

function ConvertTo-StableOfferSnapshot {
  param([Parameter(Mandatory=$true)] $OfferPreview)

  $pack = $OfferPreview.pack
  $offer = $pack.offer
  $deal  = $pack.deal
  $pricing = $pack.pricing

  $g = $null
  if ($pricing -and $pricing.guardrail) { $g = $pricing.guardrail }
  elseif ($pack.guardrail) { $g = $pack.guardrail }

  return [ordered]@{
    entity = "offer"
    id = $OfferPreview.id
    offer = [ordered]@{
      id = $offer.id
      deal_id = $offer.deal_id
      seller_id = $offer.seller_id
      price = $offer.price
      shipping_fee = $offer.shipping_fee
      status = $offer.status
    }
    deal = [ordered]@{
      id = $deal.id
      status = $deal.status
      target_price = $deal.target_price
      qty_target = $deal.qty_target
    }
    pricing = if ($pricing) {
      [ordered]@{
        reference = [ordered]@{
          p_base   = $pricing.reference.p_base
          p_target = $pricing.reference.p_target
          p_anchor = $pricing.reference.p_anchor
        }
        groupbuy = [ordered]@{
          p_group = $pricing.groupbuy.p_group
          q_room  = $pricing.groupbuy.q_room
          q_offer = $pricing.groupbuy.q_offer
          offer_cap_qty = $pricing.groupbuy.offer_cap_qty
        }
        offer_evaluation = [ordered]@{
          seller_offer_price = $pricing.offer_evaluation.seller_offer_price
          expected_price_under_offer_conditions = $pricing.offer_evaluation.expected_price_under_offer_conditions
          phrases = [ordered]@{
            vs_expected = $pricing.offer_evaluation.phrases.vs_expected
            vs_groupbuy_offer_cap = $pricing.offer_evaluation.phrases.vs_groupbuy_offer_cap
          }
        }
        guardrail = if ($g) {
          [ordered]@{
            level = $g.level
            reason_codes = @($g.reason_codes)
            badge = $g.badge
            short_title = $g.short_title
            short_body = $g.short_body
          }
        } else { $null }
      }
    } else { $null }
  }
}