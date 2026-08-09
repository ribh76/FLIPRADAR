# AI Limitations

FlipRadar's AI explanation is optional. The deterministic recommendation engine
calculates every recommendation, score, valuation, and market metric before an
LLM is called. The AI layer can only add a short, validated interpretation.

## What the AI does not do

- It does not set the BUY, PASS, WATCH, HOLD, or SELL result.
- It does not calculate, estimate, or alter prices, returns, fees, or scores.
- It does not receive raw listing payloads, seller data, titles, or marketplace
  responses.
- It must not state prices, numeric claims, marketplace names, listing facts,
  seller facts, or sales facts in its generated card text.
- It is not financial, investment, tax, or legal advice and does not guarantee
  any outcome.

## Evidence and uncertainty

Each AI fact card must cite one supplied calculated metric. Each uncertainty
card must use an uncertainty code that the deterministic analysis explicitly
provided. This reduces unsupported claims but cannot make an LLM perfectly
reliable; users should rely on the deterministic metrics and verify market data
before making purchase or sale decisions.

## Availability and fallbacks

AI narratives are subject to timeout, retry, rate-limit, and provider-availability
controls. If a response is malformed, violates the schema, times out, is rate
limited, or otherwise fails, FlipRadar returns the deterministic analysis without
an AI narrative. The UI shows the narrative status when that occurs.

## Usage telemetry

FlipRadar records model name, prompt version, token counts, retry count, latency,
and estimated cost for successful responses with provider usage data. It does not
log prompts, raw provider payloads, API keys, or user marketplace data. Cost is
an estimate based on configured per-token rates and may differ from final provider
billing because of plan discounts, caching, taxes, or provider pricing changes.
