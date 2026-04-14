# Overwatcher — Evaluation

A proactive, text-first accountability agent. It pings you during operating hours, forces you to name what you're about to do, pushes back when your plan is vague, heartbeats mid-task, and logs how it actually went. Channels: Twilio SMS first, voice / Home Assistant later.

This doc evaluates it three ways: first-principles, through the book-wisdom lens (product, behavior-change, systems), and through Garry Tan's YC Office Hours "six forcing questions." Then: personal-use verdict, then commercial-use verdict.

---

## 1. What the product actually is

Strip away the channels and it's two loops:

**Intent loop.** At the start of a time block (hourly, or user-defined), the agent asks "what are you about to do?" If the answer is vague ("work on app"), it pushes back: too broad for 60 minutes, decompose. Accepts a concrete commitment ("30 min design, then prompt AI for the rest of the hour"). Sets an implicit timebox.

**Reality loop.** At the end of the block (or on a heartbeat), it asks "how did it go?" Captures drift ("got pulled into a stream"), completions, feelings, decisions. Stores the pair (intent → reality) plus any free-form log.

Everything else — weekly planning, daily planning, cooking-stew detours, voice, Home Assistant — is a channel or a scheduler variation. The core is *structured intent + structured reflection, delivered where you already live (SMS)*.

That framing matters because it tells you what the MVP is and what's scope creep.

---

## 2. First-principles take

The problem you're describing is real and extremely common: low awareness of how time is actually spent, vague goals that silently expand to fill the hour, and no friction between intention and drift. "Logging things I do gives lots of awareness" is exactly right, and it's the mechanism behind every useful time-tracking / journaling / coaching system.

What's genuinely interesting here:

- **Proactive beats reactive.** Apps like Toggl, RescueTime, Notion journals all require *you* to open them. The failure mode is "I forgot to log." An SMS that arrives uninvited inverts that. This is the single biggest design advantage over the hundred existing tools.
- **Pushback is the feature.** "Too vague, break it down" is the part no existing app does. Todo lists accept whatever you type. A coach doesn't. This is where an LLM earns its keep.
- **Channel choice is load-bearing.** SMS has ~100% open rate and zero app-switching cost. Most productivity apps die on activation energy; SMS has none.

What's risky:

- **Notification fatigue.** Hourly SMS can go from helpful to nagging in a week. The product lives or dies on how good the cadence and tone are. This is not a "write a cron and ship it" problem.
- **You're the user and the maintainer.** If you miss a day, does it auto-pause? If you don't reply, does it escalate or shut up? These micro-decisions are the product.
- **Logging without review is noise.** A log you never read is worse than no log. The app must produce a weekly/daily readout, or the logs rot.

---

## 3. Storage — pick one, quickly

You listed three. The answer is clear:

**Google Sheets. Ship it.**

Why: zero-friction viewing from any device, trivial for an LLM to append via the Sheets API, trivial for *you* to eyeball, pivot, and annotate. Free. The "easy for LLM to analyze" argument applies equally to all three. The "easy to access" argument only applies to Sheets.

The one caveat: Sheets is not great once rows exceed ~50k or once you want structured queries across intent/reality pairs. By the time you hit that, you'll have real usage data and can migrate to Postgres or DuckDB with a day of work. That's a good problem to have. Don't pre-optimize.

JSON file is fine for a v0 spike (like, one afternoon), but skip straight to Sheets for anything you'll actually use for more than a week.

---

## 4. Through the book-wisdom lens

### Product (Cagan, *Inspired*; Torres, *Continuous Discovery Habits*)

The core value hypothesis — "proactive structured check-ins produce more focused work and better self-knowledge than passive tools" — is testable in under a week with nothing but Twilio and a Google Sheet. That's the signal: if the MVP is this cheap, build it and run it on yourself for two weeks before writing another design doc. You are the customer. Continuous discovery with N=1 is still continuous discovery.

The honest Cagan question: is this *valuable, usable, feasible, viable*? For personal use: yes, yes, yes, yes. For commercial: yes, maybe, yes, unclear (see section 6).

### Behavior change (Fogg, *Tiny Habits*; Clear, *Atomic Habits*)

