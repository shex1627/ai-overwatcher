# Feedback Cycles — How Often Should Overwatcher Check In?

Daily is a floor, not the answer. The right cadence depends on task length, user state, environment, and recent drift. This doc works out a model for picking the cycle, and proposes an **adaptive, tiered** cadence rather than a single fixed one.

---

## 1. Why one fixed cadence is wrong

Control theory has a clean rule: **the feedback cycle should match the dynamics of the thing you're controlling.** If the system can drift meaningfully in 20 minutes, a daily check-in is useless — you've already crashed by the time you measure. If the system barely moves in a day, hourly is noise that trains you to ignore the signal.

Human attention behaves the same way. Drift velocity varies:

- Deep-focus coding on a clear problem → drift slow, hourly is overkill
- Vague "work on app" with no specific first step → drift fast, you're on YouTube in 12 minutes
- Low-sleep day, stressful morning, open office → drift very fast
- Flow state, clear plan, quiet room → drift near zero

A fixed daily cadence over-checks on the focused days and under-checks on the fragile ones. That's the failure mode of every productivity tool that ships one cadence for everybody.

---

## 2. Signals that should move the cadence

Five variables determine the right cycle at any given moment:

**A. Task duration.** The feedback loop should fire *during* the task, not after. A 30-minute task wants a check at 15. A 4-hour task wants a check at 60 and 120. Hourly check-ins on a 25-minute Pomodoro are interruptions, not support.

**B. User's current motivation/energy.** Fogg's model is the frame: when motivation is low, the prompt has to do more work. Low-motivation days need more check-ins *and* gentler tone. High-motivation days need fewer, because the user is already self-regulating.

**C. Environment.** Home alone with no social accountability → higher drift → tighter cycle. Coworking space or pair-programming → lower drift → looser cycle. The app should know (ask) which mode the user is in today.

**D. Stakes / task type.** Creative exploration tolerates wandering and benefits from looser cycles. Execution of a known plan benefits from tight cycles. "Write the tests you already specced" wants different cadence than "figure out how to structure this module."

**E. Recent drift pattern.** If the last 3 days showed big gaps between intent and reality, tighten. If the last 3 days hit intent cleanly, loosen. The system should *learn* the user's drift velocity, not assume it.

---

## 3. Proposed model — tiered, selectable, adaptive

Rather than one cycle, offer three tiers and let the user (or the system) pick per day or per block.

### Tier 1 — Daily bookends (the current MVP)
- 9am: intent
- 9pm: reality
- Friday: weekly summary

**When this is right:** self-regulation is already strong, work is familiar and execution-heavy, user is in flow naturally. This is the *minimum viable cadence* and where the app should default when there's no signal to tighten.

### Tier 2 — Morning plan + per-block check-ins
- 9am: intent for the day, broken into blocks
- End of each declared block: "how did the [10-12] block go? Next?"
- 9pm: reality
- Weekly summary

**When this is right:** typical "I want to get real work done" day. User declares 2-4 blocks in the morning, app checks at the end of each one. Block length is user-defined — could be 45 min, could be 3 hours. Matches the task, not the clock.

**Why blocks beat hours:** The check-in fires when a natural pause would happen anyway (end of a task). Hourly check-ins fire mid-thought, which is the worst possible time.

### Tier 3 — Heartbeat mode
- 9am: intent
- Check-in every 30-60 min during declared operating hours
- 9pm: reality
- Weekly summary

**When this is right:** fragile days. Low sleep, high distraction environment, avoidance on a specific hard task, returning from a break, or the user explicitly requests it ("I need a babysitter today"). Also: use this when starting a new habit or tracking a specific behavior change.

**The anti-pattern to avoid:** defaulting to heartbeat mode. It's the most interruptive tier and the most likely to get muted. Use it as a tool, not a baseline.

### How the tier gets chosen

Two paths:

1. **User picks in the morning.** Add one line to the morning SMS: "Mode: [bookend / blocks / heartbeat]?" Default to yesterday's mode. One tap/word to change.
2. **System suggests based on signals.** After 2-3 weeks of data, the Friday summary can recommend: "Your last 3 days showed big intent-vs-reality gaps — want to try blocks mode next week?"

