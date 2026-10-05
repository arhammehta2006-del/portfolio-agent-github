# Goal-Based Portfolio Planner (Business Analytics - Theme 4)

An interactive GenAI-assisted tool that turns a retail investor's goals, money and risk comfort into a
recommended portfolio, explains *why* it fits, and shows two alternatives to compare.

## Submission contents
This folder is the primary submission (working prototype). Everything the brief asks for:

| Deliverable | File |
|---|---|
| Working prototype | this folder — `streamlit run app.py` (see below), or try it instantly with no install: **[live demo artifact](https://claude.ai/artifact/Uqyro7k5BdMbkatJnLopLm)** |
| README / user manual | this file |
| Architecture diagram | `ARCHITECTURE.md` (`architecture.png`) |
| Test report with screenshots | `TEST_REPORT.md` + `screenshots/` |
| Limitations | `LIMITATIONS.md` |
| AI-use declaration | `AI_USE_DECLARATION.md` |
| Source/data documentation | `DATA_SOURCES.md` |

The live demo artifact is a separate, zero-setup JavaScript build of the same engine, useful for a
quick click-through without installing Python — see `ARCHITECTURE.md` for how it relates to this
Python app, which is the main submitted prototype.

## Run it
```
pip install -r requirements.txt
streamlit run app.py
```
Optional: set `export ANTHROPIC_API_KEY=...` (or add it as a Streamlit Cloud "secret" when deploying) for
AI-written explanations and the "Ask the advisor" chat. There is no key-entry box in the app itself — by
design, nothing asks a visitor for a key — so this is a server-side setting only. Without a key the app
still works fully, using a built-in rule-based explanation.

## How it works
| Step | File | Who does the work |
|---|---|---|
| Collect inputs (age, dependents, employment/income/debt, existing investments, emergency fund, goals, risk quiz) | `app.py` | Streamlit form, 7 steps |
| Validate inputs, build goals (goal-specific inflation), compute risk appetite/capacity, emergency-fund target | `risk.py` | Plain Python |
| Allocation rules, emergency top-up, priority-based funding split, step-up SIP, existing-portfolio tilt, 3 portfolios, Monte Carlo, Sharpe/stress metrics, required-risk, financial-health scorecard | `allocation.py` | Plain Python + numpy |
| Explain the numbers (short reasoning chips + narrative), answer follow-up questions | `advisor.py` | Claude (or rule-based fallback) |
| All tunable numbers | `config.py`, `data/assumptions.csv` | - |

**The AI never calculates.** It only receives the numbers computed by the code and explains them.

## App flow
`How it works → About you → Financial life → Money & goals → Risk comfort → Review → Your plan`
Questions are shown conditionally (e.g. the sole-earner checkbox only appears if you have dependents; the EMI
"high-interest" checkbox only appears if you entered an EMI; the SIP step-up slider only appears in SIP mode).
The final page follows: Investor snapshot → Financial health → Risk profile (appetite/capacity/required) →
Goals & timeline → Recommended portfolio → Why this fits you → Expected results (3 scenarios) → Risk analysis
(Sharpe ratio, stress decline, behind an "advanced" expander) → Compare alternatives → Action plan → Portfolio
maintenance, with Goal tracker / What-if / Ask the advisor / Download kept as secondary tabs underneath.

## Key rules (for the viva)
- **Risk appetite vs capacity vs required risk** (three separate angles, not one generic score): *appetite* = 40%
  stated label + 60% scenario-quiz answers. *capacity* = average of age, dependents, money-weighted goal horizon,
  emergency-fund coverage, and employment-stability points (reduced further if EMI burden is high). The
  **recommended profile is always the LOWER of appetite and capacity** — required risk never overrides this; it's
  surfaced as a note when it's higher, telling the client to adjust amount/date/target instead.
- **Required risk** = the annual return the client's stated amount and goals would actually need, solved against
  the money-weighted horizon, compared to what the Conservative/Moderate/Aggressive profiles are expected to
  deliver at that horizon → labelled Low/Moderate/Moderate-High/High.
- **Emergency fund** target = employment-type base months (Salaried 4, Self-employed/Freelancer 8, Student 3,
  Retired 6) + 1 month per dependent, capped at 12. Any shortfall is carved out of the investable amount FIRST,
  kept 100% liquid, before the rest is split across goals.
- Goal buckets: up to 3 years = Short, over 3 to 7 = Medium, over 7 = Long. Goals 1 year or less are 100% liquid.
- Each goal gets its own allocation from a bucket x profile table (`ALLOC` in `allocation.py`).
- Goals inflate at a **goal-type-specific rate** (Education 8%, Healthcare 9%, Travel/General 6%, Housing 7% —
  see `config.GOAL_INFLATION`), not one flat number for everything.
- Money is split across goals by **priority first** (Essential → Important → Aspirational), then nearest-date
  within a tier; leftover goes to open-ended wealth building.
- **Step-up SIP**: if the client expects their SIP to grow annually, the required starting contribution is solved
  by an explicit month-by-month future-value calculation (not the flat-SIP formula), so a growing income reaches
  the same goal with a smaller starting amount.
- **Existing portfolio awareness**: if the client reports existing holdings that are already equity-heavy (or
  light), the blended *new-money* allocation is nudged the other way, so the tool never blindly recommends more
  of what they're already overloaded on.
- Recommended portfolio = the profile from risk appetite/capacity; the other two profiles are the alternatives.
- Chance of reaching a goal = share of 2,000 simulated market futures that reach the (inflation-adjusted) target.
- **Sharpe ratio** and a **stress-decline** figure (a rarer, sharper hypothetical than the existing "bad year")
  are shown behind an "advanced" expander, each with a plain-English tooltip — not surfaced by default to avoid
  overwhelming a first-time investor.
- **Financial health scorecard** (Emergency Fund / Debt Level / Savings Rate / Retirement Planning / Insurance
  Protection / Investment Diversification) is assembled from the same computed numbers — any field the client
  skipped shows "Not assessed" rather than a guessed value.
- **Consistency checks**: the tool warns when a SIP exceeds disposable income, when EMI burden is high, when
  required risk exceeds the recommended profile, and when the Aggressive option still carries high equity exposure
  within 10 years of retirement.

## Data
`data/assumptions.csv` ships with PLACEHOLDER return/volatility values. Replace them with figures computed from real
historical data: put price files in `data/history/` and run `python build_assumptions.py` (see the script header).
Emergency-fund months, the EMI-burden threshold, goal-type inflation rates and the Sharpe ratio's risk-free rate are
also stated, documented placeholder assumptions — see the "ADDITIONS" section of `config.py` and the in-app
"Assumptions & methodology" sidebar panel, which explicitly separates user-provided data, model-estimated figures,
and default assumptions.

## Testing
- `python test_engine.py` — automated checks on the deterministic engine (risk scoring, emergency-fund top-up,
  priority-based funding, step-up SIP, existing-portfolio tilt, goal-specific inflation, Sharpe/stress metrics,
  consistency-check notes) against several personas. No pytest dependency needed.
- `python apptest_smoke.py` / `python apptest_smoke2.py` — drive the actual Streamlit app end to end via
  Streamlit's `AppTest` framework (two different personas/branches: with dependents & SIP step-up, and without
  dependents & lumpsum), catching runtime errors the pure-logic tests can't see, including that conditional
  questions correctly show/hide.

## Limitations
Educational tool, not financial advice. Uses five broad asset classes and simplified assumptions (constant returns
and volatility within a scenario, no taxes or fees, no post-retirement spending model). "Required risk" uses a
single money-weighted-horizon simplification rather than solving goal-by-goal. The existing-portfolio tilt and
EMI/debt checks are deliberately light-touch (aggregate figures, not itemised holdings or loan amortisation).
"Liquidity need" is currently informational only and does not yet change the allocation math. See
`CHANGES_BACKLOG.md` for the full list of requested features not yet implemented, and why.
