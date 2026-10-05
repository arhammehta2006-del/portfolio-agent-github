# Test Report

Three layers of testing, run fresh for this submission (commands and dates below), plus one real
bug found and fixed while reviewing a screenshot during this pass.

## 1. Automated logic tests — `python test_engine.py`

Ten test cases (TC1–TC10) exercise the deterministic engine directly, independent of the UI:
minimal defaults, emergency-fund shortfall sizing, high EMI burden + SIP-exceeds-income warnings,
existing-portfolio tilt, priority-based funding order, step-up vs flat SIP, goal-specific inflation,
near-retirement aggressive-equity flag, Sharpe/stress-decline sanity, and lumpsum mode.

```
=== TC1 ... === through === TC10 lumpsum mode ===
...
ALL CHECKS PASSED.
```

**Result: all checks passed.** Full console output is in `test_engine_output.txt` alongside this
report.

## 2. End-to-end UI tests — Streamlit `AppTest`

Two personas are driven through the *actual app*, not just the logic, via Streamlit's testing
framework (`streamlit.testing.v1.AppTest`), which runs the real `app.py` headlessly and checks for
exceptions plus the expected conditional UI:

- **`apptest_smoke.py`** — has dependents, SIP with step-up, high EMI burden, no health insurance:
  checks that the sole-earner/life-insurance checkboxes appear (dependents > 0), the EMI
  high-interest checkbox appears (EMI > 0), the step-up slider appears (SIP mode), the review page
  surfaces the emergency-fund-shortfall and no-insurance warnings, and the results page renders
  with no exception.
  ```
  PASS: initial load, title: Build your plan around your life.
  PASS: moved to About you
  PASS: moved to Financial life
  PASS: moved to Money & goals
  PASS: moved to Risk comfort
  PASS: moved to Review
  PASS: moved to Results (final plan page)
  ALL APPTEST STEPS COMPLETED WITHOUT EXCEPTION.
  ```
- **`apptest_smoke2.py`** — no dependents, Lumpsum, Student: checks the *opposite* conditional
  branches are correctly hidden (no sole-earner/life-insurance checkboxes, no EMI checkbox, no
  step-up slider) and the results page still renders cleanly with a very different profile (High
  risk, short horizon).
  ```
  Checkboxes with 0 dependents (expect NO w_sole): ['w_has_ret']
  Checkboxes with EMI=0 (expect NO w_emi_high): []
  Sliders with Lumpsum mode (expect NO w_stepup): []
  PASS: branch 2 (no dependents, lumpsum, student) reached Results cleanly.
  ```

**Result: both branches pass, all conditional fields behave correctly, no exceptions.**

## 3. Manual / visual walkthrough — real screenshots

Captured from the actual running app (`streamlit run app.py`), driven with Playwright, not mocked
up. One persona: 32-year-old, 1 dependent, ₹15,000/month SIP with a 10% step-up, a "Vacation" goal
and retirement.

| # | Screenshot | What it shows |
|---|---|---|
| 1 | `screenshots/01_intro.png` | Landing step — the 5-step overview and "Build my plan" entry point |
| 2 | `screenshots/02_about_you.png` | Age, dependents, retirement goal toggle |
| 3 | `screenshots/03_financial_life.png` | Income/expenses/EMI, existing holdings, emergency fund, insurance |
| 4 | `screenshots/04_money_goals.png` | SIP/Lumpsum choice, amount, step-up slider, the goals editor |
| 5 | `screenshots/05_risk_comfort.png` | Stated risk + the 3-question scenario quiz |
| 6 | `screenshots/06_review.png` | Final check before generating the plan |
| 7 | `screenshots/07_results_top.png` | Risk score, financial-health scorecard, goals & timeline table |
| 8 | `screenshots/08_why_this_fits.png` | Reasoning chips explaining the recommendation in plain English |
| 9 | `screenshots/09_compare_alternatives.png` | Conservative / Moderate / Aggressive side-by-side with the allocation bar |
| 10 | `screenshots/10_outcome_charts.png` | Chance-of-reaching-target chart and the full scenario comparison table |

### A real bug found and fixed during this pass

While reviewing screenshot 8, the "Why this fits you" chips showed literal `**double asterisks**`
instead of bold text (e.g. `**Risk score 6.0/10 (Moderate)**` rendered as-is rather than bolded).
Cause: `render_reasoning_chips()` in `app.py` wrapped the fallback explanation's markdown bullets
directly in HTML (`unsafe_allow_html=True`) without converting `**bold**` markdown into `<b>` tags
— and without escaping the text first, which was also a latent HTML-injection risk if a user typed
`<`/`>`/`&` into a goal name. Fixed by escaping the bullet text and then converting `**bold**` to
real `<b>` tags (see the diff in `app.py`, function `render_reasoning_chips`). Re-screenshotted
after the fix to confirm — screenshot 8 above is the corrected version. Re-ran the full test suite
(all three layers above) after the fix: still all green.

This is the kind of issue pure logic tests can't catch (the numbers behind `**bold**` were always
correct) and the automated `AppTest` checks didn't either (they check for exceptions and widget
presence, not rendered markup) — it only surfaced by actually looking at a screenshot, which is
exactly why this report includes real ones rather than a description of what the UI "should" show.

## 4. Live-demo artifact (bonus build)

The JS port (`logic.js`) was separately tested with 22 checks mirroring TC1–TC11 (including a
determinism check: identical inputs produce bit-identical output across repeated runs), and the
assembled wizard UI was smoke-tested end-to-end with jsdom across two branches (29 checks,
covering every conditional field plus the free-text AI agent's fallback path) — see the artifact's
own `test_logic.js` / `smoke_test.js` for that report, summarized in `AI_USE_DECLARATION.md`.
