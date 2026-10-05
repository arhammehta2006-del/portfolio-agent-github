# Changes Backlog — mapped against the full spec

This maps every item in the "Required Changes and Improvements" + "UI/UX Redesign Requirements" document
against what's implemented in this pass, so the team can divide what's left. Legend: **Done** / **Partial**
(implemented in a lighter form) / **Deferred** (not started — reason given so it's a real backlog item,
not just "skipped").

Implementing all 94 items literally would mean rebuilding this into a different kind of product (full
financial-planning suite with persistent accounts, true native-app animation, itemised loan/holding
tracking). This pass prioritised: (a) what's gradable under your rubric (customer/use-case clarity,
model/data/prompt design, live demo, "beyond expectations"), (b) what's safely codeable and testable in
the time available, (c) low risk of breaking the already-working funding/Monte-Carlo engine.

## Functional / logic requirements (1–44)

| # | Requirement | Status | Notes |
|---|---|---|---|
| 1 | Explicit assumptions framework | **Partial** | Sidebar panel lists return/vol assumptions, goal-type inflation, and labels user-provided vs. model-estimated vs. default. Missing: salary/SIP-growth and life-expectancy as separate stated assumptions; tax rates (see #30). |
| 2 | Expand asset classes | **Deferred** | Still 5 classes (Liquid/Debt/Gold/Large-cap/Mid-cap). Small-cap, international equity, REITs/InvITs, index/ETF distinction not added. The doc says this is optional ("does not need every class") — lowest-risk place to start if someone wants a logic task. |
| 3 | Emergency-fund & healthcare planning | **Done** | Target months by employment type + dependents, shortfall carved out of investable amount first, shown as "Needs Attention"/"At Risk" in the scorecard. Health/life insurance are simple Y/N flags, not a healthcare-cost model. |
| 4 | Better return estimates (ranges, scenarios) | **Partial** | Conservative/Expected/Optimistic scenario cards exist (from the Monte Carlo p10/median/p90). Not yet shown as an explicit "9–12% p.a." range on the headline number. |
| 5 | Lumpsum / SIP / combination | **Partial** | Lumpsum and SIP (with step-up) both work end to end. A true "both at once" mode is not implemented — currently one or the other. |
| 6 | Investor knowledge / literacy questionnaire | **Deferred** | Not asked at all. Would need a new short quiz + a rule connecting the result to portfolio complexity/explanation depth. |
| 7 | Household situation | **Partial** | Dependents, sole-earner flag done. Marital status, "children vs. dependent parents" breakdown not separated. |
| 8 | Detailed income/financial info | **Partial** | Income, expenses, EMI, existing investments collected. Outstanding loans are an aggregate figure, not itemised; net worth not computed. |
| 9 | Employment type + conditional questions | **Done** | Employment type drives the income question's label and risk-capacity points; conditional reveals work (see test branches in `apptest_smoke2.py`). |
| 10 | Other income sources / retirement assets (EPF/PPF/NPS etc.) | **Deferred** | Not collected. Would feed into #19 (existing-portfolio awareness) as additional "already have" capital. |
| 11 | Goal priority & prioritisation | **Done** | Essential/Important/Aspirational column on each goal; funding now follows priority tier first, then nearest-date (`test_engine.py` TC5). |
| 12 | Goal achievability (gap, required SIP, probability) | **Done** | Each goal shows required funding, funded %, and Monte-Carlo probability; the Action Plan section turns shortfalls into a concrete rupee suggestion. |
| 13 | Detailed return info (contributions vs. growth) | **Partial** | Median/p10/p90 shown per goal. The explicit "Total contributions / Projected value / Wealth created" split for SIPs is not broken out as its own line yet — quick add if someone wants it (numbers already exist: contributions = SIP × months, wealth created = median − contributions). |
| 14 | Portfolio risk metrics (Sharpe, drawdown, etc.) | **Partial** | Sharpe ratio and a "stress decline" (an analytical 2-sigma estimate, not a historical max drawdown) are shown behind an "advanced" expander with plain-English tooltips. True historical max drawdown would need real historical return paths (`data/history/` is still placeholder). |
| 15 | Improve 3-portfolio comparison | **Done** | Conservative/Moderate/Aggressive cards with return, volatility, bad-year, Sharpe, and per-goal probability; existing "Compare alternatives" tab retained and fed by the same new numbers. |
| 16 | Explain WHY specifically (not generic) | **Done** | Advisor prompt now requires 3–6 bullets of the form "**your specific input** → the decision it drove," and feeds in risk appetite/capacity/required conflicts, debt, emergency-fund status, existing holdings. |
| 17 | "Why did the model recommend this?" transparency section | **Done** | The expander "Why these risk numbers?" plus the reasoning-chip bullets above cover this; no separate dedicated page was built. |
| 18 | Separate appetite / capacity / required risk | **Done** | All three computed; overall recommendation still follows min(appetite, capacity) deliberately (see README) — required risk is advisory, not a silent override, to avoid destabilising the already-tested recommendation logic. |
| 19 | Existing portfolio awareness | **Partial** | Two aggregate numbers (existing equity, existing other) tilt the *blended* new-money allocation away from over-concentration. Not itemised by asset class, and doesn't touch each goal's own protective allocation. |
| 20 | Debt / liability analysis | **Partial** | Aggregate EMI + a "high-interest" flag drive a debt-burden check and a repay-before-investing note. No itemised loan-by-loan amortisation. |
| 21 | Wealth management / rebalancing section | **Done** | "Portfolio maintenance" expander with rebalancing triggers, de-risking, and redistribution-on-life-event guidance (static educational copy, not a scheduler). |
| 22 | Annual review / life-stage updates | **Partial** | "Edit"/"Restart" preserve and let you change all inputs, recalculating everything live. No persistence across sessions (see UX #31 in the overall limitations) — nothing is saved once you close the tab. |
| 23 | Inflation varies by goal type | **Done** | Education/Healthcare/Travel/Housing/General each have their own rate (`config.GOAL_INFLATION`), selectable per goal. |
| 24 | Scenario analysis (conservative/expected/optimistic) | **Done** | Shown as three metrics per goal on the results page, sourced from the existing Monte Carlo. |
| 25 | "What if?" interactive analysis | **Done** | The "What-if" tab (pre-existing, kept) already does amount % and risk-profile swaps live; step-up SIP and goal-date what-ifs are not wired into that tab yet. |
| 26 | Step-up SIP | **Done** | Annual step-up % input, explicit month-by-month future-value solve for the required contribution, and Monte Carlo growing contributions (`test_engine.py` TC6). |
| 27 | Goal-specific asset allocation | **Done** | Already present before this pass (each goal gets its own bucket × profile allocation) — carried forward unchanged. |
| 28 | Insurance adequacy flag | **Done** | Health/life insurance Y/N (life insurance only asked when relevant — sole earner with dependents); flagged in the scorecard and Action Plan, no product recommendation. |
| 29 | Liquidity requirement question | **Partial** | Asked ("Very little/Some/Significant") and stored, but currently informational only — doesn't yet change the allocation math. Documented as a known limitation. |
| 30 | Tax awareness | **Deferred** | No gross-vs-post-tax distinction shown anywhere yet. Would need a stated (not computed) disclaimer at minimum, or a simple flat-rate toggle at best. |
| 31 | Final page order | **Done** | Results page now follows: Snapshot → Financial Health → Risk Profile → Goals → Portfolio → Why This Fits → Expected Results → Risk Analysis → Alternatives → Action Plan → Maintenance. |
| 32 | Back button / edit without losing data | **Done** | Already worked before this pass (session_state-backed); confirmed still true with the new fields via `apptest_smoke.py`. |
| 33 | "How this works" intro section | **Done** | New step 0 with the 5-step explainer and a "Build my plan" CTA. |
| 34 | Progress indicator | **Done** | Sidebar step list + a top progress bar, already present, now covering 7 steps instead of 5. |
| 35 | Conditional questions | **Done** | Sole-earner/insurance questions only appear if dependents > 0; EMI "high-interest" checkbox only if EMI > 0; SIP step-up slider only in SIP mode. Verified in `apptest_smoke2.py`. |
| 36 | Tooltips for jargon | **Partial** | Added on the new risk-metric and financial-profile fields (via Streamlit's `help=`). Not yet systematic across every older field. |
| 37 | Avoid false precision | **Partial** | Currency already formatted in L/Cr, not to the rupee; percentages shown to 1 decimal. Headline copy doesn't yet universally say "approximately" — a copy pass, not a logic change. |
| 38 | Consistency checks | **Done** | SIP-vs-disposable-income, high-EMI-burden, required-risk-vs-recommended, and aggressive-near-retirement checks all implemented as warnings/notes. |
| 39 | Overall financial health summary | **Done** | Scorecard (Emergency Fund / Debt Level / Savings Rate / Retirement Planning / Insurance Protection / Investment Diversification), each "Not assessed" if the user skipped that input. |
| 40 | Separate deterministic calc from GenAI | **Done** | Unchanged design principle from the original build, now extended to all new numbers too — advisor.py still never calculates. |
| 41 | Reproducibility | **Done** | Fixed seed (`config.SEED`) + `st.cache_data` keyed by a signature of the inputs; same inputs → same numbers every time (verified by rerunning `test_engine.py`). |
| 42 | Model decision / scoring layer for Claude | **Done** | `advisor.plan_context()` now passes the full scored breakdown (appetite/capacity/required, financial-health scorecard, debt/emergency-fund flags) as structured JSON. |
| 43 | Open questions for the dev team | **n/a** | This is a discussion checklist for your team, not a build item — worth a 15-minute team call before your demo script is finalised. |
| 44 | "What / Why / What if" product principle | **Done** | The reorganised results page answers all three in order (portfolio → reasoning chips → scenarios/alternatives). |

## UI/UX requirements (1–50, numbered independently in the doc's second half)

Grouped rather than itemised one-by-one, since most are visual-polish variations on a few themes:

| Theme | Status | Notes |
|---|---|---|
| Multi-step flow, one idea per screen, progress indicator, conditional questions | **Done** | 7-step wizard, progressive disclosure confirmed by automated tests. |
| Goal cards with progress, visual timeline, donut charts, 3-portfolio cards | **Done** | Pre-existing donut/compare charts kept; goal progress bars kept; reasoning turned into chip-style cards. |
| Restrained colour palette, consistent spacing, large metric typography | **Partial** | Light custom CSS added (neutral card backgrounds, accent-coloured reasoning chips). Not a full design-system pass — Streamlit's own widget chrome (buttons, inputs, tabs) is not deeply restyled. |
| Advanced metrics behind progressive disclosure, plain-English labels first | **Done** | Sharpe/stress-decline behind an expander with tooltips; emergency-fund/financial-health use plain labels with a 🟢🟡🔴 indicator rather than raw numbers first. |
| Friendly empty/error states, Indian number formatting | **Partial** | `fmt_inr` (L/Cr formatting) was already present. Validation messages are mostly friendly already; not every one was rewritten. |
| True animations (counting numbers, smooth transitions, swipe gestures, confetti/microinteractions) | **Deferred** | Not meaningfully achievable in Streamlit — it re-renders the page on every interaction rather than animating in place. Streamlit does support `st.progress`/spinners (already used) but not CSS transitions on live data. If the team wants genuine Apple-style motion, that needs a custom web front end (HTML/CSS/JS) instead of Streamlit — a bigger decision than a UI tweak, worth discussing with your instructor given the time left. |
| Landing/marketing-style hero screen, "Your Money Story" narrative sequence | **Partial** | The intro step states the product's purpose and a 5-step explainer; it's not a full animated narrative sequence. |
| Mobile-first responsiveness, swipeable cards | **Deferred** | Streamlit's layout is reasonably responsive by default but wasn't specifically tuned for mobile; swipe gestures aren't a Streamlit-native concept. |
| Dedicated "What-if" sliders playground with live recompute | **Done** | Pre-existing "What-if" tab kept and still works with all the new fields flowing through it. |

## If you want to divide the remaining work across the team

A natural 5-way split of what's left:
1. **Asset-class expansion + tax awareness** (#2, #30) — contained, logic-only.
2. **Itemised existing holdings & loans** (#10, #19, #20 full versions) — extends `risk.financial_snapshot`.
3. **Investor-knowledge questionnaire + literacy-adjusted explanation depth** (#6) — new quiz + a flag threaded into `advisor.py`'s prompt.
4. **Liquidity-need wired into allocation math** (#29) + **lumpsum+SIP combination mode** (#5) — both touch `allocation.build_plan`.
5. **Visual-design pass** (restrained palette, tooltips everywhere, friendly copy pass) — contained to `app.py`'s CSS and copy, lowest risk of breaking the engine.

Each of these can be built and tested independently against `test_engine.py`/`apptest_smoke.py` without touching the others' files much, since the engine/UI split already separates "calculation" (risk.py/allocation.py) from "presentation" (app.py) from "explanation" (advisor.py).
