---
title: Migrating Legacy LLM Infrastructure to an AI Gateway
published: false
description: A hands-on migration off direct provider calls onto an AI gateway — configs, screenshots, and measured cost results.
tags: ai, llm, devops, tutorial
---

Your support copilot started as a weekend prototype: one model, one provider, one API key in an env var. Then it became production, and you inherited its weaknesses: the provider's availability is your availability, every retry is your code, spend is a mystery until the invoice, and agents bolt tool-use on however they can. This post migrates that stack onto an enterprise AI gateway — and actually runs the migration, with the raw outputs to show for it.

The gateway here is [Bifrost](https://www.getmaxim.ai/bifrost), an open-source ([github.com/maximhq/bifrost](https://github.com/maximhq/bifrost), Apache-2.0) gateway written in Go, presenting a single OpenAI-compatible API across 23+ providers. I rebuilt the legacy stack locally — mock providers with deterministic latency, a realistic traffic pattern — and moved it behind Bifrost step by step.

## The legacy baseline, measured

![Step 1: legacy direct-to-provider architecture](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step1-legacy.png)

A support copilot's traffic has a shape: mostly repeated FAQ-style questions, plus one-off queries. My traffic mix: 60 requests — 40 FAQ prompts (8 distinct questions asked 5 times each) plus 20 one-offs. Mock provider latency: 200 ms.

Run 1, direct to the provider:

```
legacy: 60 ok / 0 fail, 9,335 tokens billed, ~201 ms avg latency
```

Run 2 — the provider dies mid-sweep, as providers do:

```
legacy + failure: 34 ok / 26 fail
```

26 requests — 43% — failed outright. Nothing in the legacy stack retries across providers because nothing can: the app speaks one provider's API. And availability is only the loudest problem. The quieter ones: every team's service embeds the same shared key (one key's quota is everyone's ceiling, and revoking it breaks everyone at once), there is no per-team attribution of spend, and the only way to cut cost on repeated questions is to build caching yourself — request normalization, hash keys, TTLs, invalidation — inside the application. That is the whole argument for a gateway in one row of output.

## The migration, step by step

Seven moves, each reversible. Diagrams follow the flow.

### 1. Deploy the gateway beside the app

![gateway beside the app](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step2-beside.png)

```bash
docker run -p 8080:8080 maximhq/bifrost
```

One config file wires your existing provider and key; the app keeps working untouched. Mine, reduced to the bones:

```json
{
  "providers": {
    "openai": {
      "keys": [{ "name": "primary", "value": "mock-key", "weight": 1.0,
                 "models": ["support-chat"] }],
      "network_config": { "base_url": "http://provider:9001",
                          "default_request_timeout_in_seconds": 30 }
    }
  }
}
```

The [gateway setup guide](https://docs.getbifrost.ai/quickstart/gateway/setting-up) covers the web-UI alternative, and there is a [Go SDK](https://docs.getbifrost.ai/quickstart/go-sdk/setting-up) if you want the gateway embedded rather than adjacent.

### 2. Point one low-risk client at the gateway

![one client pointed](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step3-one-client.png)

The [OpenAI-compatible API](https://docs.getbifrost.ai/providers/supported-providers/overview) means the client change is a base URL — `api.openai.com` → `localhost:8080` — not a rewrite. Every request now flows through a hop you control. Screenshot of the providers page after this step:

![Bifrost UI: providers configured](https://copyleftdev.github.io/bifrost-editorial/assets/screenshots/providers.png)

### 3. Add a fallback provider

![fallback added](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step4-fallback.png)

A second provider config (`anthropic` in my bench) plus a request-level fallback chain:

```json
{
  "model": "openai/support-chat",
  "messages": [{"role": "user", "content": "hi"}],
  "fallbacks": ["anthropic/support-chat"]
}
```

Then the proof. Healthy primary:

```json
"routing_info": {"provider": "openai", "key": "primary", "is_fallback": false}
```

I killed the primary provider's process and re-sent the identical request:

```json
"routing_info": {
  "provider": "anthropic", "key": "backup",
  "is_fallback": true,
  "primary_provider": "openai", "primary_model": "support-chat"
}
```

The request succeeded on the backup and the response says exactly what happened — `is_fallback: true` with the failed primary recorded. That audit trail is what you want at 2 a.m.: not just "it kept working," but "it kept working this way." The [retries and fallbacks docs](https://docs.getbifrost.ai/features/retries-and-fallbacks) cover chained fallbacks and per-provider retry counts.

One honest caveat from my bench: failover on *initial* connection-refused (provider already dead before the first connect) was inconsistent in my mock setup — it fired reliably when the upstream errored or the connection dropped mid-pool, but a cold connection-refused sometimes returned a 502 instead of failing through. Validate failover against your providers' real failure modes before you trust it in production.

### 4. Turn on caching

![cache enabled](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step5-cache.png)

[Semantic caching](https://docs.getbifrost.ai/features/semantic-caching) has two modes: exact-match (direct hash, no embeddings needed) and embedding-based similarity. Config for direct mode with a Redis Stack vector store:

```json
"plugins": [{
  "name": "semantic_cache",
  "config": { "dimension": 1,
              "vector_store_namespace": "BifrostBench",
              "default_cache_key": "support-cache",
              "ttl": "5m" }
}]
```

Two identical requests, one cache key. The second response:

```json
"cache_debug": {
  "cache_hit": true,
  "cache_id": "1cf8a91b-c115-57bf-97a0-fc821dc4de1e",
  "hit_type": "direct",
  "cache_hit_latency": 0
}
```

Same `created` timestamp as the first response — it was replayed, not re-fetched. Zero provider call, zero tokens. (Practical note: this needed Redis Stack with the RediSearch module; plain Redis lacks the `FT.*` commands the index wants.)

### 5. Issue virtual keys per team

![virtual keys](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step6-virtual-keys.png)

[Virtual keys](https://docs.getbifrost.ai/features/governance/virtual-keys) are the governance primitive: per-team keys carrying model allowlists, budgets, and rate limits. Declared in config for the support team:

```json
"governance": {
  "virtual_keys": [{
    "id": "vk-support-team",
    "value": "sk-bf-support-team",
    "provider_configs": [{
      "provider": "openai",
      "allowed_models": ["support-chat"], "key_ids": ["*"]
    }]
  }]
}
```

The allowed request routes normally. A request for `premium-model` with the same key:

```
"Model 'premium-model' is not allowed for this virtual key"
```

Denied at the gateway before any provider saw it. The same key machinery carries [budgets and rate limits](https://docs.getbifrost.ai/features/governance/budget-and-limits) — the mechanism that ends the "who spent $800 on Opus last night" incident review. Screenshot of the key in the governance UI:

![Virtual Keys page](https://copyleftdev.github.io/bifrost-editorial/assets/screenshots/virtual-keys.png)

### 6. Wire observability and agent tooling

Bifrost exports Prometheus metrics natively and logs every request with routing context — provider chosen, fallback index, cache behavior, token counts, latency split into gateway vs upstream time. That last distinction matters: when a provider slows down, you see `upstream_latency` grow while gateway overhead stays flat, so you know whose pager to page. See the [observability docs](https://docs.getbifrost.ai/features/observability/default). And for agent traffic, [MCP](https://docs.getbifrost.ai/mcp/overview) is a first-class surface: the gateway brokers tool calls with explicit execution (no auto-execution unless you opt in).

I hand-rolled a minimal MCP server (one tool, JSON-RPC over HTTP) and registered it as a client. The client list reported `state: healthy` with `get_time` discovered. Execution went through the gateway explicitly:

```
POST /v1/mcp/tool/execute  {"function":{"name":"benchtools-get_time","arguments":"{}"}}
→ {"role":"tool","content":"2026-08-27T07:48:21Z"}
```

Two security properties surfaced unprompted: tool names are namespaced per client (`benchtools-get_time`) to prevent collisions between servers, and execution without permission fails closed ("tool is not available or not permitted"). Agent traffic gets the same governance as chat traffic.

### 7. Cut over with an audit trail

![cutover complete](https://copyleftdev.github.io/bifrost-editorial/assets/diagrams/step7-cutover.png)

Remaining clients migrate one at a time — each is a base-URL change with the gateway's request log as your audit trail. The Logs view after a few requests:

![LLM Logs](https://copyleftdev.github.io/bifrost-editorial/assets/screenshots/logs.png)

## The measured payoff

Same 60-request traffic, now through Bifrost with the cache on and the fallback wired:

```
via Bifrost: 60 ok / 0 fail, 32 cache hits, 4,363 tokens billed
```

At an illustrative $0.0025 per 1K tokens:

| | legacy | via Bifrost |
|---|---|---|
| billable tokens | 9,335 | 4,363 |
| cost | $0.0233 | $0.0109 |
| cache hits | 0 | 32 |
| failed requests (provider kill) | 26 | 0 |
| savings | — | **53%** |

The savings came entirely from replayed cache hits — no provider call, no tokens. On a support workload that repeats questions daily, that ratio compounds. The availability delta speaks for itself: 0 failures through a provider kill, against 26 in the legacy run.

## The bottom line

Migrating to an enterprise AI gateway is not a rewrite. It is a sequence of small, reversible moves — deploy beside, point one client, add fallback, enable cache, issue keys, wire observability, cut over. Measured on the rebuilt stack: 53% cost reduction on cacheable traffic, zero failed requests through a provider kill, and governance the legacy stack never had. The migration risk is low; the legacy risk is already on your pager.