Fogg's model: B = MAT (behavior = motivation × ability × trigger). You're adding a trigger (the SMS) and reducing ability-cost (reply via text, no app). Motivation is already there (you wouldn't be building this). That's the whole loop. This is well-aimed.

The trap Fogg would flag: if the trigger fires when motivation is low, the behavior doesn't happen, *and* the trigger loses credibility. So the cadence must degrade gracefully. Missed a reply? Don't double-text. Don't guilt. Just log "no response" and move on.

### Systems (Nygard, *Release It!*; SRE)

The failure modes to actually worry about:

- Twilio outage or quota exhaustion. The product just silently stops working. Add a daily heartbeat from the scheduler *to yourself* ("system is alive, sent N messages today") so you notice.
- Timezone bugs during travel. Timebox the fix: hard-code your home TZ for v1, revisit when you travel.
- LLM latency or failure. Reply handling must degrade to "logged, will process later" rather than hang.

For personal use, the SLO is "works most days." Don't over-engineer.

### Systematic feature design (Ousterhout, *Philosophy of Software Design*)

Deep module: the `Checkin` abstraction. It should have one interface (start, collect reality, log) and many implementations under it (SMS, voice, Home Assistant). If you design that boundary well now, adding channels later is a weekend each. If you don't, you'll rewrite.

---

## 5. Through Garry Tan's Office Hours — the six forcing questions

This section runs the app through YC's startup-mode diagnostic. I answer on your behalf from what you wrote, then flag where the answers would need to get sharper if you wanted to commercialize.

### Q1 — Demand Reality

*What's the strongest evidence anyone wants this beyond you?*

Honest answer: none yet. You described your own pain. That's legitimate for a side project (it's the #1 source of great side projects) but it's not evidence of market demand. Waitlists, "cool idea" comments, and "I'd totally use that" from friends would not count.

**What would count:** someone else running your prototype for two weeks and getting upset when you turn it off. You can generate that evidence in a month with almost zero cost.

### Q2 — Status Quo

*What are people doing right now to solve this, even badly?*

Plenty. Todo apps (Todoist, Things), time trackers (Toggl, RescueTime), journaling apps (Day One), calendar blocking, accountability partners, Pomodoro timers, Beeminder, Focusmate, Stoic-style daily review apps. The status quo isn't nothing — it's a messy stack of six tools nobody uses consistently. Your real competitor is *the user's own half-abandoned Notion template*.

That's actually a good competitive position: fragmented market, no dominant winner, most users unsatisfied. But it also means "nobody solved it yet" isn't true. They tried and mostly failed. You need a theory of why.

### Q3 — Desperate Specificity

*Name the human who needs this most.*

Candidates: ADHD knowledge workers, solo founders, PhD students, freelancers with no external structure, people returning from burnout, vibe-coding hobbyists. Each is a different product. Pick one to build the v2 for — the MVP is just "for you."

### Q4 — Narrowest Wedge

*Smallest thing someone pays for this week.*

Strip it to: morning SMS asks what you'll do today, evening SMS asks how it went, Friday SMS gives you the week's log. That's the wedge. No hourly heartbeats, no vague-goal pushback, no voice. Ship that in a weekend. Everything else is earned by proving the wedge works.

This is the single most useful thing the office-hours frame produces for you: **don't build the full loop first.** Build the daily bookends, live with them for a week, then add hourly check-ins only if the daily rhythm isn't enough.

### Q5 — Observation & Surprise

*Have you watched someone else use this?*

No, and you can't yet — it doesn't exist. But plan for it. After the MVP runs on you for two weeks, give it to one friend cold, no onboarding, and watch what they do. The surprise is the signal.

### Q6 — Future-Fit

*Does this get more essential in 3 years?*

Moderately yes. LLMs keep getting better at conversation, so the pushback loop gets sharper. Ambient / voice interfaces (AirPods, home speakers) become more natural, and your app is already channel-agnostic. The risk is that Apple or Google ships something adjacent at the OS level ("Siri, what should I work on?") and eats the category. That's a real risk but 3+ years out.

### Office Hours verdict

As a side project: green light, build the wedge in Q4 this weekend.
As a startup: not yet. You'd need to run the wedge on yourself, then on 5-10 others, and come back with Q1 evidence before this is a company-shaped thing.

---

## 6. Personal-use verdict

**Yes, build it. This is a high-ROI vibe-code project for you specifically.**

Reasons:

1. The problem is real and you named it precisely (vague goals eat time, logs create awareness, streams steal hours). That's the best possible starting point.
2. The MVP is small. Twilio webhook + one LLM call + Google Sheets append + a cron. One evening for v0, one weekend for something genuinely useful.
3. You don't need anyone else to validate this. If it helps *you* spend fewer hours on streams and more hours on what matters, it paid for itself in week one.
4. You get to dogfood an agent loop that's genuinely useful, which sharpens your instincts for the next, bigger agent project.

**What to build first (this weekend):**

- 9am SMS: "What are you working on today? Top 1-3 items." → log to Sheet.
- 9pm SMS: "How did today go? What happened with [items]?" → log to Sheet.
- Friday 5pm SMS: summary of the week (LLM-generated from the Sheet).
- One LLM prompt that handles vague replies by asking one follow-up. Just one. Don't build the full hourly loop yet.

**What to defer:**

- Hourly heartbeats (add after the daily version proves sticky).
- Voice and Home Assistant (cool but orthogonal).
- Weekly planning intake (manual for now, just put it in the Sheet yourself).
- A web dashboard. The Sheet *is* the dashboard.

---

## 7. Commercial verdict

**Not obvious. Interesting enough to revisit after 2-4 weeks of personal use.**

Where there's a real business:

- **Accountability-coach-as-a-service for specific audiences.** ADHD coaching is a real market (see Shimmer, Inflow). A text-first, LLM-powered accountability agent priced at $15-30/mo for ADHD knowledge workers is plausible. You'd need a credentialed coaching partner or clear "not medical" positioning.
- **B2B for bootcamps or coaching practices.** Executive coaches and career coaches already charge $200-500/session. An agent that keeps clients accountable *between* sessions, branded under the coach, is a real white-label opportunity. Higher willingness to pay, slower sales cycle.
- **Tied to a specific vertical.** "Accountability for solo founders" or "accountability for freelancers between client work" is sharper than "accountability for everyone."

Where it's not a business:

- **General-purpose productivity tool.** Competing against Todoist/Notion/Sunsama as "the SMS one" is a slow death. Productivity is where features go to die in feature bloat.
- **Selling to yourself and 100 HN readers.** Fine for a $5/mo side project, not a company.

The honest read: the product is a strong personal tool and a *plausible* wedge into ADHD / solo-founder coaching. Before spending real time on the commercial path, finish the personal version, use it for a month, then give it to 5 people in one specific target audience and see if they'd pay. If two of them get angry when you turn it off, you have something.

---

## 8. The AI-coding-agent multiplier

Everything above was written assuming a normal cost of building. That assumption is wrong now. With Claude Code / Cursor / similar agents, the actual build costs collapse:

| Piece | Old estimate | With coding agents |
|---|---|---|
| Twilio webhook + inbound handler | 1 day | 30 min |
| Google Sheets append + schema | 0.5 day | 15 min |
| Scheduler (cron / Temporal / simple queue) | 1 day | 30 min |
| LLM pushback prompt + reply routing | 1 day | 1 hour |
| Friday summary generator | 0.5 day | 20 min |
| Hourly heartbeat loop | 2 days | 2 hours |
| Voice channel (Twilio Voice + Whisper) | 1 week | 1 day |
| Home Assistant integration | 3 days | 3 hours |
| Basic web dashboard (if you want one) | 3 days | 2 hours |

The MVP goes from "one weekend" to "one evening." The full vision goes from "a month" to "a weekend." This changes three things in the analysis:

**1. The wedge argument gets weaker, not stronger.** I told you to build the daily bookends first and defer the hourly loop. That advice was partly about dev cost. With agents, the incremental cost of adding the hourly loop is a couple hours. Still ship the bookends first to *test the behavior*, but the gating reason is now "will you tolerate hourly pings?", not "will you get bored building it?" Build → live with → extend, same flow, just compressed to days not weeks.

**2. The "ship crappy, learn from reality" principle gets much stronger.** When the full feature set is a weekend, there's zero reason to design on paper first. Build two variants, A/B them on yourself across two weeks, keep the one that stuck. The cost of being wrong is a few hours.

**3. Completeness is cheap, so boil the lake on the boring stuff.** Retry logic, timezone handling, auth, idempotent webhook handling, dead-letter queue for missed messages, a daily system-heartbeat to yourself — all of it takes an extra 1-2 hours with an agent. Do it upfront. The failure mode of "silent Twilio outage, didn't notice for 5 days" is the kind of thing that kills personal tools. Fix it in v1, not v3.

**What this changes for the commercial path specifically:** the cost of testing "does this work for ADHD coaches' clients" is now *days* of engineering, not *months*. So the bar shifts from "is this worth building?" to "can you get in front of 10 real candidates and let them run it?" Distribution, not code, is the bottleneck. Which is the usual answer, but it's now the *only* answer.

One caveat. Agent speed makes it tempting to keep adding channels and features because you *can*. Don't. The product constraint is still how many pings a human will tolerate before they mute you. No amount of Claude Code makes that constraint go away.

---

## 9. Recommended next steps

1. Build the Q4 wedge this weekend: 9am / 9pm / Friday SMS, Google Sheet storage, one LLM pushback prompt.
2. Use it for 14 days. Keep a side journal of what worked, what annoyed you, what you wanted it to do.
3. After 14 days, decide: extend to hourly heartbeats, or stay on daily and polish? Don't decide upfront.
4. If you still care after 30 days, put it in front of 3-5 people outside your head. Pick a specific audience before you pick them.
5. Only then ask the commercial question again.

The single biggest failure mode here is over-building the v0. You have a clear loop, you are the customer, and the MVP is tiny. Ship it crappy, live with it, let reality tell you what to build next.
