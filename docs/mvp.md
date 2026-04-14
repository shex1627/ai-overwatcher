# Overwatcher MVP (v2 — updated)

One weekend of build time. Runs on you for 14 days. Answers one question: **does getting pinged by a text-based accountability agent actually change how you spend your time?**

If yes, extend. If no, you learned something cheap.

> **Update note:** This version incorporates findings from `behavior-science.md` (Gollwitzer if-then, Fogg/Clear reward closure, Eyal internal triggers, Flow challenge/skill balance) and `feedback-cycles.md` (mode-as-first-class, on-demand check-ins, warm LLM-routed inbound). It replaces the original bookend-only MVP.

---

## The MVP in one paragraph

Every morning the agent texts you: "What are you working on today? Top 1-3 items, in if-then format." You reply. If your reply is vague or in abstract form, it fires one follow-up to sharpen it into `if [time/trigger], then [specific action]`. Every reply gets a warm one-line acknowledgment back, not a silent receipt. During the day, you can text the agent anything — `start`, `stuck`, `done`, `quiet`, or just a free-form progress note — and it routes through the LLM and responds like a person, not a form. At 9pm it asks how it went, and if drift is reported it asks one follow-up about the internal trigger ("what were you feeling right before?"). Every row lands in Google Sheets. Every Friday, an LLM reads the week and texts you a 4-6 sentence summary with a pattern and an identity line. That's the product.

---

## What's IN the MVP

### 1. Morning intent SMS with if-then pushback
**Prompt:** "Good morning. What are your top 1-3 items for today? Try if-then format — e.g. 'if it's 10am, then I open the design doc and do 30 min on section 2.'"
**Behavior:** If the reply is vague OR not in if-then form, fire **one** follow-up: "Turn it into an if-then so it triggers on its own. What's the situation and the first action?"
**Why in:** This is the single strongest intervention in the behavior-change literature. Gollwitzer meta-analysis: 94 studies, 8000+ participants, medium-to-large effect sizes on goal attainment. Cost: one prompt. Expected impact: real.
**Why capped at one follow-up:** nagging erodes trust faster than imperfect plans hurt outcomes.

### 2. Warm acknowledgment on every inbound reply
**Behavior:** After any user message, send a short warm reply (1-2 sentences) that references what they said. Not "Logged." — more like "Nice, that's a sharp plan. Go get it."
**Why in:** Clear's 4th law (Make it Satisfying) + Fogg's immediate celebration principle. A silent Sheets append feels like shouting into a void. Closure is what makes the user text back *next* time.
**Tone rules:** 1-3 sentences, specific to what they sent, encouraging without flattery, never scold, no emojis unless they used one first.

### 3. On-demand check-ins (inbound-first flexibility)
**Behavior:** The user can text the agent any time. Every inbound message runs through an LLM classifier that routes to one of:
- **Command** (`start X 30min`, `stuck`, `done`, `quiet N hr`) → execute + warm reply
- **Progress note** (free-form: "halfway through design, section 2 is messier than i thought") → log as `progress`, short acknowledgment
- **Question** ("should I switch tasks?") → short coaching-style reply, not a decision
- **Emotional** ("this is overwhelming") → acknowledge first, then one concrete next-step suggestion

**Why in:** The user always knows their state better than the system. On-demand access is what turns a scheduled pinger into an accountability partner. It's also the cadence-flexibility pressure-release valve — if daily feels wrong, the user can pull check-ins without the app having to guess.
**Cost:** trivial on top of the inbound webhook you're already building.

### 3a. User-declared timeboxes with auto-check-back
**Behavior:** When the user declares a timebox — either via explicit command (`start design 30min`) or inside a morning/free-form message ("I'll spend 30 min on the design doc") — the agent schedules a check-back for that task at the declared time.

**Explicit command path:**
- User: `start design 30min`
- Agent: "Timer set. 30 min on design. Go."
- At T+30 (with a 2-min grace buffer): "30 min on design — how'd it go? Done, keep going, or stuck?"

**Implicit parse path (from morning intent or free-form):**
- User (in morning reply): "If it's 10am, then I spend 30 min on design section 2."
- Agent: "Sharp plan. Want me to check back at 10:32?"
- User: `yes` / `no` / ignores → default to no, respect their non-reply.

