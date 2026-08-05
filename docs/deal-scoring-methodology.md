# Deal scoring methodology

The deal-discovery engine uses `deal-score-v2`, an auditable 0–100 score that
separates value from the reliability of the listing and its valuation:

| Component | Weight | Input |
| --- | ---: | --- |
| Value | 30% | Discount or premium of landed cost compared with fair value |
| Product match | 15% | Normalized 0–100 product-match confidence |
| Valuation confidence | 15% | Normalized 0–100 fair-value confidence |
| Seller trust | 10% | Normalized 0–100 seller trust score |
| Marketplace trust | 10% | Normalized 0–100 marketplace trust score |
| Condition and completeness | 10% | Listing condition plus completeness state |
| Listing quality | 10% | Normalized 0–100 listing/set-data quality score |

Landed cost is `asking price + shipping`. A positive `discount_percent` means
the landed cost is below fair value; a positive `premium_percent` means it is
above fair value. Exactly fair value has both values at zero.

The value component maps a 25% premium to 0, fair value to 50, and a 25% or
greater discount to 100. The weighted component scores are added, explicit
guardrail penalties are subtracted, then the result is clamped and rounded to a
normalized 0–100 score. Scores are classified as `excellent` (85–100), `good`
(70–84), `fair` (50–69), `risky` (30–49), or `poor` (0–29).

The same reliability inputs produce an independent 0–100 `confidence_score`:
product match and valuation confidence each account for 25%; seller and
marketplace trust each account for 15%; condition/completeness and listing
quality each account for 10%. It is classified as high (80–100), medium
(55–79), or low (0–54).

Guardrails subtract points for unclear (-10), incomplete (-15), suspicious
(-25), and low-quality (<60, -10) listings. Every weighted component, penalty,
base score, final score, and confidence score is returned in `score_breakdown`,
alongside user-facing `explanations`; callers can persist that breakdown with a
deal record.

A listing cannot be scored without a positive fair value. It is returned as
`unscored` with its landed cost and available quality/confidence breakdown so it
can be revisited when valuation data becomes available.
