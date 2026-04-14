# Behavior Science → Product Decisions

The thesis for Overwatcher is that a proactive text agent can be a crutch for executive function, willpower, and focus. That thesis is testable against 50+ years of behavior-change research. This doc pulls the relevant findings, checks where the current MVP aligns, and names the features that the research says we're missing.

The goal isn't to cite books for flavor. The goal is: given what's known about how humans actually change behavior, **what else should this app do that it currently doesn't?**

---

## 1. The frameworks that matter

### Fogg Behavior Model — B = MAP
Behavior happens when **Motivation × Ability × Prompt** converge at the same moment. Fogg's central insight: raising ability (making the behavior easier) is almost always more effective than raising motivation. Motivation fluctuates wildly; ability doesn't.

**Where the MVP lines up:** We own the Prompt (SMS) and Ability is high (reply by text, no app). Motivation is the variable we don't control.

**What this implies we're missing:** A graceful degradation path for low-motivation days. Don't design only for the enthusiastic user, design for the exhausted one.

### Atomic Habits — Four Laws
Make it **Obvious, Attractive, Easy, Satisfying.** The fourth one is where most tools fail: there's no immediate satisfying reward for logging, so logging dies.

**Where the MVP lines up:** Obvious (SMS is unmissable), Easy (text reply). **Gaps:** Attractive (tone is undefined) and Satisfying (we don't close the loop after the user replies).

### Implementation Intentions — Gollwitzer's if-then planning
This is the single most evidence-backed finding in the behavior-change literature. A meta-analysis of 94 studies, 8,000+ participants, found **medium-to-large effect sizes** for goal attainment when people form plans in the structure "if [situation], then I will [action]" vs. abstract goals.

The mechanism: the "if" clause makes the situation highly accessible in memory, so when it occurs in the world, the action fires automatically. It bypasses willpower.

**Where the MVP lines up:** Not at all. The vague-reply pushback asks for specifics but doesn't force if-then structure.

**This is the single biggest missing feature.** See section 3.

### Deep Work — Newport
Deep work ability has a ceiling of roughly **4 hours per day**. Beyond that, focused attention degrades. Newport's "rhythmic" strategy (fixed daily windows for deep work) fits our daily-bookend cadence precisely.

**What this implies:** The app should treat 4 hours of substantive work as a strong day, not a weak one. Scoring yourself against 8 hours of output is setting up daily failure.

### Flow — Csikszentmihalyi
Three conditions for flow: **clear goals, immediate feedback, challenge/skill balance**. Too easy → boredom. Too hard → anxiety.

**Where the MVP lines up:** We help with clear goals (morning intent) and feedback (evening reality). **Gap:** we don't catch challenge/skill mismatch. Overreach ("I'll build the whole MVP today") is as much a failure mode as vagueness.

### Indistractable — Eyal
Three useful ideas:

1. **Traction vs. distraction.** Traction = action toward your goals. Distraction = away. Same activity (Twitter) can be either depending on intent. You can't tell without knowing what the person meant to do.
2. **Timeboxing is the most studied time-management technique and has the strongest evidence.**
3. **Internal triggers drive most distraction.** You don't open the stream because the stream is there. You open it because you felt bored / anxious / stuck, and it relieved the feeling. The app that doesn't ask "what were you feeling right before you got pulled away?" misses the actual root cause.

### Willpower / Ego depletion — Baumeister
The original ego-depletion research has replication problems (recent meta-analyses are mixed). But the practical takeaways survive:
- Decision-making depletes. Minimize decisions during the check-in itself.
- Time of day matters — morning is high-capacity for most people.
- Belief about willpower is itself mitigating: people who think willpower is unlimited behave as if it is.

### ADHD and Externalized Executive Function
This is the clinical frame for what we're building. People with ADHD (and to a degree, anyone under stress) benefit from **externalizing** executive function — offloading planning, monitoring, and self-regulation to external tools and people. Research on executive function coaching for ADHD shows consistent improvements in time management, self-regulation, and goal attainment when an external accountability structure exists.

**This legitimizes the product.** It isn't a productivity gimmick; it's a scalable, low-cost version of executive-function coaching. That's a real clinical category with real evidence.

---

## 2. Where the current MVP is well-aligned

- **Prompt timing is explicit and proactive** → Fogg's Prompt axis.
- **SMS is a low-ability-cost channel** → Fogg's Ability axis.
- **Morning intent + evening reality** → rhythmic deep-work structure (Newport), daily coaching cadence (ADHD research).
- **Google Sheets as visible log** → externalization of memory and monitoring.
- **Graceful missed-reply handling** → doesn't punish low-motivation days (Fogg).
- **One-shot pushback, not nagging** → respects decision fatigue.

The MVP isn't wrong. It's just incomplete in specific, fixable ways.

---

## 3. What's missing — features the research says we should add

### Must add to the MVP (before shipping, not after)

**A. Force if-then structure in the morning reply.**
Don't just push back on vagueness. Push back on format. When the user says "work on app from 10 to 12," the follow-up should be:
> "Turn it into an if-then. Something like: 'If it's 10am, then I open the design doc and spend 30 min on section 2.' What's yours?"

**Why:** The Gollwitzer effect only kicks in when the plan is formatted as if-then. Generic specifics ("I'll do X for 2 hours") don't get the same automaticity boost. This is the one change with the strongest evidence base in the entire behavior-change literature. Cost to add: one sentence in the prompt. Expected impact: real.

**B. Close the loop with a satisfying acknowledgment.**
After the user replies, send one short confirmation: "Logged. Good plan. Go." Not flattery. Closure.

**Why:** Clear's 4th law (Make it Satisfying) and Fogg's emphasis on immediate celebration after the behavior. A silent append to Sheets is unsatisfying — it feels like shouting into a void. One confirmation line is the difference between "this thing responds" and "did that even go through?" Cost: trivial.

**C. Ask for the internal trigger when drift is reported.**
When the evening check-in reveals drift ("got pulled into a stream for 2 hours"), fire one follow-up:
> "What were you feeling right before that happened? Bored? Stuck? Avoiding something?"

**Why:** Eyal's core finding. Distraction is a symptom; the internal trigger is the cause. Logging the pattern ("stuck on hard task → stream") over 2-4 weeks reveals the actual intervention target, which is never "more willpower." Cost: one conditional prompt.

**D. Detect overreach, not just vagueness.**
Pushback should catch both directions. "Work on stuff for an hour" → too vague. "Finish the entire MVP today" → too ambitious. Both produce failed intent-reality pairs and erode trust in the system.

**Why:** Flow requires challenge/skill balance. Repeated overreach trains you to distrust your own plans. Cost: extend the existing LLM pushback prompt to check for scope plausibility given the time available.

### Add in v2 (after 14 days of data)

**E. Anchor the morning prompt to an existing routine, not just the clock.**
Ideal: the prompt fires after coffee, not at 9am. For MVP, 9am is fine — but ask the user during setup "when do you usually sit down to work?" and use that time instead of assuming 9am.

**Why:** Fogg's Tiny Habits principle: anchor the new behavior to an existing routine. The anchor is the most reliable prompt.

**F. Identity reflection in the Friday summary.**
The summary shouldn't just be "here's what you did." It should close with a one-sentence identity cue: "This was a week where you showed up as someone who ships." Clear's point: habits stick when they're tied to identity, not outcomes.

**Why:** "I am someone who does X" is a more durable motivator than "I want to achieve X." Cost: prompt change in the weekly LLM call.

**G. Scheduled distraction slot.**
Evening prompt adds: "Anything you wanted to do today that wasn't work? (streams, scrolling, whatever) Did you give yourself time for it?"

**Why:** Eyal: you can't suppress internal triggers; you can only schedule around them. Giving distraction an explicit slot reduces its power during work blocks. Cost: one extra prompt line, optional reply.

**H. Front-load hard tasks, surface the pattern.**
After 2 weeks of data, the Friday summary should start noticing: "You tend to succeed at items scheduled before 11am and fail at items scheduled after 3pm." This is just reading the Sheet with an LLM.

**Why:** Willpower and attention degrade across the day (Newport's 4-hour cap, circadian research). Surfacing the user's own pattern is more convincing than generic advice.

### Consider later (v3 or never)

**I. Pacts and commitment devices.**
Eyal's last line of defense: price pacts ("charge me $10 if I fail"), effort pacts (block sites), identity pacts. These work but are aggressive. Only add if the lighter interventions plateau.

**J. Streak counter.**
Tempting, dangerous. Streaks are satisfying (4th law) but train the user to game the system and punish normal life events. Don't add unless there's evidence from self-use that absence of streak hurts.

**K. LLM-scored outcomes.**
Letting the LLM judge whether you "succeeded" is worse than letting the user self-report. Self-report is the point — the act of evaluation *is* the behavior change.

---

## 4. Features to explicitly resist

Research also tells us what *not* to build:

- **Motivation-dependent features.** Anything that only works if the user is in a good mood will fail on the days the app is most needed. Fogg is clear: optimize for ability, not motivation.
- **Guilt or shame mechanics.** Beeminder-style "you failed, pay up" is a small niche. For most users it triggers avoidance (mute, uninstall). Eyal's internal-trigger work shows shame produces more distraction, not less.
- **Gamification layers.** Points, badges, levels. These externalize motivation (bad per Deci's self-determination theory) and erode intrinsic motivation over time. The app is already the external structure; don't add a second one on top.
- **Social features / leaderboards.** Social accountability works with real humans, not strangers. Don't build this.
- **AI that argues with you.** One follow-up, then accept. An LLM that debates your plans becomes a cost, not a crutch.

---

## 5. Updated hypothesis

With the research layered in, the hypothesis sharpens from:

> "Proactive SMS + pushback changes how I spend time."

to:

> **"An SMS agent that (a) forces my morning plans into if-then format, (b) closes the loop with immediate acknowledgment, (c) surfaces my internal triggers when I drift, and (d) reflects my patterns back on Fridays — will produce measurable changes in what I do during the day, because each of those mechanisms has independent evidence behind it."**

That's a stronger hypothesis. Each clause is independently falsifiable. If the whole thing works, we don't know which part mattered most. That's fine for v1; we can ablate later.

---

## 6. Revised day-14 success criteria

Original MVP doc had four criteria. Adding two from the research:

5. At least one Friday summary identified an **internal-trigger pattern** (e.g., "streams consistently follow stuck-on-hard-task moments"). If we never surface a pattern, the internal-trigger logging isn't paying off.
6. If-then plans in the morning reply should have a **noticeably higher completion rate** than vague plans or plans without if-then structure. You can eyeball this from the Sheet after 14 days. If if-then doesn't help, something's off with the prompting.

---

## Sources

- [Roy Baumeister: Willpower Is Finite (Ego Depletion Theory) — Shortform](https://www.shortform.com/blog/baumeister-willpower/)
- [Ego depletion — Wikipedia](https://en.wikipedia.org/wiki/Ego_depletion)
- [Self-control and limited willpower: Current status of ego depletion theory and research — ScienceDirect (2024)](https://www.sciencedirect.com/science/article/pii/S2352250X24000952)
- [Atomic Habits Summary — James Clear](https://jamesclear.com/atomic-habits-summary)
- [Atomic Habits: 4 Laws of Habit Formation — Shortform](https://www.shortform.com/blog/atomic-habits-4-laws/)
- [Fogg Behavior Model — BJ Fogg](https://www.behaviormodel.org)
- [The Fogg Behavior Model: B = MAP — The Behavioral Scientist](https://www.thebehavioralscientist.com/articles/fogg-behavior-model)
- [Prompts in the Fogg Behavior Model](https://www.behaviormodel.org/prompts)
- [Gollwitzer — Implementation Intentions: Strong Effects of Simple Plans (1999)](https://www.prospectivepsych.org/sites/default/files/pictures/Gollwitzer_Implementation-intentions-1999.pdf)
- [If-then planning — Taylor & Francis](https://www.tandfonline.com/doi/full/10.1080/10463283.2020.1808936)
- [Implementation intention — Wikipedia](https://en.wikipedia.org/wiki/Implementation_intention)
- [Deep Work: The Complete Guide — Todoist](https://www.todoist.com/inspiration/deep-work)
- [Deep Work — Cal Newport](https://calnewport.com/deep-work-rules-for-focused-success-in-a-distracted-world/)
- [Flow (psychology) — Wikipedia](https://en.wikipedia.org/wiki/Flow_(psychology))
- [Investigating the "Flow" Experience — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7033418/)
- [Indistractable — Nir Eyal](https://www.nirandfar.com/indistractable/)
- [Strategies for becoming less distracted — Lenny's Newsletter / Nir Eyal](https://www.lennysnewsletter.com/p/strategies-for-becoming-less-distractible)
- [Executive Function Coaching — PubMed](https://pubmed.ncbi.nlm.nih.gov/25917958/)
- [Strategies for Externalizing Executive Functioning for Individuals with ADHD](https://www.couragetobetherapy.com/blogarticles/strategies-for-externalizing-executive-functioning-for-individuals-with-adhd)
- [Executive Function Coaching — CHADD](https://chadd.org/about-adhd/coaching/)
