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
| primary | `minimax/MiniMax-M2.5` | ≈48 | 1074 ms | 0.30 | 1.20 | 0.03 | 0.375 |
| fallback 1 | `anthropic/claude-haiku-4-5` | ≈37 | 634 ms | 1.00 | 5.00 | 0.10 | 1.25 |
| fallback 2 | `gemini/gemini-3-flash-preview` | ≈45 | 1307 ms | 0.50 | 3.00 | 0.05 | — |
| fallback 3 | `openai/gpt-5.4-mini` | 54 | 614 ms | 0.75 | 4.50 | 0.075 | — |

**Why this order:**
- **MiniMax-M2.5 primary:** cheapest on the chart (~3× cheaper input than Haiku, ~4× cheaper output) and slightly smarter on the Intelligence Index. Sits in the Intelligence-vs-Price "most attractive quadrant." Struct latency ~1.1s is well under the 2s soft budget. Cost-first default.
- **Haiku fallback 1:** Anthropic-ecosystem fallback. Our prompts were authored with Claude's voice in mind, so if MiniMax output style drifts in practice we can swap back to Haiku as primary without changing prompts. Fastest struct latency of the chain (634ms). Worth noting: Haiku's Intelligence Index (≈37) is actually the lowest here — it's the ecosystem-consistency pick, not the quality pick.
- **Gemini 3 Flash fallback 2:** Google infra independence for when both MiniMax and Anthropic are down.
- **GPT-5.4-mini fallback 3:** highest intelligence of this tier (54) and matches Haiku's latency. Placed last because it's the most expensive per-token of the fast tier — use only when cheaper options have failed.

---

## Quality tier (morning pushback, evening follow-up, weekly summary)

These run from APScheduler cron jobs or FastAPI `BackgroundTasks`, not on the Twilio webhook path. Latency budget is therefore **loose** — up to 30s is fine. Quality matters more than speed here.

| Rank | Model | Intel | Struct Latency | In $/M | Out $/M | Cache Read $/M | Cache Write $/M |
|---|---|---:|---:|---:|---:|---:|---:|
| primary | `minimax/MiniMax-M2.5` | ≈48 | 1074 ms | 0.30 | 1.20 | 0.03 | 0.375 |
| fallback 1 | `anthropic/claude-sonnet-4-5` | ≈50 | 1775 ms | 3.00 | 15.00 | 0.30 | 3.75 |
| fallback 2 | `openai/gpt-5.4` | 57 | 1208 ms | 2.50 | 15.00 | 0.25 | — |
| fallback 3 | `gemini/gemini-3.1-pro-preview` | 57 | 10438 ms | 2.00 | 12.00 | 0.20 | — |
| fallback 4 | `anthropic/claude-opus-4-6` | 53 | 2049 ms | 5.00 | 25.00 | 0.50 | 6.25 |

**Why this order:**
- **MiniMax-M2.5 primary:** 10× cheaper input than Sonnet ($0.30 vs $3.00/M) and 12× cheaper output. For an N=1 cost-first system, this pulls expected spend from dollars/day into cents/day. Intelligence Index (~48) sits just below Sonnet (~50) — close enough that the cost delta dominates. Latency (~1.1s struct) is the fastest of the quality tier.
- **Sonnet 4.5 fallback 1:** Anthropic-ecosystem fallback. Our prompts were tuned for Claude voice, so if MiniMax output style drifts or fails validation consistently in practice, swapping primary back to Sonnet requires only an env change.
- **GPT-5.4 fallback 2:** highest frontier intelligence tied with Gemini (57), and **8× faster than Gemini on structured output** in our probe (1.2s vs 10.4s). On a fallback walk, latency matters — we've already lost two providers by this point.
- **Gemini 3.1 Pro fallback 3:** same intelligence as GPT-5.4 (57), cheapest input at $2/M, "most attractive quadrant" on the Intelligence-vs-Price chart. Placed after GPT purely because of the structured-output latency gap.
- **Opus 4.6 fallback 4:** the worst intelligence-per-dollar on the entire Intelligence-vs-Price chart (53 intel at ~$10+ blended per million). Kept as absolute last resort — a different Anthropic model when three other providers have failed.

---

## Operational notes

- **Gemini 3.1 Pro's 10.4s structured-output latency** is the biggest surprise from the probe. Plain text generation is much faster. If we later add a "quality, plain text" route (e.g. for summaries we manually post-process), Gemini moves up.
- **MiniMax-M2.5 outperformed its "lightning" variant** in our probe (1074 ms vs 2337 ms on struct). The lightning variant appears to do hidden reasoning. Using plain M2.5 in both tiers.
- **Cache write cost** shows Anthropic's explicit `cache_creation_input_token_cost` and MiniMax's `cache_creation_input_token_cost`. OpenAI and Gemini do automatic caching with no separate write fee exposed in LiteLLM's registry.
- **Gemini `input_cost_per_token_above_200k_tokens`** doubles input cost past 200k tokens. Irrelevant at N=1 (our max prompt is the weekly summary ~10k tokens).
- **Probe script:** `.venv/bin/python scripts/probe_llm.py` — run this after any model name change, any provider key change, or monthly to catch silent model retirements.

---

## Expected cost at N=1

Envelope math with MiniMax-M2.5 as primary on both tiers:

- ~12 fast-tier calls/day × (avg 500 input + 200 output): ~6k input, 2.4k output/day with MiniMax → **~$0.005/day**
- ~2–3 quality-tier calls/day × (avg 1.5k input + 400 output): ~4.5k input, 1.2k output/day with MiniMax → **~$0.003/day**
- Friday summary: 10k input + 600 output with MiniMax → **~$0.004/week**
- **Expected total: ~$0.25/month at N=1 when MiniMax is healthy.**
- Worst case (every call falls over to Sonnet + Opus): ~$3–4/month. Monitor the heartbeat row's `error_count_24h` to catch persistent MiniMax failover.
