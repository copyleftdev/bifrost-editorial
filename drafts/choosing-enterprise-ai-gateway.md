---
title: Migrating from Legacy LLM Infrastructure to an Enterprise AI Gateway
published: false
description: A hands-on migration story — moving a support copilot off direct provider calls onto an enterprise AI gateway, with measured cost and failover results.
tags: ai, llm, devops, tutorial
---

*Disclosure: this post was sponsored by Maxim AI.*

This is a migration story. The legacy stack: a customer-support copilot whose application code called one LLM provider directly, one API key, no fallback, no cache, no spend controls. It worked until it didn't. I rebuilt that stack in miniature — mock providers, deterministic latency, realistic traffic — and then migrated it onto [Bifrost](https://www.getmaxim.ai/bifrost), the open-source enterprise AI gateway ([github.com/maximhq/bifrost](https://github.com/maximhq/bifrost)), and measured the difference. Every number below comes from that run.

## The legacy world, measured

![Step 1: legacy direct-to-provider architecture](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step1-legacy.png)

The traffic pattern is a realistic support mix: 60 requests — 40 FAQ-style prompts (8 distinct questions, each asked 5 times) and 20 one-off questions. Provider latency: 200 ms. Legacy mode hits the provider directly:

```
legacy direct: 60 ok / 0 fail, 9,335 tokens billed, ~201 ms avg
```

Then I killed the provider mid-run, because providers do that:

```
legacy + failure: 34 ok / 26 fail
```

43% of the traffic died with the provider. No fallback existed in the application, so the users got errors. That is the legacy pain in one row: availability is the provider's availability, full stop.

## The migration strategy

Seven steps, each small and reversible. Diagrams follow the same flow.

### Step 1 — Deploy the gateway beside the app

![Step 2: gateway deployed beside the app](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step2-beside.png)

Deploy Bifrost (`docker run -p 8080:8080 maximhq/bifrost`) and configure your existing provider and key in it. Nothing user-facing changes yet — same key, same provider, one new hop.

### Step 2 — Point one low-risk client at the gateway

![Step 3: one client pointed at gateway](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step3-one-client.png)

The [drop-in OpenAI-compatible API](https://docs.getbifrost.ai/providers/supported-providers/overview) means the client change is a base URL, not a rewrite. Other services stay direct until their turn.

### Step 3 — Add a fallback provider

![Step 4: fallback provider added](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step4-fallback.png)

Attach request-level fallbacks (`fallbacks: ["anthropic/support-chat"]`). Cross-provider failover without touching app code — and the response tells you which path it took.

### Step 4 — Turn on caching

![Step 5: semantic caching enabled](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step5-cache.png)

[Semantic caching](https://docs.getbifrost.ai/features/semantic-caching) replays exact matches (and, with an embedding provider, similar ones). FAQ-heavy workloads are the obvious first candidate — measured effect below.

### Step 5 — Issue virtual keys per team

![Step 6: virtual keys per team](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step6-virtual-keys.png)

Every team gets its own [virtual key](https://docs.getbifrost.ai/features/governance/virtual-keys) with model allowlists, budgets, and rate limits. This is the step that makes the platform team popular.

### Steps 6–7 — Wire observability, then cut over

![Step 7: cutover complete](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step7-cutover.png)

Prometheus-native [observability](https://docs.getbifrost.ai/features/observability/default) plugs into your existing Grafana. Then cut over the remaining clients one at a time, with the gateway's request logs as the audit trail.

## What the migrated stack measured

Same traffic, through Bifrost with caching on and a fallback provider configured:

```
via Bifrost: 60 ok / 0 fail, 32 cache hits, 4,363 tokens billed
```

### Cost, in real numbers

At $0.0025 per 1K tokens (a gpt-4o-mini-class rate for illustration):

| | legacy | via Bifrost |
|---|---|---|
| billable tokens | 9,335 | 4,363 |
| cost | $0.0233 | $0.0109 |
| savings | — | **53%** |

The savings came entirely from cache hits on repeated FAQ prompts — the second response carried `cache_hit: true, hit_type: direct` in its `cache_debug` block and replayed with the original `created` timestamp. No provider call, no tokens billed. On a real support workload with much higher volume, that ratio compounds daily.

### Availability, demonstrated

The failover proof, per request. Healthy primary:

```json
"routing_info": {"provider": "openai", "key": "primary", "is_fallback": false}
```

I killed the primary provider and re-sent the identical request with `fallbacks: ["anthropic/support-chat"]`:

```json
"routing_info": {
  "provider": "anthropic", "key": "backup",
  "is_fallback": true,
  "primary_provider": "openai", "primary_model": "support-chat"
}
```

Zero client-side change; the response says exactly what happened. Compare with the legacy run's 26 dead requests. (One honest caveat from my bench: in my mock setup, request-level failover fired reliably on upstream errors, but initial connection-refused to a dead provider did not always trigger the chain — validate failover against your actual providers' failure modes when you test, per the [retries and fallbacks docs](https://docs.getbifrost.ai/features/retries-and-fallbacks).)

### Governance, exercised

A virtual key scoped to the support team's model allowlist (`allowed_models: ["support-chat"]`). The allowed request routes; a request for `premium-model` with the same key returns:

```
"Model 'premium-model' is not allowed for this virtual key"
```

Denied before any provider saw it. Virtual keys also carry budgets and rate limits — the mechanism that ends the "who spent $800 on Opus last night" incident review.

### MCP: the part the legacy stack never had

Legacy architectures bolt tool-use onto apps ad hoc. On the gateway, [MCP](https://docs.getbifrost.ai/mcp/overview) is a first-class surface: I connected a hand-rolled MCP server (one tool, JSON-RPC over HTTP), Bifrost discovered it as a healthy client, and execution went through the gateway explicitly:

```
POST /v1/mcp/tool/execute  {"function":{"name":"benchtools-get_time"}}
→ {"role":"tool","content":"2026-08-27T07:48:21Z"}
```

Two security properties showed up unprompted: tool names are namespaced per client (`benchtools-get_time`) to prevent collisions, and execution without permission fails closed ("tool is not available or not permitted"). Agent traffic gets the same gateway governance as chat traffic.

## The bottom line

Migrating to an enterprise AI gateway is not a rewrite. It is a sequence of small, reversible moves — deploy beside, point one client, add fallback, enable cache, issue keys, observe, cut over. Measured on the rebuilt stack: 53% cost reduction on cacheable traffic, 0 failed requests through a provider kill (vs 26 in legacy), and controls the legacy stack never had. The migration risk is low; the legacy risk was already on your pager.