Give the user the choice. Don't auto-switch without asking; auto-switching feels like the system is judging you.

---

## 4. Adaptive rules — when to tighten or loosen without asking

These are rules the system can apply silently, *within* a chosen tier, to respond to observed state.

**Tighten (without switching tiers):**
- User declared an intent but didn't name a specific first step, even after one pushback → add an extra check at the 20-min mark that block
- Evening report reveals drift > 50% of the block's time → next morning, suggest moving from bookend to blocks
- User explicitly reports stuck/avoiding in an internal-trigger log → offer a 30-min check-in for the rest of that block only ("want me to check back in 30?")

**Loosen:**
- 3 consecutive days hit intent cleanly → drop one check-in per day, see if the user notices
- User is clearly in flow (long block, evening report shows high completion) → reduce next day by default
- User explicitly says "I'm good today, don't check in till tonight" → respect it, skip the middle check-ins

**Never do:**
- Double-text on a missed reply (nag)
- Change the cadence on the user's behalf without telling them
- Tighten in response to one bad day (one bad day is noise, 3 bad days is a pattern)

---

## 5. On-demand check-ins — the missing primitive

One feature that solves a lot of cadence problems: **let the user pull, not just receive.**

Texting the agent at any time should do something useful:
- Text "start [task] [30min]" → logs intent, sets a check-back at 30 min
- Text "stuck" → agent asks the internal-trigger question, offers a 20-min check-back
- Text "done" → closes the current block, asks how it went
- Text "quiet" → suppresses check-ins for N hours

**Why this matters:** the user always knows their state better than the system. If they feel drift coming, they can call for backup. If they're in flow, they can push the system away. On-demand check-ins make the cadence fluid without complicating the default schedule.

This is also the highest-leverage feature to add after the bookend MVP proves sticky. Small code change, big flexibility gain.

---

## 5.1 Reply tone and free-form logging

The command list (`start`, `stuck`, `done`, `quiet`) is the *parser*, not the *interface*. The interface should accept anything the user sends and respond like a person, not a form.

### Two things the on-demand path has to get right

**1. Warm replies, not receipts.**
When the user proactively checks in, the reply should acknowledge what they said, not just confirm the command was parsed. Compare:

- Bad: `OK. Check-back set for 10:30.`
- Good: `Nice, you're in. I'll check back at 10:30. Go get it.`

- Bad: `Logged: stuck.`
- Good: `Got it. What were you feeling right before you got stuck? Bored, anxious, unsure where to start?`

- Bad: `Done. Recorded.`
- Good: `Nice. How'd it actually go vs. what you planned?`

The user reached out voluntarily. That's the most engaged moment in the whole loop. A cold machine reply burns that moment. A warm reply reinforces that checking in is worth doing, which is the behavior you want to compound.

**Tone rules for the LLM prompt:**
- Short. One to three sentences max. The user is working.
- Specific. Reference what they actually said, not a generic template.
- Encouraging without flattery. "Good plan" lands. "Amazing! You got this!" grates.
- Never scold. If they've drifted, ask what happened; don't guilt them.
- No emojis by default. Channel is SMS; keep it text-native and serious. Let them add emojis if they want.

This is a prompt engineering problem, not a feature problem. The LLM handles it — you just have to prompt it well, and the prompt has to be in the inbound handler, not just the scheduled prompts.

### Free-form progress logging

Users should be able to text *anything* during a task and have it logged usefully. Not just commands.

Examples that should work:
- `halfway through the design doc, section 2 is messier than i thought`
- `pressure cooker is on, back at laptop in 30`
- `decided to scrap the original approach, going with X instead`
- `this is harder than i expected`
- `taking a coffee break, back in 10`

All of these are *valuable signal*. Every one of them is a data point about how the work is actually unfolding. None of them map cleanly to `start/stuck/done/quiet`.

**How to handle it:** the inbound webhook runs everything through the LLM first. The LLM decides: is this a command? A progress note? A question? An emotional check-in? Route accordingly.

