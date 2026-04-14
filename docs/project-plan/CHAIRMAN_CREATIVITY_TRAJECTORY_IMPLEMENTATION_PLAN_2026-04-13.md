# Chairman Creativity + Trajectory Implementation Plan — 2026-04-13

## Strategic shift

Civic Ledger should stop treating **launch-readiness validation** as the project strategy.

Launch-readiness validation remains necessary, but from this point forward it should serve a sharper product strategy:

> **Build a trusted, evidence-backed accountability product for a specific first user and workflow.**

The implementation plan below assumes the recommended direction is:
- maintain current trust/operations discipline
- narrow the first wedge
- emphasize evidence portability and freshness honesty
- prefer higher-trust depth over broader but shakier coverage

---

# Priority stack

## P0 — Must happen first
1. Finish operational proof of life
2. Choose first user + launch wedge
3. Define trust boundary for scoring and coverage
4. Make freshness / coverage visible in product, not only docs

## P1 — Next after P0
5. Build shareable official evidence brief/export
6. Establish high-priority coverage tier and manual promise curation workflow
7. Add basic production observability and release evidence trail

## P2 — After P1
8. Add watchlists / alerts / repeated workflow hooks
9. Add institutional-user features and exports/API
10. Expand adjacent data sources and broader coverage only after trust density is strong

---

# Near-term sequence

## Today / next 7 days

### 1) Decide the launch wedge
**Action:** Sean chooses the first user and primary workflow.

**Recommended choices, in order:**
1. watchdog / advocacy researcher
2. journalist / newsroom researcher
3. highly engaged citizen researcher

**Decision needed:**
- Who is first?
- What job are they hiring Civic Ledger to do?

**Owner assumption:** Sean
**External dependency:** none
**Requires Sean specifically:** yes
**Can be done autonomously:** no

---

### 2) Reframe roadmap and status language around the wedge
**Action:** Update roadmap/status docs so the repo no longer implies that generic MVP validation is the whole story.

**Desired output:**
- explicit first user
- explicit launch wedge
- explicit non-goals
- explicit trust boundary

**Owner assumption:** gov-director / gov-docs
**External dependency:** Sean’s decision from step 1
**Requires Sean specifically:** only the decision
**Can be done autonomously:** yes, after direction is chosen

---

### 3) Run the real verification pass in a network-enabled environment
**Action:** Execute the verification matrix honestly and append dated results.

**Minimum commands/surfaces:**
- `python3 -m pytest -q` or equivalent test suite runs in a prepared environment
- baseline bootstrap
- read-model refresh
- GitHub Actions run health
- Render `/healthz` + live route smoke

**Success condition:**
- verification status becomes dated and observed, not inferred

**Owner assumption:** gov-director / gov-coding
**External dependency:** working runtime, CI visibility, deploy visibility
**Requires Sean specifically:** access to GitHub Actions, Render, secrets, or a network-enabled environment
**Can be done autonomously:** partially, once access exists

---

### 4) Define scoring and trust guardrails explicitly
**Action:** create one short policy that states:
- when a score may be shown
- when a score must be withheld or downgraded
- when promise inference is acceptable
- which profiles need human-reviewed promise inputs before the score is treated as strong

**Reason:** current heuristics are good enough for an internal prototype but not yet strong enough for broad public overconfidence.

**Owner assumption:** gov-director + gov-audit
**External dependency:** Sean alignment on trust posture
**Requires Sean specifically:** final policy choice if tradeoffs are politically or brand sensitive
**Can be done autonomously:** yes, draftable autonomously

---

### 5) Add product-visible freshness and coverage indicators
**Action:** elevate current readiness semantics into prominent product surfaces.

**Implementation target:**
- show `seeded` / `partial` / `enriched` prominently on official pages
- show last refresh time / freshness band
- show whether promises are curated vs inferred
- show whether score confidence is limited

**Owner assumption:** gov-coding / gov-docs
**External dependency:** none beyond current data model
**Requires Sean specifically:** no
**Can be done autonomously:** yes

---

## One month / next 30 days

### 6) Build the core shareable artifact
**Action:** create an official brief / exportable accountability packet.

**Minimum viable shape:**
- official summary
- funding summary
- promise coverage summary
- legislative activity summary
- score + explanation
- evidence and caveats
- freshness/readiness indicators

**Why this matters:** this turns the product from a browseable dashboard into a useful object people can cite, send, and reuse.

**Owner assumption:** gov-coding + gov-docs
**External dependency:** wedge definition from Sean
**Requires Sean specifically:** final call on format priorities (PDF-like brief, printable page, permalink share card, etc.)
**Can be done autonomously:** largely yes

---

### 7) Create a tiered coverage policy
**Action:** split coverage into explicit tiers.

**Recommended policy:**
- **Tier 1:** high-priority officials with manual promise curation and stronger evidence expectations
- **Tier 2:** broad federal directory with transparent inferred / partial coverage

**Reason:** this preserves breadth without pretending equal confidence everywhere.

**Owner assumption:** gov-director + gov-research + gov-audit
**External dependency:** chosen priority set
**Requires Sean specifically:** yes, for priority-selection philosophy
**Can be done autonomously:** draft yes; final selection no

---

