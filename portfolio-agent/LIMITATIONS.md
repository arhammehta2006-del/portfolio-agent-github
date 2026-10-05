# Limitations

This is an educational prototype for a coursework assignment, not a product giving real
investment advice. Read alongside `DATA_SOURCES.md` (what the numbers are based on) and
`CHANGES_BACKLOG.md` (the full 94-item spec we triaged, and what's deliberately deferred).

## Not real financial advice
- The app says so on every screen. It has no SEBI Investment Adviser registration and isn't a
  substitute for one — a real deployment giving personalised investment advice in India would
  need that.
- Figures are estimates from stated assumptions, not guarantees. Markets can (and do) perform
  worse or better than modelled.

## Modelling simplifications
- Five broad asset classes (Liquid Fund, Debt Fund, Gold, Large-cap Equity, Mid-cap Equity), not
  individual securities or funds.
- Constant expected return/volatility within a scenario — no regime changes, no fat tails beyond
  what a normal-distribution Monte Carlo captures.
- No taxes (capital gains, STT) and no fees/expense ratios anywhere in the projections.
- No post-retirement spending/drawdown model — retirement is sized as a target corpus (25x annual
  expenses), not simulated through withdrawal.
- "Required risk" uses a single money-weighted-horizon simplification across all goals combined,
  rather than solving it goal-by-goal.
- The existing-portfolio tilt and EMI/debt checks use aggregate figures the user types in (total
  EMI, total existing equity/other) — not itemised holdings, loan amortisation schedules, or an
  actual portfolio import.
- "Liquidity need" is currently collected but informational only; it does not yet change the
  allocation math.

## Data
- `data/assumptions.csv` ships with **placeholder** return/volatility figures (documented as such
  in the file itself and the in-app "Assumptions & methodology" panel). A pipeline exists to
  replace them with real historical data (`build_assumptions.py`) but has not been run against
  real downloaded price series for this submission — see `DATA_SOURCES.md` for exactly what that
  would take.
- Emergency-fund months, the EMI-burden threshold, goal-type inflation rates, and the Sharpe
  ratio's risk-free rate are also stated, reasoned assumptions (see `config.py`), not fitted to
  current Indian market data.

## Scope not built
- No accounts or persistence — nothing is saved between sessions (by design, for privacy, but
  also a real limitation versus a product someone would return to).
- No integration with an actual mutual fund platform or broker to act on the recommendation.
- No multi-user support, no authentication.
- The original spec we were handed had 94 functional/UI requirements; we triaged to a tested
  "Phase 1" subset (see `CHANGES_BACKLOG.md` for the full item-by-item disposition and reasoning)
  rather than attempting all of them with no time to test the result.

## The bonus JS artifact specifically
- Its Monte Carlo simulation uses a different seeded random-number generator (`mulberry32` +
  Box-Muller) than the Python build's `numpy`, so exact simulated figures differ slightly between
  the two builds — the underlying math and conclusions are the same, this is expected, not a bug.
- Its free-text "Ask the advisor" agent only works live inside a claude.ai artifact viewer; outside
  that context (or if the viewer declines the AI permission prompt) it falls back to a generic
  template answer rather than failing.
