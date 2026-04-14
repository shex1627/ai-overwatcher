# LLM Model Chains

Source of truth for which models serve which call type, in what order, and why.

- **Intel** = Artificial Analysis Intelligence Index (higher = smarter), from [artificialanalysis.ai/models](https://artificialanalysis.ai/models) April 2026. `≈` = approximate; exact index not shown for all fast-tier models.
- **Struct latency** = observed p50 on Instructor structured-output calls via LiteLLM, measured by [scripts/probe_llm.py](../scripts/probe_llm.py). Plain-text latency is typically 30–60% lower.
- **Costs** = USD per million tokens, pulled from LiteLLM's `model_cost` registry.
- **Cache write** = empty cell means the provider doesn't expose explicit cache-write pricing (Gemini/OpenAI handle caching implicitly).

Column order: `Model → Intel → Latency → In → Out → Cache Read → Cache Write`. Intelligence first because it gates "is this tier appropriate"; latency second because it gates "can this run on the hot path"; costs last, grouped input-side → output-side.

---

## Fast tier (classifier, warm-ack, timer parser)

Budget target: **<2s soft, <5s hard**. These calls sit behind the Twilio webhook, so total roundtrip must clear under 10s. The fast-tier primary is always tried first; we only walk the chain on timeout, rate limit, or schema-validation failure.

| Rank | Model | Intel | Struct Latency | In $/M | Out $/M | Cache Read $/M | Cache Write $/M |
|---|---|---:|---:|---:|---:|---:|---:|
| primary | `anthropic/claude-haiku-4-5` | ≈37 | 634 ms | 1.00 | 5.00 | 0.10 | 1.25 |
| fallback 1 | `minimax/MiniMax-M2.5-highspeed` | ≈48 | — | 0.30 | 1.20 | 0.03 | 0.375 |
| fallback 2 | `gemini/gemini-3-flash-preview` | ≈45 | 1307 ms | 0.50 | 3.00 | 0.05 | — |
| fallback 3 | `openai/gpt-5.4-mini` | 54 | 614 ms | 0.75 | 4.50 | 0.075 | — |

**Why this order:**
- **Haiku primary:** fastest struct latency of the chain (634ms), well under the 2s soft budget. Our prompts were authored with Claude's voice, so structured-output adherence is strongest here. MiniMax was previously primary for cost, but observed latency from this server (7–13s) made it unusable on the hot path — it consistently blew the 5s hard timeout.
- **MiniMax-M2.5-highspeed fallback 1:** cheapest option (~3× cheaper input than Haiku). The `highspeed` variant is faster than plain M2.5. Used as first fallback for cost savings when Anthropic is down.
- **Gemini 3 Flash fallback 2:** Google infra independence for when both Anthropic and MiniMax are down.
- **GPT-5.4-mini fallback 3:** highest intelligence of this tier (54) and matches Haiku's latency. Placed last because it's the most expensive per-token of the fast tier — use only when cheaper options have failed.

---

## Quality tier (morning pushback, evening follow-up, weekly summary)

These run from APScheduler cron jobs or FastAPI `BackgroundTasks`, not on the Twilio webhook path. Latency budget is therefore **loose** — up to 30s is fine. Quality matters more than speed here.

| Rank | Model | Intel | Struct Latency | In $/M | Out $/M | Cache Read $/M | Cache Write $/M |
|---|---|---:|---:|---:|---:|---:|---:|
| primary | `minimax/MiniMax-M2.7` | ≈50 | — | — | — | — | — |
| fallback 1 | `anthropic/claude-sonnet-4-5` | ≈50 | 1775 ms | 3.00 | 15.00 | 0.30 | 3.75 |
| fallback 2 | `openai/gpt-5.4` | 57 | 1208 ms | 2.50 | 15.00 | 0.25 | — |
| fallback 3 | `gemini/gemini-3.1-pro-preview` | 57 | 10438 ms | 2.00 | 12.00 | 0.20 | — |
| fallback 4 | `anthropic/claude-opus-4-6` | 53 | 2049 ms | 5.00 | 25.00 | 0.50 | 6.25 |

**Why this order:**
- **MiniMax-M2.7 primary:** newest MiniMax model, Intelligence Index ~50 (matches Sonnet) at a fraction of the cost. Quality tier runs from cron/BackgroundTasks where MiniMax's higher latency from this server (7–13s) is acceptable — no Twilio webhook timeout pressure. Cost-first default for an N=1 system.
- **Sonnet 4.5 fallback 1:** Anthropic-ecosystem fallback. Our prompts were tuned for Claude voice, so if MiniMax output style drifts or fails validation consistently in practice, swapping primary back to Sonnet requires only an env change.
- **GPT-5.4 fallback 2:** highest frontier intelligence tied with Gemini (57), and **8× faster than Gemini on structured output** in our probe (1.2s vs 10.4s). On a fallback walk, latency matters — we've already lost two providers by this point.
- **Gemini 3.1 Pro fallback 3:** same intelligence as GPT-5.4 (57), cheapest input at $2/M, "most attractive quadrant" on the Intelligence-vs-Price chart. Placed after GPT purely because of the structured-output latency gap.
- **Opus 4.6 fallback 4:** the worst intelligence-per-dollar on the entire Intelligence-vs-Price chart (53 intel at ~$10+ blended per million). Kept as absolute last resort — a different Anthropic model when three other providers have failed.

---

## Operational notes

- **Gemini 3.1 Pro's 10.4s structured-output latency** is the biggest surprise from the probe. Plain text generation is much faster. If we later add a "quality, plain text" route (e.g. for summaries we manually post-process), Gemini moves up.
- **MiniMax latency from bookhouse is 7–13s** on structured output, far above the probe benchmarks (which likely ran from a lower-latency network). This made MiniMax unusable as fast-tier primary — Haiku at 634ms is the practical choice. Quality tier tolerates the latency since it runs off-path.
- **MiniMax-M2.5-highspeed** is the `highspeed` variant of M2.5 (same quality, faster inference). Used as fast-tier fallback. **MiniMax-M2.7** is the newest model (Intelligence ~50), used as quality-tier primary.
- MiniMax models newer than M2.5 are not yet in LiteLLM's model registry but work via pass-through to MiniMax's API.
- **Cache write cost** shows Anthropic's explicit `cache_creation_input_token_cost` and MiniMax's `cache_creation_input_token_cost`. OpenAI and Gemini do automatic caching with no separate write fee exposed in LiteLLM's registry.
- **Gemini `input_cost_per_token_above_200k_tokens`** doubles input cost past 200k tokens. Irrelevant at N=1 (our max prompt is the weekly summary ~10k tokens).
- **Probe script:** `.venv/bin/python scripts/probe_llm.py` — run this after any model name change, any provider key change, or monthly to catch silent model retirements.

---

## Expected cost at N=1

Envelope math with Haiku as fast-tier primary, MiniMax-M2.7 as quality-tier primary:

- ~12 fast-tier calls/day × (avg 500 input + 200 output): ~6k input, 2.4k output/day with Haiku → **~$0.018/day**
- ~2–3 quality-tier calls/day × (avg 1.5k input + 400 output): ~4.5k input, 1.2k output/day with MiniMax → **~$0.003/day**
- Friday summary: 10k input + 600 output with MiniMax → **~$0.004/week**
- **Expected total: ~$0.65/month at N=1 when both providers are healthy.**
- Worst case (every call falls over to Sonnet + Opus): ~$3–4/month. Monitor the heartbeat row's `error_count_24h` to catch persistent failover.