**Rules:**
- **Grace window:** fire at T+2 minutes, not exactly T. Avoids interrupting mid-thought.
- **One check-back per timer.** If user doesn't reply to the check-back, log "no response" and move on. No re-pings.
- **Cancellable:** `quiet` or `cancel design` kills the pending check-back. Don't make the user earn silence.
- **Stackable:** multiple live timers OK (stew at 30 min, design at 60 min). Sheet tracks each with a `timer_id`.
- **Message is warm and specific:** references the declared task and time, not "timer expired."

**Why in (despite heartbeat mode being OUT):** This is user-initiated, not system-initiated. The user opted into the specific check-back moment. That's a completely different UX from "app pings every 60 min whether you wanted it or not." Also: this was literally in the original product sketch ("either ai sets a timer for 30min and check back for me") — the timebox negotiation feature is the whole point of proactive accountability, just done with consent.

**Cost:** one scheduled-job API call per declared timer + parsing logic in the LLM-routed inbound handler. Few hours on top of section 3.

### 3b. Mid-block check-ins (conditional, not default)
**Behavior:** A scheduled check-in *during* an active timer, with rules that protect flow state.

**Default rules:**
| Timer length | Mid-check? |
|---|---|
| ≤ 45 min | No. End-check only. |
| 45-90 min | Optional. Agent asks at start: "Mid-check at 45?" Default no. |
| > 90 min | Yes, at ~50%. |
| User said `heartbeat me` or is in heartbeat mode | Yes, at ~50% regardless of length. |

**Why the length cutoffs:** Flow entry takes 15-20 minutes (Csikszentmihalyi). A mid-check inside a short block destroys the thing the user was protecting by declaring the timebox. Only blocks long enough to have both flow-entered *and* be at meaningful drift risk justify the interruption.

**Mid-check message is lighter than end-check:** one line, one-word replies accepted.
- "Halfway through design. On track? `yes` / `stuck` / `switching`"

**Passive on-track suppression:** If the user voluntarily texts a progress note within the last 20 minutes of a live timer, skip the scheduled mid-check. The signal has already been received; asking again would feel like the system wasn't listening.

**`stuck` during an active timer — the important case:**
1. Pause the timer (mark, don't end)
2. Fire the internal-trigger question ("what were you feeling right before?")
3. Offer one concrete next step or a short break
4. Resume the timer after the user's reply, or let them cancel

This is the highest-value mid-block interaction in the whole product. It's user-initiated so there's no flow-interruption cost, and it catches drift at the exact moment it's happening — when the internal trigger is still fresh in the user's awareness.

**Cost:** a conditional branch on the existing scheduled-job logic plus the `stuck`-while-active handler. Small.

### 4. Mode word in the morning reply (cadence as first-class)
**Behavior:** User can start their morning reply with `bookend`, `blocks`, or `heartbeat` to set that day's cadence. Default is `bookend` (the MVP's daily pair). Other modes are stubbed and log the preference for v2.
**Why in:** Committing to mode as a concept on day one means v2's richer cadences don't require a rewrite. Data captured about which mode the user picks is itself a signal.

### 5. Evening reality SMS with internal-trigger follow-up
**Prompt:** "How did today go? What happened with: [this morning's items]?"
**Conditional follow-up:** If the user reports drift ("got pulled into a stream," "didn't start," "avoided"), fire one: "What were you feeling right before that happened? Bored, stuck, anxious, avoiding something?"
**Why in:** Eyal's internal-trigger insight. Distraction is a symptom; the feeling underneath is the cause. Logging the pattern (stuck → stream, anxious → scrolling) over 2-4 weeks surfaces the actual intervention target, which is never "more willpower."

### 6. Google Sheets storage
**Schema:** `timestamp | direction (in/out) | type (morning/evening/followup/progress/command/weekly/heartbeat) | mode (bookend/blocks/heartbeat) | raw_text | parsed (JSON: items, if_then, internal_trigger, etc.)`
**Why in:** Zero-friction viewing from phone or laptop. LLM can read back on Friday. Free. No DB to maintain.
**Why not Postgres or JSON:** Postgres is overkill. JSON on disk needs a separate viewer. Sheets is the viewer.

