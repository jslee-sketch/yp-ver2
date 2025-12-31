from pydantic import BaseModel, Field
from app.policy.params._schema.refund import RefundPolicy
from app.policy.params._schema.time_rules import TimeRulesPolicy
from app.policy.params._schema.offer_exposure import OfferExposurePolicy

class PolicyParams(BaseModel):
    refund: RefundPolicy
    time_rules: TimeRulesPolicy
    offer_exposure: OfferExposurePolicy