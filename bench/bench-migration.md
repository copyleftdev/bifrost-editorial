# Migration bench: legacy vs Bifrost

Setup: mock support-copilot traffic (60 requests: 40 FAQ-duplicates, 20 one-off),
mock OpenAI-compatible providers with deterministic latency (200ms) + usage fields.

## Results

| run | ok | fail | cache hits | billable tokens |
|---|---|---|---|---|
| legacy direct | 60 | 0 | 0 | 9335 |
| legacy + provider failure mid-run | 34 | 26 | 0 | 5280 (26 requests failed outright) |
| via Bifrost (cache enabled) | 60 | 0 | 32 | 4363 |

At $0.0025/1K tokens: $0.0233 -> $0.0109 = 53% savings on this traffic mix.

## Failover evidence (per-request, v1 mock)

healthy: provider=openai, routing_info.provider=openai
post-kill of primary: provider=anthropic, is_fallback=true, primary_provider=openai recorded

## Honest caveat

- Mid-run traffic failover could not be captured in aggregate: v1 mocks answer
  in ~1ms so the 60-request sweep completes before any externally-triggered
  kill lands. Failover is demonstrated per-request instead (above), repeated twice.
- Failover on *initial* connection-refused showed inconsistent behavior in the
  mock setup (fell back for v1 mock, sometimes refused 502 for v2 mock with
  200ms latency). The blog describes request-level fallbacks based on the proven
  path: errors that reach the provider or mid-pool EOFs.
- Cost numbers assume $0.0025/1K tokens for illustration; token counts are
  real, measured by the mock from request text.

## Artifacts

traffic-legacy.json, traffic-legacy-down.json, traffic-gateway.json (raw per-request),
healthy.json, failover.json, cache-run1.json, cache-run2.json, vk-allowed.json,
vk-denied.json, mcp-execute.json