### 7. Friday weekly summary with identity line + pattern
**Behavior:** LLM reads the week's rows, texts back 4-6 sentences: (a) what you said you'd do, (b) what actually happened, (c) one pattern (e.g., "3 of 5 days, drift followed a stuck-on-hard-task moment"), (d) one identity line ("This was a week where you showed up as someone who ships design docs.").
**Why in:** The payoff loop. A log you don't read is worse than no log. Identity line comes from Clear — durable motivation comes from "who you're becoming," not "what you achieved."

### 8. Overreach detection in morning pushback
**Behavior:** The vague-reply pushback also flags unrealistic scope ("finish the entire MVP today" → "that's a week of work. What's the first 90 minutes?").
**Why in:** Flow theory — challenge/skill mismatch kills the loop as badly as vagueness. Repeated overreach trains you to distrust your own plans. Cost: one extra rule in the pushback prompt.

### 9. System-alive daily heartbeat (internal, not user-facing)
**Behavior:** Once a day, scheduler logs to Sheets: "system healthy, sent N messages." If you don't see a new row for 36 hours, something's broken.
**Why in:** Silent Twilio outages or scheduler death are the #1 killer of personal automation. Two hours of work now saves a week of silent failure.

### 10. Missed-reply handling
**Behavior:** If no reply within 3 hours, log "no response" and move on. Never re-ping the same prompt.
**Why in:** Graceful degradation. A nagging system gets muted, then ignored, then uninstalled.

---

## What's OUT of the MVP (and when it comes back)

### Hourly heartbeats (full heartbeat mode) — *defer to v2*
**Why out:** Full heartbeat cadence is where notification fatigue lives. Test the bookend + on-demand version first. The mode word is stubbed now so v2 just wires up the logic.
**When back:** After 14 days, if you consistently texted `stuck` or wanted mid-day check-ins.

### Full blocks mode with auto-generated check-ins — *defer to v2*
**Why out:** Same reasoning. Committing to "I'll do X from 10-12, Y from 1-3" and getting auto-checked at the boundaries is the natural v2 feature once we know which boundaries matter.
**When back:** After 14 days, if on-demand use shows a pattern of block-shaped days.

### Voice (Twilio Voice + Whisper) — *defer to v3*
**Why out:** Orthogonal. Adds a day of build and a new failure surface (transcription, call routing). No new information over SMS.
**When back:** If you find yourself driving/cooking when pings fire.

### Home Assistant integration — *defer to v3*
**Why out:** New channel, not a new loop. Until the core loop is sticky, more channels is premature.

### Weekly planning intake (Sunday "goals for the week?") — *defer to v2*
**Why out:** You can type weekly goals into the Sheet manually for now. Building a dedicated flow is half a day for something you use once a week.
**When back:** Once daily is sticky. Trivial to add.

### Smart cross-day context ("yesterday you said X, how did that finish?") — *defer to v2*
**Why out:** Tempting but easy to get wrong in ways that erode trust. Requires reasoning across rows, handling ambiguity.
**When back:** After 2 weeks of data.

### Adaptive cadence rules (auto-tighten on drift, auto-loosen on flow) — *defer to v2*
**Why out:** Requires 2+ weeks of data to calibrate. Premature auto-tightening feels like the system is judging you.
**When back:** Once baseline drift velocity is visible.

### Web dashboard — *probably never*
**Why out:** The Sheet is the dashboard. Recreating it is a week of work for zero marginal value.

### Multi-user / auth / billing — *not applicable*
**Why out:** MVP is N=1. Commercialization comes after the loop is proven.

### Pacts, streaks, gamification — *out*
**Why out:** Every one of these adds friction and teaches you to game the system. The product is a mirror, not a scoreboard. Eyal's pact mechanism is a last-resort tool, not a v1 feature.

### LLM judging whether you "did" your intent — *out, maybe forever*
**Why out:** Self-report is the point. The act of evaluation *is* the behavior change. LLM scoring would either be wrong (annoying) or right (you already knew).

---

## Why these particular cuts

Four principles shaped the in/out list:

**1. Test the behavior, not the features.** The hypothesis is now sharper: "SMS agent with if-then planning, warm acknowledgment, internal-trigger logging, and pattern-surfacing Friday summaries changes how I spend time." Everything in the MVP directly tests that hypothesis. Everything deferred is a variation that only matters if the base hypothesis holds.

**2. Cheap to extend later.** With AI coding agents, adding hourly heartbeats, blocks mode, voice, weekly planning — hours, not weeks. There's no cost to deferring. The cost is only to *premature* building — you waste the 14-day signal window on features that turn out not to matter.

