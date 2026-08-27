#!/usr/bin/env python3
"""Traffic generator: 60 requests, support-copilot mix.
- 40 FAQ requests: 8 distinct repeated prompts (5 duplicates each)
- 20 one-off requests
Legacy mode: all go to the primary base URL; a provider-down event mid-run
means those requests fail (no failover in legacy).
Gateway mode: same traffic to Bifrost with fallback + cache."""
import json, time, urllib.request, urllib.error, sys

URLS = {
    "legacy":  "http://localhost:9001/v1/chat/completions",
    "gateway": "http://localhost:8080/v1/chat/completions",
    "gateway-cache": "http://localhost:8080/v1/chat/completions",
}
FAQ = [
    "what is the refund policy?",
    "how do I reset my password?",
    "where is my invoice?",
    "how do I upgrade my plan?",
    "what are your support hours?",
    "how do I cancel my subscription?",
    "do you offer student discounts?",
    "how do I export my data?",
]
ONOFF = [f"custom question #{i} about my account" for i in range(20)]

def call(url, prompt, cache_key=None, model="openai/support-chat", fallback=None):
    body = {"model": model, "messages": [{"role":"user","content":prompt}]}
    if fallback: body["fallbacks"] = [fallback]
    headers = {"Content-Type": "application/json"}
    if cache_key: headers["x-bf-cache-key"] = cache_key
    if url.startswith("http://localhost:8080"):  # gateway mode target label
        model_to_use = model.split("/",1)[1] if "/" in model else model
        body["model"] = f"openai/{model_to_use}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
            dt = time.time() - t0
            usage = resp.get("usage", {})
            cache = (resp.get("extra_fields") or {}).get("cache_debug", {})
            return {"ok": True, "lat_ms": dt*1000,
                    "total_tokens": usage.get("total_tokens", 0),
                    "cache_hit": cache.get("cache_hit", False),
                    "provider": (resp.get("extra_fields", {}) or {}).get("routing_info", {}).get("provider") or "openai"}
    except Exception as e:
        return {"ok": False, "lat_ms": (time.time()-t0)*1000, "total_tokens": 0,
                "cache_hit": False, "provider": None, "error": str(e)[:80]}

def run(mode, down_at=None):
    url = URLS["legacy" if mode == "legacy-down" else ("gateway" if mode.startswith("gateway") else mode)]
    results = []
    n = 0
    for faq_prompt in FAQ:
        for _ in range(5):  # 5 duplicates each
            results.append(call(url, faq_prompt,
                                cache_key="migration-bench" if mode=="gateway" else None,
                                fallback="anthropic/support-chat" if mode in ("gateway","gateway-cache") else None))
            n += 1
            if down_at and n == down_at:
                print(f"[event] provider goes DOWN at request {n}", file=sys.stderr)
    for p in ONOFF:
        results.append(call(url, p,
                            cache_key="migration-bench" if mode=="gateway" else None,
                            fallback="anthropic/support-chat" if mode in ("gateway","gateway-cache") else None))
    return results

if __name__ == "__main__":
    mode = sys.argv[1]
    results = run(mode)
    agg = {
        "mode": mode,
        "requests": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "fail": sum(1 for r in results if not r["ok"]),
        "cache_hits": sum(1 for r in results if r["cache_hit"]),
        "tokens": sum(r["total_tokens"] for r in results),
        "lat_avg": round(sum(r["lat_ms"] for r in results)/len(results), 1),
        "lat_p95": round(sorted(r["lat_ms"] for r in results)[int(.95*len(results))], 1),
    }
    print(json.dumps(agg, indent=2))
    json.dump(results, open(f"/home/ops/Project/bifrost-editorial/bench/traffic-{mode}.json","w"))