- **Command intent** → execute (set check-back, close block, etc.) + warm reply
- **Progress note** → log to sheet with type `progress`, warm one-liner back: `Noted. Keep going.` or `That's useful context — worth flagging in tonight's review.`
- **Question** (`should I switch tasks?`) → short coaching reply, not a decision. `You're mid-block. What would change if you waited until the next break?`
- **Emotional** (`this is overwhelming`) → acknowledge first, then offer one concrete next step. `Yeah, that's a real feeling. What's the smallest piece you could finish in 15 min?`

### Why this matters for the product

The loop isn't "user sends command, system responds." The loop is **the user talking to something that's listening.** The more the replies feel like listening, the more the user talks. The more the user talks, the better the log, the sharper the Friday summary, the more the whole system works.

Cheap implementation, large UX delta. Do this in v1.

### One concrete prompt addition

The inbound handler's LLM call should get a system prompt along the lines of:

> You are a calm, warm, direct accountability partner over SMS. The user is in the middle of work and just texted you. Your job: (1) classify what they sent (command, progress note, question, emotional check-in), (2) take any needed action, (3) reply in 1-3 sentences. Be specific to what they said. Never scold. Never generic. No emojis unless they used one first. If they're stuck or struggling, ask one concrete question or offer one concrete next step. If they're doing well, acknowledge and get out of their way.

That single prompt is probably 80% of the warmth. The remaining 20% is tuning it over the first two weeks of real use.

---

## 6. Research-backed cadence notes

- **Gollwitzer (implementation intentions):** the "if" in if-then plans is what triggers automatic action. Check-ins aren't what make the behavior happen — the plan does. This means the app can get away with *fewer* check-ins if the morning plan is strong. Quality of plan > quantity of check-ins.
- **Newport (Deep Work):** ~4 hours/day of deep work ceiling. More than 4 check-ins in a day of deep work is interrupting the thing you're trying to protect.
- **Eyal (Indistractable):** internal triggers cause distraction; check-ins address them. The right cadence is "frequent enough to surface the internal trigger before it wins." For most people, that's hourly on bad days, per-block on normal days.
- **Fogg:** prompts fire behavior; too many prompts stop firing behavior (habituation). There's a ceiling on useful prompt frequency that's lower than you'd think.
- **Control theory rule of thumb:** sample at 2-10x the dynamics you want to control. If you want to catch a drift that takes 30 min to fully manifest, sample every 5-15 min on the bad days and every 30-60 on the good ones.

---

## 7. Concrete recommendations

### For the MVP (this weekend's build)
Keep the daily bookends as the default. Add **two things**:

1. **On-demand check-ins** via inbound SMS (`start`, `stuck`, `done`, `quiet`). This is the cadence flexibility the user wants, with almost zero cost. You already have the inbound webhook — you're just adding a few intent parsers.
2. **A "mode" word in the morning prompt.** Let the user type "blocks" or "heartbeat" as the first word of their morning reply to shift that day's cadence. Default: bookend.

That's it. Don't build block-mode or heartbeat-mode fully yet — but design the system so mode is a first-class concept from day one, so v2 doesn't require a rewrite.

### For v2 (after 14 days of data)
- Full blocks mode with user-declared block boundaries
- Full heartbeat mode with configurable frequency
- Friday summary recommends a mode change if data warrants
- Adaptive tightening/loosening rules run silently within a chosen mode

### For v3+
- Calendar integration (app sees declared meetings and skips check-ins during them)
- Location / environment awareness (at home vs at coffee shop)
- Auto-detection of low-motivation days from reply latency and tone

---

## 8. The meta-principle

**The right feedback cycle isn't a number. It's a feedback cycle.**

The cadence itself should be something the system (and the user) adjusts based on what's working. A system that pings every 60 min forever is as dumb as one that pings every 24 hr forever. The product is a controller, and every controller needs to tune itself against its own output.

Design for *that* from day one — meaning: mode as a first-class concept, on-demand check-ins from the start, explicit data captured about drift velocity — and every cadence change later is a config tweak, not a rewrite.