**3. Graceful degradation beats rich features.** A simple system that always works beats a rich system that fails silently. Missed-reply handling, system-alive heartbeat, mode defaulting — all "in" because they're what keeps the app in your life at day 30, not day 3.

**4. Research-backed over intuition-backed.** If-then pushback, warm acknowledgment, and internal-trigger follow-up are all *in* because they have specific evidence behind them (Gollwitzer meta-analysis, Fogg/Clear, Eyal). Intuition-backed features (streaks, gamification, LLM scoring) are all *out*. When we pay the feature cost, we want to pay it on something the literature says works.

---

## Build order (one weekend)

**Saturday morning (2-3 hours)**
- Twilio account + phone number
- Google Sheets API credentials
- Scheduled job runner (cron on a cheap VPS, Cloudflare Workers Cron, or Render background worker)
- Send one hardcoded SMS end-to-end. Prove the pipe works.

**Saturday afternoon (3-4 hours)**
- Morning + evening prompts wired to scheduler
- Inbound webhook with **LLM-routed classification** (command / progress / question / emotional)
- Warm-reply generation for every inbound message
- Sheets schema with mode and parsed-JSON columns
- Timezone handling (hard-code home TZ; defer travel)

**Sunday morning (3-4 hours)**
- If-then pushback prompt (morning)
- Overreach detection (morning)
- Internal-trigger follow-up (evening, conditional on drift signal)
- Command parsing for `start`, `stuck`, `done`, `quiet`, `cancel`
- Mode-word parsing at start of morning reply
- **User-declared timebox → scheduled check-back** (explicit command + implicit parse from morning/free-form messages, with grace window and cancellation)

**Sunday afternoon (1-2 hours)**
- Friday summary job (LLM reads week's rows; output: what-said / what-happened / pattern / identity line)
- System-alive heartbeat row
- Missed-reply handling (3-hour timeout, log and move on)
- Ship. Start Monday morning.

Total: ~8-13 hours. Fits in a weekend with agent assistance.

---

## What "success" looks like at day 14

Six criteria now, up from four. Two new ones tied to the research-backed features:

1. You replied to ≥10 of 14 mornings and ≥10 of 14 evenings without feeling resentful.
2. You caught at least one day where your 9am intent was honestly wrong by 9pm, and the surprise was useful.
3. At least one Friday summary told you something you didn't already know.
4. The pushback fired at least twice and you either sharpened your answer or consciously chose to leave it.
5. **If-then plans had a noticeably higher completion rate than vague plans.** Eyeball it from the Sheet. If not, the if-then addition isn't paying off.
6. **At least one internal-trigger pattern surfaced** (e.g., "streams consistently follow stuck-on-hard-task moments"). If not, the internal-trigger logging isn't working.

If ≥4 of 6 are true, extend to v2. If fewer, shelve or revise the hypothesis. Either is a valid outcome.

---

## What changed from v1 of this doc (and why)

| v1 MVP | v2 MVP (this doc) | Why |
|---|---|---|
| Vague-reply pushback | If-then-format pushback | Gollwitzer meta-analysis: if-then has strongest evidence base in behavior-change lit |
| Silent append to Sheets | Warm LLM acknowledgment on every inbound | Clear 4th law + Fogg celebration principle. Closure makes users text back |
| Command-only inbound handling | LLM-routed inbound (command / progress / question / emotional) | User needs to log anything, not just map to commands |
| Bookend-only cadence | Bookend + mode word stub + on-demand check-ins | Cadence flexibility is needed from day one; mode as concept unlocks v2 |
| No internal-trigger question | Evening asks for internal trigger when drift reported | Eyal: the feeling underneath drift is the real target |
| No overreach detection | Pushback catches overreach and vagueness | Flow challenge/skill balance — overreach erodes trust in plans |
| Weekly summary: data only | Weekly summary: data + pattern + identity line | Identity cues are more durable than outcome cues (Clear) |
| 4 success criteria | 6 success criteria | Two new ones validate the if-then and internal-trigger additions specifically |

The spirit of the MVP didn't change: still one weekend, still N=1, still "test the behavior not the features." What changed is that the behavior being tested is now sharper, and a handful of research-backed features earned their way in at low cost.