### 8) Stand up basic observability
**Action:** implement:
- deploy health checks
- refresh run status view
- error tracking
- dated release evidence log

**Why this matters:** without observability, launch-readiness remains a guess.

**Owner assumption:** gov-coding
**External dependency:** service access, possibly third-party tools
**Requires Sean specifically:** platform/service account approval if third-party tools are used
**Can be done autonomously:** partly

---

### 9) Establish manual promise curation workflow
**Action:** define how new manual promises enter `data/manual_promises.json` or successor storage.

**Must include:**
- source quality rules
- required citation fields
- review standard
- change logging

**Owner assumption:** gov-research + gov-docs + gov-audit
**External dependency:** Sean’s decision on how much curation labor to support
**Requires Sean specifically:** yes, if labor/resourcing matters
**Can be done autonomously:** draft yes

---

## One year / long term

### 10) Turn Civic Ledger into accountability infrastructure
**Action:** evolve from a website into a durable trust platform.

**Capabilities to add over time:**
- exports and APIs
- watchlists and alerts
- comparative views
- topic scorecards
- institutional workflows
- eventually adjacent data integrations if they strengthen the trust story

**Owner assumption:** multi-agent GOV stack
**External dependency:** usage proof, operating budget, partnerships
**Requires Sean specifically:** funding level, scope discipline, partnership priorities
**Can be done autonomously:** some product execution yes; strategic expansion no

---

# Concrete prioritized action items

## Priority 1 — Sean decisions
1. Choose first user.
2. Choose first workflow.
3. Decide launch wedge breadth:
   - all federal officials with tiered trust signals
   - or narrower priority set with deeper curation
4. Decide trust posture on inferred promises:
   - permissive for all profiles
   - or restricted for public-facing strong claims
5. Decide whether the core shareable artifact is:
   - evidence page
   - printable brief
   - export packet
   - all three over time

## Priority 2 — Autonomous once decisions exist
1. Rewrite roadmap/status to match the sharper wedge.
2. Add visible freshness/readiness indicators in product surfaces.
3. Draft score-confidence / trust-boundary policy.
4. Build official brief/export page.
5. Draft tiered coverage policy.
6. Draft manual promise curation SOP.
7. Add release-evidence and operations-observation logging.

## Priority 3 — Access-dependent execution
1. Run verification matrix in a working environment.
2. Inspect GitHub Actions run health.
3. Inspect Render health and logs.
4. Validate production database posture.
5. Install/use missing tooling in director runtime (`pytest`, `gh`, or equivalents).

---

# External dependencies

## Required soon
- GitHub Actions visibility and repo permissions
- Render service visibility and logs
- durable production database confirmation
- working network-enabled Python environment with test dependencies

## Likely service/tool choices
- Postgres host: Render/Neon/Supabase
- Error tracking: Sentry or equivalent
- Uptime/deploy health: Better Stack/UptimeRobot/Render-native checks
- Product analytics: Plausible/PostHog or equivalent

## Potential future external partners
- watchdog groups
- journalists / newsrooms
- journalism schools
- civic-tech communities
- policy research nonprofits

---

# What requires Sean specifically

1. Picking the first user and launch wedge
2. Approving trust posture for inference vs curated claims
3. Granting access to GitHub / Render / production visibility
4. Approving any service spend
5. Deciding how much manual promise curation investment the project will support
6. Deciding whether the first market is media, advocacy, civic education, or campaign-adjacent research
7. Choosing whether breadth or trust density wins when they conflict

---

# What can be done autonomously

1. Draft sharper roadmap and status docs
2. Draft trust-boundary/scoring policy
3. Build freshness and readiness UI
4. Build shareable official brief surface
5. Draft tiered coverage policy
6. Draft manual curation SOP
7. Add release-evidence logging and internal ops trails
8. Refactor copy so the product is less generic and more accountability-oriented

---

# Recommended owner assumptions

- **Sean** — strategy decisions, access, spend, launch wedge
- **gov-director** — synthesis, prioritization, product direction, final plan ownership
- **gov-coding** — implementation, observability, product surfaces, export flow
- **gov-research** — coverage priorities, promise sourcing, evidence quality
- **gov-audit** — trust guardrails, misleading-claim prevention, launch-risk review
- **gov-docs** — product language, operator docs, curation SOP, evidence-page clarity

---

# Risks if the plan is ignored

1. The project becomes a competent but strategically vague dashboard.
2. Scoring is read as more authoritative than the evidence really supports.
3. Launch validation completes but no one has a strong reason to return.
4. Breadth outruns trust density.
5. The repo looks mature while the product remains weakly positioned.

---

# Recommended next sequence in plain English

1. Sean picks the first user and wedge.
2. GOV rewrites the roadmap around that wedge.
3. GOV verifies the real operating path with dated evidence.
4. GOV makes freshness, evidence quality, and score confidence visible in product.
5. GOV builds the shareable official brief.
6. GOV introduces tiered coverage and stronger promise curation.
7. Only after that does GOV widen scope.

---

# Bottom line

This implementation plan assumes the project should become **more opinionated, more trustworthy, and more useful in real workflows** rather than merely more complete.

The right move now is not to balloon scope. It is to sharpen the wedge, prove the operating path, and make the evidence portable.
