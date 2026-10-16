"""Provider usage and optional cost estimates; pricing is operator supplied."""
import json
import math
import os
from prometheus_client import Counter

REQUESTS = Counter("ai_provider_requests_total", "Actual provider HTTP attempts", ["provider", "operation"])
TOKENS = Counter("ai_provider_tokens_total", "Reported usage tokens", ["provider", "operation", "kind"])
COST = Counter("ai_provider_estimated_cost_usd_total", "Estimate using configured rates, not billing totals",
               ["provider", "operation"])
MISSING_COST = Counter("ai_provider_unpriced_responses_total", "Responses without complete usage/pricing",
                       ["provider", "operation"])


def record_gemini_usage(model, operation, response):
    usage = response.get("usageMetadata") or {}
    if not isinstance(usage, dict):
        usage = {}
    fields = {"input": "promptTokenCount", "output": "candidatesTokenCount", "cached": "cachedContentTokenCount",
              "thinking": "thoughtsTokenCount"}
    counts = {}
    for kind, field in fields.items():
        count = usage.get(field)
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            counts[kind] = count
            TOKENS.labels("gemini", operation, kind).inc(count)
    estimate = None
    try:
        rates = json.loads(os.getenv("AI_PRICING_JSON", "{}"))[model]
        inp, out = float(rates["input"]), float(rates["output"])
        cached = counts.get("cached", 0)
        cache_rate = float(rates["cached_input"]) if cached else inp
        if not all(math.isfinite(x) and x >= 0 for x in (inp, out, cache_rate)):
            raise ValueError("Invalid rates")
        if cached > counts["input"]:
            raise ValueError("Invalid cached usage")
        estimate = ((counts["input"] - cached) * inp + cached * cache_rate
                    + (counts["output"] + counts.get("thinking", 0)) * out) / 1_000_000
        if not math.isfinite(estimate):
            estimate = None
            raise ValueError("Non-finite cost")
    except (KeyError, TypeError, ValueError):
        MISSING_COST.labels("gemini", operation).inc()
    if estimate is not None:
        COST.labels("gemini", operation).inc(estimate)
    return estimate
