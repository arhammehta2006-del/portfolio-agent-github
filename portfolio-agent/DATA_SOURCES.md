# Source & Data Documentation

## User-provided data (collected by the app, used as entered)
Age, dependents, employment type, retirement age, monthly income/expenses/EMI, whether any EMI is
high-interest, existing equity/non-equity holdings, current emergency savings, health/life
insurance flags, sole-earner status, liquidity need, investment mode (SIP/Lumpsum) and amount, SIP
step-up rate, goals (name, cost, years, priority, inflation category), stated risk appetite, and
3-question risk-scenario quiz answers. None of this is stored anywhere outside the browser
session — see `LIMITATIONS.md`.

## Model-estimated figures (computed by the app from the above)
Emergency-fund target, risk appetite/capacity/score, required-return-to-reach-goals, per-goal and
blended asset allocation, expected return/volatility/Sharpe ratio, Monte Carlo outcome ranges
(median / P10 / P90 / probability of reaching target), stress-decline and "bad year" figures,
financial-health scorecard. All computed in `risk.py`/`allocation.py` — see `ARCHITECTURE.md`.

## Default/assumed data (not user-provided, not computed — stated assumptions)

**`data/assumptions.csv`** — expected annual return and volatility for each of the five asset
classes. **Current status: placeholder values**, explicitly labelled as such in the file:

| Asset | Expected return | Volatility |
|---|---|---|
| Liquid Fund | 6.0% | 1.0% |
| Debt Fund | 7.0% | 3.0% |
| Gold | 8.0% | 14.0% |
| Large-cap Equity | 12.0% | 17.0% |
| Mid-cap Equity | 14.0% | 22.0% |

These were chosen to be directionally reasonable (roughly in line with commonly cited long-run
Indian market figures — e.g. Nifty 50-type large-cap equity in the low-to-mid teens, debt funds
mid-single-digits, gold high-single-digits) but are **not fitted to any specific downloaded
dataset** for this submission.

**To replace them with real historical data** (left as a documented, ready-to-run next step):
1. Download monthly or daily price history for each asset class — e.g. Nifty 50 TRI / Nifty
   Midcap 150 TRI from niftyindices.com, a representative debt/liquid fund's NAV history from
   AMFI or the fund's factsheet, a gold price series.
2. Save each as `data/history/<Asset Name>.csv` with `Date,Close` columns (file naming documented
   in `build_assumptions.py`'s header).
3. Run `python build_assumptions.py`, which computes CAGR, annualised return, and annualised
   volatility from the real series and overwrites `data/assumptions.csv`, recording the source and
   date range used for each asset.

**Other stated assumptions** (in `config.py`, all labelled "ADDITIONS" / documented inline):

| Assumption | Value | Where |
|---|---|---|
| General inflation | 6%/yr | `INFLATION` |
| Goal-specific inflation | Education 8%, Healthcare 9%, Travel/General 6%, Housing 7% | `GOAL_INFLATION` |
| Emergency fund, base months | Salaried 4, Self-employed/Freelancer 8, Student 3, Retired 6, Other 6 | `EMERGENCY_MONTHS_BASE` |
| Emergency fund, per dependent | +1 month, capped at 12 total | `EMERGENCY_MONTHS_PER_DEPENDENT`, `EMERGENCY_MONTHS_CAP` |
| High EMI-burden threshold | EMI > 40% of income | `HIGH_EMI_BURDEN_RATIO` |
| Risk-free rate (for Sharpe ratio) | 6.5% | `RISK_FREE_RATE` |
| Retirement corpus multiple | 25× annual expenses | `RETIREMENT_MULTIPLE` |
| Monte Carlo simulations per goal/profile | 2,000 (Python) / 1,500 (JS artifact, for in-browser speed) | `N_SIMS` |
| Correlation matrix between asset classes | Stated, not fitted (e.g. equity–debt 0.10, large/mid-cap 0.85) | `CORR` in `allocation.py` |

The in-app "Assumptions & methodology" panel (visible on every results page) shows this same
breakdown to the end user, so nothing here is hidden from someone using the tool.

## Bonus JS artifact
`logic.js` carries an identical copy of every constant above (kept in sync by hand during the
port, verified via the shared test cases in `TEST_REPORT.md`), so both builds use the same
assumptions.
